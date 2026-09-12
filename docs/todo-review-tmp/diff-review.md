# Diff review

The remediation changes 34 files. Every deletion in the working-tree diff was classified
before being accepted.

## Deletions

| Deleted construct | Location | Classification | Result |
|---|---|---|---|
| 212 boilerplate `TODO` comments | 31 modules | `CORRECT_REMOVAL` | Noise that was itself breaking `ruff check` (95 `E501`) and `ruff format --check` (21 files). Each was classified first (see `original-todo-ledger.md`) |
| `FailureBoundaryProbe = FiniteFloat \| PositiveInt` | `types.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by the per-axis domain union; no responsibility lost |
| `FailureBoundaryCoordinate.finite_level` / `node_count` / `event_count` / `band_count` | `provenance.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Four mutually exclusive optionals collapsed into one required `level`; strictly more constrained |
| `NumericSign = NewType("NumericSign", str)` | `types.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by a two-member `StrEnum` |
| `_failure_boundary_probe` body (4 option-null branches) | `dispatch.py` | `CORRECT_REMOVAL` | The null checks became unreachable once `level` is required and typed |
| `if coordinate.node_count is None: raise …` | `dispatch.py` | `CORRECT_REMOVAL` | Same — replaced by `_node_budget_level`, which validates the actual invariant |
| Duplicated `1e-12` tolerance literals | `config.py` | `CORRECT_REMOVAL` | Replaced by named module constants |
| Hardcoded `0.01` rho offset | `publication_rows.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by the authoritative configured case |
| 7 × hardcoded `* 1000.0` | `publication_rows.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Routed through `_runtime_milliseconds()` |
| `sys.platform` string comparisons ×3 | `paths.py`, `scaling.py` | `SHOULD_HAVE_BEEN_REFACTORED` | Replaced by `current_platform() is PlatformName.WIN32` |

No production deletion was classified `STILL_REQUIRED`, `MISSING_WIRING`, or `UNKNOWN`.

## Additions

| Addition | Location | Justification |
|---|---|---|
| `PlatformName`, `Platform`, `current_platform()` | `types.py` | Closes a real closed-domain string abuse; cross-cutting home |
| `NumericSign(StrEnum)` | `types.py` | Replaces a 2-value string alias |
| 7 explicit axis narrowing validators | `failure_boundaries.py` | Each raises on an axis/value mismatch, converting a silent impossibility into a fail-fast error |
| `_node_budget_level` | `dispatch.py` | Local narrowing for the dedicated optimizer evaluator |
| `_runtime_milliseconds` | `publication_rows.py` | Single authoritative seconds→milliseconds conversion |
| `_principal_coverage_stress_case` | `publication_rows.py` | Resolves the authoritative configured case instead of re-deriving governed values |
| `_EXACT_AGREEMENT_*` constants | `config.py` | De-duplicate a governed tolerance |

Every addition removes a duplication, closes a real domain, or fails fast on an impossible
state. No wrapper, adapter, proxy, one-field value object, or conversion helper was added,
and none was found to remove. The three helpers introduced
(`_runtime_milliseconds`, `_principal_coverage_stress_case`, `_node_budget_level`) each
replace repeated or duplicated logic rather than forwarding a value, and each is called
from at least two sites or eliminates a coercion.

## Behaviour preservation

* `FailureBoundary` probe values, coordinate display text, artifact content and reported
  level strings are byte-identical to before: `level` is now the typed value that
  previously arrived via `int(level)`/`float(level)`, and display still renders it with
  `str(...)`.
* `NumericSign.NON_NEGATIVE` renders as `""` and `NEGATIVE` as `"-"`, so
  `canonical_number_token` output is unchanged (verified by the paths/artifact tests).
* `current_platform()` returns a `PlatformName` member exactly when `sys.platform` is one
  of the three enumerated values, and the raw string otherwise, so the `win32` branches
  behave identically on every platform.
* The Figure-4 principal coverage-stress cell selection now resolves the configured case
  that satisfies the same three conditions that the previous law/band/offset filter
  expressed (`law == timing_terminal_harmful_late`, `band_count == finest_bands`,
  `rho == true_information + rho_offset`), and additionally requires
  `sensitivity_reference == TRUE_INFORMATION` and `beta_offset is None`, which is what makes
  the match unique. No scientific selection criterion was invented: every field used is an
  existing authoritative configuration field.
