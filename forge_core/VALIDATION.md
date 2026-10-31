# FORGE Core v0.1 — Validation

Build environment: Python 3.12.14, Linux. Python source also parsed using the
Python 3.8 syntax grammar. Local macOS validation confirmed by operator-supplied terminal output on October 31, 2026: Python 3.8.5 passed all 15 tests in 1.238 seconds. The default mission completed one dispatch, reconciled as ACCEPTED, and returned READY_FOR_REVIEW with human decision PENDING_ACTUAL.

Fifteen unittest methods cover:

- All five WHITE RABBIT fixture outcomes, using real child-process dispatch.
- Unknown executor, excess dispatch budget, boolean limit, and arbitrary scenario rejection.
- Changed executor identity preventing dispatch.
- Timeout handling with exactly one attempted dispatch and no retry.
- Nonzero process failure and zero-exit malformed JSON.
- Wrong mission identity, forged input hash, forged READY disposition, and forged evidence references.
- Changed input snapshot during execution.
- Duplicate JSON keys in the mission brief.

The default recovery mission completed, reconciled as ACCEPTED, and returned
READY_FOR_REVIEW with human decision PENDING_ACTUAL and exactly one dispatch.
Timeout behavior is exercised by simulated subprocess timeout in the unit test;
it is not a measured real-time reliability or production security claim.

The accepted WHITE RABBIT runner, tests, and fixtures are unchanged. This
extension uses the root-level WHITE RABBIT runtime and its synthetic fixtures.
No work-lane material or private Git history is included.

## Standalone candidate validation

Runtime adaptations cover two path references: the root-level WHITE RABBIT
executor location and the reported fixture-source path. The required executor
SHA-256 is unchanged. The original 15 Core tests and 16 WHITE RABBIT tests passed
on Python 3.12.14 (Linux). Recovery and blocked walkthroughs produced the expected
separate execution, reconciliation, and mission states in this layout.

Standalone macOS validation confirmed by operator-supplied output on October 31, 2026, using Python 3.8.5: all 16 WHITE RABBIT tests passed in 0.038 seconds and all 15 FORGE Core tests passed in 1.168 seconds. The default mission completed one dispatch, reconciled as ACCEPTED, and returned READY_FOR_REVIEW with human decision PENDING_ACTUAL. These results validate the adapted standalone layout.
