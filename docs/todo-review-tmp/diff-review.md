# Diff review

Significant deletions were classified as follows:

| Deleted area | Classification | Result |
|---|---|---|
| Real-trajectory literals/collections | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by typed, validated configuration and consumed in preprocessing. |
| Skeleton leaf collections | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by exhaustive `ProjectSummaryLeaf` iteration. |
| Numerical global controls | `SHOULD_HAVE_BEEN_REFACTORED` | Rehomed under validated numerical configuration. |
| Persistence/provenance aliases | `SHOULD_HAVE_BEEN_REFACTORED` | Centralized in `types.py`; no responsibility removed. |
| Flat failure fields | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced with `FailureDiagnostic`. |
| Old seed constant forwards | `CORRECT_REMOVAL` | Removed during this audit; internal consumer uses `SeedMaterialGrammar` directly. |

No production deletion was classified `STILL_REQUIRED` or `MISSING_WIRING`.
