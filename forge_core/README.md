# FORGE Core — Brief, dispatch, reconcile

Local proof of concept: one human-directed mission brief, one allowlisted WHITE
RABBIT executor, one reconciliation record. Original code and synthetic inputs.
This demonstrates software-enforced workflow boundaries around a deterministic
executor. It does not implement autonomous AI agents or cross-chat messaging.

## Run from the repository root

Python 3.8 or later; standard library only. The accepted WHITE RABBIT v0.1 must
be present as the root-level `runner.py` and `fixtures/` directory. Its runtime
is unchanged by this extension. FORGE Core checks its expected SHA-256 before dispatch.

```bash
python3 -B -m unittest discover -s forge_core/tests -v
python3 -B forge_core/core.py
```

The default brief uses WHITE RABBIT's synthetic recovery scenario. Expected:

```text
Execution: COMPLETED
Reconciliation: ACCEPTED
Mission: READY_FOR_REVIEW
Human decision: PENDING_ACTUAL
Dispatch attempts: 1
```

A fresh `.runs/nexus-.../` directory contains `SITREP.md` and `nexus_record.json`.
The directory is ignored by this demo's `.gitignore`. Each run creates new files;
existing runs are preserved. No Git commands, credential access, network requests,
package installation, or external service writes are performed by the demo.

## Brief-to-result contract

The brief is `briefs/readiness.json`. It records objective, named executor,
allowlisted scenario, expected mission and site identities, requested end state,
and execution limits. No free-form shell command or arbitrary input path is accepted.
The permitted source is the selected WHITE RABBIT fixture directory. It contains
exactly the named mission and primary evidence inputs, plus a supplemental file
for the recovery scenario. Sources are snapshotted before dispatch.

| Control | Fixed behavior in v0.1 |
| --- | --- |
| Executor | Accepted WHITE RABBIT runtime, checked against its SHA-256 |
| Dispatch attempts | Exactly one; no retry after failure or timeout |
| Executor timeout | Five seconds, enforced with a subprocess timeout |
| Scenarios | complete, missing, conflict, recovery, invalid |
| Brief/input file size | 64 KiB each |
| WHITE RABBIT recovery | At most one supplemental lookup, unchanged from v0.1 |
| Executor output | Checked against a 256 KiB limit after process capture |
| Consequential human decision | Always PENDING_ACTUAL |

The five-second timeout applies to the child executor, not a measured end-to-end
service guarantee. Output is captured before its size check, so this is not a
memory sandbox. Only the trusted, hash-checked local executor is supported.

## Reconciliation

Nexus checks the result schema, expected mission/site identities, input receipts,
file hashes, operation counts, requirement coverage, source references, and final
disposition against the actual supplied fixture records. Input hashes are checked
again after execution and reconciliation. A zero process exit code is insufficient.

| Executor result | Execution | Reconciliation | Nexus mission state |
| --- | --- | --- | --- |
| Complete evidence | COMPLETED | ACCEPTED | READY_FOR_REVIEW |
| Missing evidence | COMPLETED | ACCEPTED | BLOCKED |
| Conflicting evidence | COMPLETED | ACCEPTED | REVIEW_REQUIRED |
| Recovery within budget | COMPLETED | ACCEPTED | READY_FOR_REVIEW |
| Deliberately invalid mission | COMPLETED | ACCEPTED | INVALID_INPUT |
| Forged/mismatched result | COMPLETED | REJECTED | RECONCILIATION_FAILED |
| Executor failure | FAILED | NOT_PERFORMED | EXECUTION_FAILED |
| Executor timeout | TIMED_OUT | NOT_PERFORMED | EXECUTION_FAILED |

An invalid brief stops before dispatch with INVALID_BRIEF. A valid brief whose
executor or fixture precheck fails stops with PRECHECK_FAILED. ACCEPTED means the
returned record passed reconciliation; it does not mean the mission is ready.
READY_FOR_REVIEW means the synthetic evidence satisfies the stated checks, with
the final human decision still pending. Nothing in the program grants deployment
authority or writes an approval.

The command returns 0 for an accepted reconciliation, including BLOCKED and
INVALID_INPUT results, and 2 for precheck, dispatch, or reconciliation failures.
Read the explicit states rather than treating exit status as mission approval.

## Records and limitations

The Nexus record includes the brief hash, executor hash, permitted source,
scenario, input snapshot, dispatch count, three distinct outcome states, original
reconciled executor result, issues, elapsed time, and pending human decision.
Timings are descriptive. Hashes identify bytes; they do not authenticate ownership
or establish a security boundary against concurrent hostile filesystem changes.

No persisted mission queue, autonomous planning, multiple-executor routing, live
service integration, or cross-run resume is implemented. Each invocation is one
bounded mission. The five built-in scenarios are acceptance cases for that contract.

See [VALIDATION.md](VALIDATION.md) for test evidence and
[CASE_STUDY.md](CASE_STUDY.md) for the architecture and observed outcomes.
`PENDING_ACTUAL` denotes the human operator's pending decision. This standalone
candidate remains under review; its outputs grant no consequential authority.
