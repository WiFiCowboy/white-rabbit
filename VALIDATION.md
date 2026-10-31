# WHITE RABBIT validation record — v0.1

## Local operator run

Date recorded: October 30, 2026 (Pacific).
Environment: Personal Mac, Python 3.8.5.
Evidence: operator-supplied terminal output from local installation and validation.
The development assistant did not independently access the Mac.

```text
Ran 16 tests in 0.042s
OK
complete: READY | validation=PASSED | recovery=0
missing: BLOCKED | validation=PASSED | recovery=0
conflict: REVIEW_REQUIRED | validation=PASSED | recovery=0
recovery: READY | validation=PASSED | recovery=1
invalid: INVALID_INPUT | validation=NOT_COMPLETED | recovery=0
```

The 16 unittest methods include a five-scenario acceptance test with subtests.
The reported 0.042 seconds is test-suite elapsed time, not a productivity metric
or an end-to-end performance comparison. INVALID_INPUT is the expected result
for the deliberately malformed fixture. Validation PASSED means the evidence
evaluation is internally consistent; it does not mean deployment is READY.

## Assistant build verification

Python 3.12.14 on Linux: 16 unittest methods passed and the CLI suite produced
the five expected dispositions. Source parsed with the Python 3.8 syntax grammar.
Package installation was tested in an isolated temporary Git repository, including
refusal to replace an existing demo directory.

## Reproduce

From the repository root:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B runner.py --suite
```

Reports are created under `.runs/`, ignored by `.gitignore`. Each report records input hashes, requirement-level references,
disposition, validation status, counts, issues, and elapsed time.

## Scope

All supplied fixtures are original synthetic examples. No external dependencies,
network calls, credentials, inherited sanitizer, or work-lane materials are needed.
These checks do not constitute a full security audit, ownership determination,
real-world deployment assessment, or public-release approval.

## Standalone package verification

The unchanged runtime, tests, and fixtures were assembled with directory-relative
entry points. On Python 3.12.14 (Linux), all 16 tests passed and the five CLI
scenarios produced the expected dispositions in this standalone layout.
Standalone macOS validation on October 30, 2026: operator-supplied terminal
output confirms all 16 tests passed in 0.036 seconds on Python 3.8.5.
All five CLI scenarios matched their expected dispositions and recovery counts.
