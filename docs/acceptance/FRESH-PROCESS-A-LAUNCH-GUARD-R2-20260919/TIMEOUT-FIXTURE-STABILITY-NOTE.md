# Timeout fixture stability note

This is an evidence-quality note, not a new production finding.

R2's `_communicate_bounded()` implementation passed the intended bounded
normal/timeout/inherited-pipe behavior in the candidate result and in an
independent successful run. However, the bundled timeout test starts a child
and gives it only 50ms before requiring exactly one `timeout-line` in stdout.
Independent repeated assertion runs produced 3 passes and 2 assertion failures.
No-assertion direct runs returned zero or one line, never more than one; the
zero-line cases are consistent with the child being killed before startup/flush.

The test should synchronize child readiness or assert “at most once” rather
than treating one short-lived print as guaranteed evidence. Until stabilized,
the shipped `PASS_BOUNDED_TIMEOUT_CHILD_TESTS` record is not independently
reproducible evidence by itself.
