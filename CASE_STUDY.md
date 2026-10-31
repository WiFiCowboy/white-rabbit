# WHITE RABBIT — From field evidence to a reviewable decision

## Problem

A deployment decision can look complete while relying on missing or contradictory
evidence. The workflow needs to expose those gaps and stop at a defined boundary.

## Approach

This original demonstration evaluates power, connectivity, and access records for
a fictional site. A human dispatches the mission. Python processes only declared
local evidence files, validates the input contract, and preserves source references.
If evidence is missing, one designated supplemental lookup is allowed. Unresolved
gaps and conflicting observations remain explicit in the final report.

## Engineering decisions

| Choice | Operational reason |
| --- | --- |
| Standard-library Python | Reproducible offline execution with no package setup |
| Synthetic fixtures | Inspectable examples without transferring operational records |
| Fixed file and record limits | Bounded work per run |
| One supplemental lookup | Recovery with an explicit stopping point |
| Separate validation and disposition | A correctly processed mission may still be blocked |
| Source references and SHA-256 | Reviewable input identity and requirement-level evidence |
| Unique, ignored result directories | Preserve run outputs without tracking runtime artifacts |

## Observed results

The local macOS run on Python 3.8.5 passed all 16 unittest methods. The five
acceptance scenarios produced these results:

| Scenario | Disposition | Supplemental lookups |
| --- | --- | --- |
| Complete evidence | READY | 0 |
| Missing connectivity evidence | BLOCKED | 0 |
| Conflicting power observations | REVIEW_REQUIRED | 0 |
| Gap resolved by supplemental evidence | READY | 1 |
| Malformed mission input | INVALID_INPUT | 0 |

Tests also exercise wrong-site evidence, duplicate records, malformed field types,
file-read failures, path containment, evidence-reference integrity, and repeatable
decisions. These results show behavior on supplied fixtures and controlled tests;
they do not establish real deployment readiness or measured productivity gains.

## Human and AI roles

The project was developed with AI assistance and human review. The human
operator established the operating objective, approved the specification, and
executed local validation. AI assistance supported architecture, code generation,
tests, and documentation. The delivered runtime is
deterministic Python. Human-directed AI assistance during development is distinct
from autonomous AI execution in the program.

## Limits and next evidence

The demo does not evaluate evidence freshness, authoritative-source precedence,
physical measurements, or production dependencies. A hash identifies input bytes;
it does not authenticate the source. Extension to real operations would require
domain-specific criteria and separate validation.

Review the [input contract](README.md) and
[validation record](VALIDATION.md). No competition score,
performance comparison, or production autonomy is claimed.
