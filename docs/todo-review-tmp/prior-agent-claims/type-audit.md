# Type and alias audit

## `types.py` inventory (taken before any alias change)

`types.py` (551 lines at `HEAD`) is the designated home for cross-cutting domain types and
is exempt from the primitive-annotation rule by design (`tools/source_audit.py:239`). It
holds 55 `NewType`/`Annotated` contracts, ~40 `StrEnum`/`IntEnum` closed domains,
constrained numeric building blocks (`UnitFloat`, `OpenUnitFloat`, `PositiveInt`,
`NonNegativeInt`, `FiniteFloat`, …), the `DomainModel` base, and `Vector`.

Every one of the 55 aliases was checked for real usage across `src/` and `tests/`:

| Type / family | Example members | Underlying | Usages | Valid? | Action |
|---|---|---|---|---|---|
| External/open identifiers | `ClientId`, `DatasetColumnName`, `ArtifactKey`, `EventId`, `EpochId`, `ActionChannelId` | `NewType(str)` | 6–82 each | Yes — open vocabularies from data/input | Retained |
| Generated digests | `DigestHex`, `PlanDigest`, `EnvironmentDigest`, `SpecificationDigest`, `SourceIdentityDigest`, `DependencyFingerprint`, `DatasetChecksumHex` | `NewType(str)` | 9–73 each | Yes — digests of differing provenance, already distinct contracts | Retained |
| Generated display/presentation text | `FigureTitle`, `ComparisonPairDisplay`, `FailureBoundaryCoordinateDisplay`, `FailureBoundaryLevel`, `SvgFragment`, `FacetLabel`, `MethodDisplayName` | `NewType(str)` | 1–13 each | Yes — rendering output, not domain identity | Retained |
| Diagnostics | `FailureMessage`, `ExceptionClassName`, `TracebackText`, `TelemetryLabel` | `NewType(str)` | 5–31 each | Yes — free text; this is the only family for which the boilerplate's "proper error type or message class" reading is even coherent, and a message record would add no invariant these aliases do not already carry | Retained |
| Generated/open coordinate text | `CoordinateToken`, `VariantName`, `SemanticCellKey`, `SemanticComparisonKey`, `ExperimentSlug`, `PartitionName`, `LawName`, `MethodName`, `NamedComparison`, `BaselineName` | `NewType(str)` | 4–148 each | Yes — generated or open text. `LawName`/`PartitionName` are generated display names; the closed axes are `LawKey`/`PartitionLabel` | Retained |
| Numeric scalar contracts | `BandCount`, `EventCount`, `Count`, `Probability`, `Mass`, `RiskValue`, `InformationNats`, `RiskOffset`, `TimingContrast`, `OuterMaxNodes`, … | `Annotated[StrictFloat/StrictInt, Field(...)]` | many | Yes — constrained numeric contracts; these are exactly the values the old probe union should have named | **Reused** in `FailureBoundaryProbe` |
| Parser/serializer + text-processing values | `ConfigFieldPath`, `SerializedConfigJson`, `CliArgumentValue`, `ColumnName`, `DecimalCoefficient`, `DecimalDigits` | `NewType(str)` | 6–39 each | Yes — named external boundaries | Retained |
| `FailureBoundaryProbe` | — | was `FiniteFloat \| PositiveInt` | 8 | **No** — an untyped union of generic primitives whose meaning depends on the axis | **Replaced** with a union of per-axis domain types |
| `NumericSign` | — | was `NewType(str)` | 5 | **No** — a two-value closed domain modelled as free text | **Replaced** with a `StrEnum` |

Conclusion: no alias was semantically invalid, duplicated, or unused. No alias was deleted,
no alias was repurposed across concepts because two concepts happened to share a primitive,
and no new alias was invented except where a real closed domain existed.

## Added enums

| Enum | Members | Justification |
|---|---|---|
| `PlatformName(StrEnum)` | `WIN32`, `LINUX`, `DARWIN` | Replaces three raw `sys.platform == "win32"` comparisons. `Platform = PlatformName \| str` plus `current_platform()` also models the genuine open case: the runtime may report a platform outside the enumerated set, and `current_platform()` returns the raw string then. No invalid assumption is baked in and no current call path changes behaviour |
| `NumericSign(StrEnum)` | `NEGATIVE = "-"`, `NON_NEGATIVE = ""` | Replaces free-form string consumed by concatenation; the two values are exhaustive by construction |

## Primitive leak sweep of changed code

| Pattern | Occurrences | Verdict |
|---|---|---|
| `int(level)`, `float(level)`, `str(level)` coercion of a domain probe | 6 (before) → **0** | `DOMAIN_LEAK` — fixed by the probe refactor |
| `int(value_text)` / `float(value_text)` in `_failure_boundary_from_parts` | 6 | `LEGITIMATE_BOUNDARY` — parsing a serialized coordinate display string back into a validated `DomainModel`; the model re-validates to the per-axis aliases. Kept local and immediate |
| `cast(...)` across `src/` | 14 | All `LEGITIMATE_BOUNDARY`: `yaml.safe_load`, `model_dump(mode="json")`, Polars `to_pylist` cell typing, `psutil` attribute widening, multiprocessing `recv()`, argparse `getattr`. None bridges an internal type mismatch |
| `.value` across `src/` | 3 | All legitimate: `model_dump().values()` ×2, `LAW_DISPLAY_NAMES.values()`. **No** enum `.value` unwrapping remains (`source_audit` `RULE_REDUNDANT_CONVERSION` clean) |
| bare primitive function returns | 20 | Predicates (`-> bool`) and text/formatting helpers (`_canonical_json`, `_format_tex_value`, `_escape_tex`). No domain-identity return is a raw primitive |
| semgrep `TC-PRIMITIVE-001/002` | 0 findings | clean |

## Why the architecture test did not catch the defect

The removed boilerplate asked explicitly why `tests/architecture/test_primitive_leaks.py`
did not catch this. Established by reading `tools/source_audit.py`:

1. `_check_primitive_leak` returns immediately when `path.name == "types.py"` (line 239),
   so none of the 55 `types.py` alias declarations is ever examined.
2. For any other annotation it flags only a name matching `_LEAKED_PRIMITIVE_PATTERN`
   (`int|float|str|Any|object`). An annotation spelled with a *project alias*
   (`FailureBoundaryProbe`, `FiniteFloat`) contains none of those tokens and is not a
   building-block name (`PositiveInt`, `StrictFloat`, …), so it passed silently.
3. `_check_annotation` over `DOMAIN_PARAMETER_NAMES` fires only when the annotation text is
   literally `str`/`int`/`float`; `FailureBoundaryProbe` is not.

So the union-of-primitives construct escaped both rules. This is recorded as a scanner
limitation and was **not** "fixed" by weakening anything. Extending the scanner would have
been a redesign of the enforcement surface beyond this remediation's scope; the defect it
hid is fixed at the source, so no rule currently passes vacuously on this construct.
