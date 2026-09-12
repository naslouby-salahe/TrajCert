# Original unfinished-work marker ledger

## Reconstruction

The pre-change marker population was reconstructed from the committed pre-remediation
state (`git show HEAD:…`, i.e. `db67419`), not from the current tree, and every marker was
cross-checked against the code it annotated.

**Total pre-existing markers: 213**, in exactly three auto-generated templates:

| Template | Count |
|---|---|
| `# TODO: should be constant` | 149 |
| `# TODO: do not use primitives. Fix by introducing a proper error type or message class and identify and fix why architecture tests didn't catch this` | 55 |
| `# TODO: should be enum` | 9 |

Because the text is templated rather than situated, the markers are **not trustworthy
statements of intent**. They were mechanically appended across 31 modules; the same
sentence was applied to 55 unrelated aliases. Each was therefore classified on its own
merits as *applies*, *misworded*, or *nonsense*.

## Template 1 — `should be constant` (149): overwhelmingly FALSE POSITIVE

Audit of every occurrence showed the annotated literals are mathematical identities,
loop/quantile conventions, array indexing, or numeric-literal display ranges. Named
constants for these would be exactly the "speculative constants" CLAUDE.md §2 forbids, and
the codebase already enforces the opposite rule mechanically (`RULE_CONSTANT` in
`tools/source_audit.py`: module-level numeric constants outside `config.py` are a
violation, with `test_hardcoded_values.py` enforcing it).

Representative false positives, each verified as correct code:

| Site | Literal | Why a constant is wrong |
|---|---|---|
| `analysis/bootstrap.py:48-52` | `1.0 - level`, `alpha / 2.0`, `1.0 - alpha / 2.0` | Standard percentile-bootstrap quantile definition |
| `comparators/ignorable_delay.py:105`, `inference/confidence.py:154,177` | `(lower + upper) / 2.0` | Bisection midpoint identity |
| `inference/confidence.py:78` | `betaln(successes + 0.5, failures + 0.5)` | Jeffreys prior parameter, not a tunable value |
| `math/oracle.py:173` | `(mpf(bands) + mpf(1)) / mpf(2)` | Band-centre arithmetic |
| `analysis/sign_flip.py:41-44` | `rng.integers(0, 2, …)`, `*= 2.0`, `-= 1.0` | Sign-flip Rademacher arithmetic |
| `data/laws.py:74` | `(bands + 1) / 2.0` | Symmetric band centre |
| `reporting/figures.py:175,180,202,226,237,244,305,341,365` | `linewidth=3.0/1.0`, `axvline(0.0)`, `(0.0, 1.0)` | Matplotlib rendering styling and axis reference lines |
| `config.py:106` | `endpoint_band_count != 1` | `BandCount = PositiveInt`; the one-band endpoint partition is an intrinsic domain invariant already guarded by config validation |
| `reporting/publication_rows.py:1248` | `0.0 <= u_beta_value <= unresolved` | Mathematical range test; the lower bound is zero by definition |

`Status: ANALYZED, REVIEWED` → markers removed as **justified false positives**; no code
change warranted. No rule, test, or validation was weakened.

## Template 2 — `do not use primitives` (55): one real defect cluster, 54 misworded

The 55 aliases in `types.py` are `NewType`/`Annotated` domain contracts. Two independent
facts establish that the boilerplate reason is misapplied to them:

1. The sentence "introducing a proper error type or message class" is only meaningful for
   the error-representation aliases (`FailureMessage`, `ExceptionClassName`,
   `TracebackText`). It is incoherent for `ClientId`, `DatasetChecksumHex`, `DigestHex`,
   `PlanDigest`, `LawName`, `PartitionName`, `BandCount`, etc.
2. `NewType` *is* the project's mechanism for named domain types, and all 55 aliases have
   real usages (verified: none unused). `types.py` is exempt-by-design from the
   primitive-annotation rule (`tools/source_audit.py:239`). Converting a genuinely open
   vocabulary (client ids, digests, dataset columns, generated display text) into an enum
   would be a false enum — itself a defect class (see `enum-audit.md`).

**One genuine defect cluster was found and fixed** — the same root error the boilerplate was
gesturing at, in the `FailureBoundary*` family:

| Item | Detail |
|---|---|
| Original location | `src/trajcert/types.py:146` (`FailureBoundaryProbe`); `provenance.py:73` (`FailureBoundaryCoordinate`) |
| Original text | `FailureBoundaryProbe = FiniteFloat \| PositiveInt` |
| Underlying intent | A failure-boundary probe must be a *domain-typed* value, not an untyped float-or-int whose meaning depends on the axis |
| What was wrong | The probe was a union of generic primitives, so callers coerced with `int(level)` (`failure_boundaries.py:75`, and `bands = int(level)`) and `float(level)` (`plan.py:594`), then re-unwrapped with `str(node_budget)` / `str(level)` for display. `FailureBoundaryCoordinate` carried four mutually exclusive optional fields (`finite_level`, `node_count`, `event_count`, `band_count`) plus `q1`/`q0`, so nothing prevented an axis/value mismatch |
| Resolution | `FailureBoundaryProbe` became a union of the real per-axis domain types (`Probability`, `TimingContrast`, `InformationNats`, `RiskOffset`, `BandCount`, `EventCount`, `OuterMaxNodes`). `FailureBoundaryCoordinate` now carries exactly one required `level: FailureBoundaryProbe` plus its `q1`/`q0` pair. Each axis is narrowed once by an explicit fail-fast `isinstance` validator (`_probability_level`, `_timing_contrast_level`, `_information_margin_level`, `_risk_offset_level`, `_band_count_level`, `_sample_size_level`, `_node_budget_level`), removing every `int(...)`/`float(...)`/`str(...)` coercion. `dispatch._failure_boundary_probe` collapsed from four option-null checks to `return coordinate.level` |
| Status | `RECOVERED`, `CORRECTLY_FIXED`, `VERIFIED` |

The remaining 54 aliases were retained with their `NewType` contracts intact and their
boilerplate markers removed as misworded (`Status: ANALYZED, REVIEWED`).

## Template 3 — `should be enum` (9): three real, six FALSE POSITIVE

| Original site | Original text | Assessment |
|---|---|---|
| `paths.py:272` | `CoordinateToken("0")` | Not an enum. A canonical zero token — an open generated token, correctly a `CoordinateToken` |
| `paths.py:275,278` | `…lstrip("0") or "0"`, `…rstrip("0") or "0"` | Not an enum. Decimal-digit string processing; `"0"` is a digit literal |
| `paths.py:305` | `if integer == "0":` | Not an enum. Single-character digit test |
| `math/oracle.py:36` | `_ORACLE_PRECISION_MUST_BE_POSITIVE = "oracle precision must be positive"` | Misworded: already a named module constant used at 4 raise sites, not a closed domain. `RESOLVED_NO_CHANGE` |
| `paths.py:24` | `_WINDOWS_EXTENDED_LENGTH_PREFIX = "\\\\?\\"` | Misworded: already a named constant; an OS path-syntax prefix is not a closed domain |
| `paths.py:232`, `paths.py:241`, `scaling.py:188` | `sys.platform != "win32"` / `== "win32"` | **Genuine.** A closed domain compared against raw strings in three places. Fixed by the cross-cutting `PlatformName` enum plus `current_platform()` in `types.py`; all three sites now compare enum members. `Status: RECOVERED, CORRECTLY_FIXED, VERIFIED` |
| `types.py:78` | `NumericSign = NewType("NumericSign", str)` | **Genuine.** A two-value closed domain (`"-"`, `""`) modelled as free-form string and consumed by string concatenation. Fixed by a two-member `StrEnum`; `canonical_number_token` now renders the sign explicitly from the member instead of appending an empty string. `Status: RECOVERED, CORRECTLY_FIXED, VERIFIED` |
| `config.py:106` | `endpoint_band_count != 1` | Not an enum. See template 1 |

## Independent genuine defects found while auditing (not marker-driven)

| Defect | Location | Fix |
|---|---|---|
| Duplicated governed tolerance `1e-12` repeated verbatim in two validators | `config.py:133,196` | Extracted to `_EXACT_AGREEMENT_RELATIVE_TOLERANCE` / `_EXACT_AGREEMENT_ABSOLUTE_TOLERANCE` |
| Hardcoded duplicated governed value `0.01` used to identify the principal anytime coverage stress cell, duplicating the authoritative configured `rho_offset` | `publication_rows.py:964` | Replaced with the authoritative `CoverageStressCaseConfig` resolved by `_principal_coverage_stress_case()`; the coincidental use of `config.method.finest_bands` was replaced by the case's own `band_count` |
| Unit conversion factor `1000.0` hardcoded at 7 sites although `UnitsConfig.nanoseconds_per_millisecond` already owns the unit relationship | `publication_rows.py` | Routed through `_runtime_milliseconds()` |

An earlier revision of this document claimed a discarded boolean in
`plan.py:_population_rho_values`. That claim was checked against `HEAD` and is **false** —
the comparison result is consumed by `if any(...)` and the function is correct. The claim
was removed rather than carried forward.

## Accounting

| Class | Count |
|---|---|
| Markers reconstructed | 213 |
| Markers resolved by a real code change | 5 (the `PlatformName` trio, `NumericSign`, and the `FailureBoundaryProbe` cluster) plus 4 independent defects |
| Markers removed as justified false positives | 208 |
| Markers remaining in production source | **0** |
| Markers parked in `unresolved.md` | 0 |

Every one of the 213 pre-change markers is accounted for. Zero markers is not the success
condition — the resolution of each one is.
