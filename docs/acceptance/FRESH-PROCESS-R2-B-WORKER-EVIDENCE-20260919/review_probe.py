from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TARGET_PIDS = ("1161595", "1162100")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def verify_package(root: Path) -> dict[str, Any]:
    manifest_path = root / "DELIVERY_MANIFEST-R2-B-WORKER-EVIDENCE-20260919.json"
    index_path = root / "EVIDENCE_INDEX.json"
    manifest = read_json(manifest_path)
    entries = manifest.get("files", [])
    expected = {item["path"]: item for item in entries}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path not in {manifest_path}
    }
    missing = sorted(set(expected) - actual)
    extra = sorted(actual - set(expected))
    mismatches: list[dict[str, Any]] = []
    total = 0
    for relative, item in sorted(expected.items()):
        path = root / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        total += size
        if size != item.get("bytes") or digest != item.get("sha256"):
            mismatches.append(
                {
                    "path": relative,
                    "expected_bytes": item.get("bytes"),
                    "actual_bytes": size,
                    "expected_sha256": item.get("sha256"),
                    "actual_sha256": digest,
                }
            )
    index = read_json(index_path)
    index_entries = index.get("entries", [])
    return {
        "manifest": {
            "sha256": sha256_file(manifest_path),
            "declared_file_count": manifest.get("file_count"),
            "declared_total_bytes": manifest.get("total_bytes"),
            "entry_count": len(entries),
            "actual_total_bytes": total,
            "missing": missing,
            "extra": extra,
            "mismatches": mismatches,
            "ok": not missing and not extra and not mismatches and len(entries) == manifest.get("file_count") and total == manifest.get("total_bytes"),
        },
        "index": {
            "sha256": sha256_file(index_path),
            "declared_artifact_file_count": index.get("artifact_file_count"),
            "declared_artifact_total_bytes": index.get("artifact_total_bytes"),
            "entry_count": len(index_entries),
            "entry_total_bytes": sum(int(item.get("bytes", 0)) for item in index_entries),
            "remote_worker_logs_copied": index.get("remote_worker_logs_copied"),
            "remote_worker_bytes_copied": index.get("remote_worker_bytes_copied"),
            "weights_or_tensors_touched": index.get("weights_or_tensors_touched"),
            "ok": len(index_entries) == index.get("artifact_file_count") and sum(int(item.get("bytes", 0)) for item in index_entries) == index.get("artifact_total_bytes"),
        },
    }


def command_result(raw: Path, stem: str) -> dict[str, Any]:
    command = read_text(raw / f"{stem}-command.txt")
    exit_text = read_text(raw / f"{stem}.exit.txt")
    stdout = read_text(raw / f"{stem}.stdout.txt")
    stderr = read_text(raw / f"{stem}.stderr.txt")
    exit_match = re.search(r"(?:^|\n)0\s*(?:\n|$)", exit_text)
    return {
        "command_sha256": sha256_file(raw / f"{stem}-command.txt"),
        "command": command.strip(),
        "exit_record": exit_text.strip(),
        "exit_record_is_zero": bool(exit_match),
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    shared = args.shared.resolve()
    supplement = args.supplement.resolve()
    raw_shared = shared / "raw"
    raw_supplement = supplement / "raw"
    inventory = read_text(raw_shared / "207-inventory.stdout.txt")
    inventory_lines = inventory.splitlines()
    ray_start = next((i for i, line in enumerate(inventory_lines) if line.startswith("BEGIN RAY_LOG_CANDIDATES")), None)
    ray_end = next((i for i, line in enumerate(inventory_lines) if line.startswith("END RAY_LOG_CANDIDATES")), None)
    ray_lines = inventory_lines[ray_start + 1 : ray_end] if ray_start is not None and ray_end is not None else []
    file_rows = [line for line in ray_lines if re.match(r"^\d+\t", line)]
    exact_inventory_hits = [line for line in inventory_lines if any(pid in line for pid in TARGET_PIDS)]
    inventory_exit = read_text(raw_shared / "207-inventory.exit.txt")
    inventory_stderr = read_text(raw_shared / "207-inventory.stderr.txt")
    inventory_script = read_text(raw_shared / "207-inventory-script.sh")
    ray_files = sorted((shared / "evidence" / "ray-logs").glob("*"))
    ray_log_hits: dict[str, list[dict[str, Any]]] = {}
    for path in ray_files:
        if not path.is_file():
            continue
        hits = [
            {"line": line_no, "text": line[:500]}
            for line_no, line in enumerate(read_text(path).splitlines(), 1)
            if any(pid in line for pid in TARGET_PIDS)
        ]
        if hits:
            ray_log_hits[path.name] = hits[:10]

    searches = {
        stem: command_result(raw_supplement, stem)
        for stem in (
            "207-worker-name-enumeration",
            "207-session-wide-worker-name-enumeration",
            "207-worker-content-correlation",
        )
    }
    correlation = read_json(supplement / "evidence" / "B-PID-ANCHOR-CORRELATION.json")
    search_stdout_empty = all(item["stdout_bytes"] == 0 for item in searches.values())
    search_stderr_empty = all(item["stderr_bytes"] == 0 for item in searches.values())
    search_exit_zero_records = all(item["exit_record_is_zero"] for item in searches.values())

    result = {
        "schema": "fresh-process-r2-b-worker-narrow-independent-review-v1",
        "reviewed_at": "2026-09-19",
        "scope": {
            "read_only": True,
            "new_ssh": False,
            "rerun": False,
            "expanded_scan": False,
            "weights_or_tensors_touched": False,
        },
        "supplement_integrity": verify_package(supplement),
        "shared_inventory": {
            "path": str(raw_shared / "207-inventory.stdout.txt"),
            "sha256": sha256_file(raw_shared / "207-inventory.stdout.txt"),
            "inventory_exit_record": inventory_exit.strip(),
            "inventory_stderr": inventory_stderr,
            "ray_section_present": bool(ray_lines),
            "ray_section_file_row_count": len(file_rows),
            "ray_python_core_worker_row_count": sum("python-core-worker-" in line for line in file_rows),
            "ray_worker_out_err_row_count": sum("/worker-" in line and (line.endswith(".out") or line.endswith(".err")) for line in file_rows),
            "exact_target_pid_hits_anywhere": exact_inventory_hits,
            "exact_target_pid_hits_in_ray_section": [line for line in ray_lines if any(pid in line for pid in TARGET_PIDS)],
            "script_has_timeout_or_mask": "timeout 15s find" in inventory_script and "|| true" in inventory_script,
            "script_uses_find_P_and_type_f": "find -P" in inventory_script and "-type f" in inventory_script,
            "symlink_inventory": "not_collected_by_find_P_type_f",
        },
        "existing_copied_ray_logs": {
            "file_count": len([path for path in ray_files if path.is_file()]),
            "target_pid_content_hits": ray_log_hits,
        },
        "new_limited_searches": {
            "results": searches,
            "all_recorded_exit_zero": search_exit_zero_records,
            "all_stdout_empty": search_stdout_empty,
            "all_stderr_empty": search_stderr_empty,
            "pipeline_without_pipefail": all("pipefail" not in item["command"] for item in searches.values()),
            "interpretation": "限定文件名/内容搜索没有返回目标 PID 路径或内容；exit=0 只记录了外层命令结果，不能独立证明 find/grep/xargs 每一段成功，也不能证明 worker 日志绝对不存在。",
        },
        "correlation_summary": {
            "status": correlation.get("status"),
            "requested_pids": [item.get("pid") for item in correlation.get("pid_phase_correlation", [])],
            "exact_stdout_stderr_paths_found": len(correlation.get("worker_log_discovery", {}).get("filename_pid_matches_in_logs_root", []))
            + len(correlation.get("worker_log_discovery", {}).get("filename_pid_matches_in_session_root", [])),
            "copied": correlation.get("worker_log_discovery", {}).get("copy_performed"),
            "path_size_mtime_records": correlation.get("worker_log_discovery", {}).get("path_size_mtime_records"),
            "filename_pid_matches_in_logs_root": correlation.get("worker_log_discovery", {}).get("filename_pid_matches_in_logs_root"),
            "filename_pid_matches_in_session_root": correlation.get("worker_log_discovery", {}).get("filename_pid_matches_in_session_root"),
            "content_pid_matches_in_session_out_err_log_files": correlation.get("worker_log_discovery", {}).get("content_pid_matches_in_session_out_err_log_files"),
        },
        "finding": "NO_CONCRETE_WORKER_LOG_PATH_OR_ROTATION_SYMLINK_CLUE_FOUND_IN_LIMITED_LOCAL_EVIDENCE; B_INTERNAL_ABORT_CAUSE_NOT_RECOVERED",
        "overall": "PARTIAL_EVIDENCE_SUPPLEMENT",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall": result["overall"], "finding": result["finding"], "manifest_ok": result["supplement_integrity"]["manifest"]["ok"], "search_stdout_empty": search_stdout_empty}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
