# WHITE RABBIT

**Bounded evidence processing for a fictional deployment-readiness decision.**

A field decision depends on complete, consistent evidence. This small offline
Python demonstration makes missing information, contradictory observations, and
recovery limits visible in a reviewable report.

A human dispatches a mission. The runner checks declared local evidence files,
permits at most one supplemental lookup, validates source references, and produces
a JSON report and a Markdown SITREP. It takes no deployment action.

## Run it

Python 3.8 or later. Standard library only; no packages, API keys, or network access
are required. From this directory:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B runner.py --suite
```

Expected dispositions:

```text
complete: READY | validation=PASSED | recovery=0
missing: BLOCKED | validation=PASSED | recovery=0
conflict: REVIEW_REQUIRED | validation=PASSED | recovery=0
recovery: READY | validation=PASSED | recovery=1
invalid: INVALID_INPUT | validation=NOT_COMPLETED | recovery=0
```

The malformed scenario is intentionally invalid. Each CLI execution creates a
unique `.runs/run-.../` directory containing JSON and Markdown reports. Runtime
output is ignored by `.gitignore` and existing reports are preserved.

Run one mission:

```bash
python3 -B runner.py --mission fixtures/recovery/mission.json
```

## What to inspect

| Example | Engineering behavior |
| --- | --- |
| `fixtures/missing/` | Stops short of readiness when evidence is absent |
| `fixtures/conflict/` | Preserves contradictory observations and references |
| `fixtures/recovery/` | Resolves a gap within one permitted supplemental lookup |
| `tests/test_runner.py` | Exercises acceptance cases and failure controls |
| Generated `recovery.md` and `conflict.md` | Show the human review surface |

The local Mac run passed 16 unittest methods, including five acceptance-scenario
subtests. See the [validation record](VALIDATION.md) for the evidence and limits,
and the [engineering case study](CASE_STUDY.md) for the design rationale.

## Input contract

Mission JSON contains exactly these fields:

| Field | Contract |
| --- | --- |
| `mission_id` | Nonempty text, at most 120 characters, no ASCII controls |
| `site` | Same text constraint; matched exactly |
| `requirements` | 1–16 unique requirement names |
| `evidence_files` | 1–2 explicitly named relative JSON files |
| `supplemental_file` | One relative JSON filename, or null |
| `max_recovery_lookups` | Integer 0 or 1 |

Each evidence document has a `records` array of at most 128 records. Each record
contains exactly `record_id`, `site`, `requirement`, and boolean `ready`. Record IDs
must be unique across files read. Wrong-site records cannot satisfy a requirement.

Input files are UTF-8 JSON, limited to 64 KiB each. Duplicate JSON keys, absolute
evidence paths, parent traversal, and symlink evidence paths are rejected. These
are local convenience controls, not an adversarial filesystem security boundary.

Primary evidence is read first. A missing requirement may trigger one declared,
budgeted supplemental-file read. Supplemental evidence cannot silently replace
primary observations. There is no unbounded retry loop.

## Decision rules

| Requirement evidence | Requirement state |
| --- | --- |
| None | MISSING |
| Positive only | SATISFIED |
| Negative only | NOT_READY |
| Both positive and negative | CONFLICT |

Any conflict produces REVIEW_REQUIRED. Otherwise missing or negative evidence
produces BLOCKED. READY requires every requirement to be SATISFIED.
Malformed or unreadable input produces INVALID_INPUT. Evaluation validation
PASSED means references and results are internally consistent; it does not mean
the deployment is READY.

Reports contain input SHA-256 hashes, requirement-level source references, issues,
read and recovery counts, and elapsed time. Hashes identify bytes, not authenticity.
Decisions are repeatable for the same inputs; timestamps and durations vary.

The suite command returns zero after producing reports, including its deliberately
invalid case. The unittest suite checks acceptance. Single-mission runs return 2
for INVALID_INPUT and 0 for evaluated dispositions. A zero exit code alone is not
readiness approval.

## Scope and development

All supplied fixtures are fictional. This is a compact engineering demonstration,
not a production deployment tool. It does not model evidence freshness, source
authority, physical measurements, or real engineering acceptance criteria.
No performance improvement or real-world readiness claim is made.

Developed with AI assistance and human review. The runtime is deterministic
Python; it does not contain an autonomous AI agent. The human operator supplies
the mission, reviews evidence, and retains consequential decisions.
