# Enum audit

## Closed string domains reviewed

| Domain | Current representation | Verdict |
|---|---|---|
| Platform (`sys.platform`) | was raw `"win32"` at 3 sites | **Was STRINGLY_TYPED_DOMAIN** → now `PlatformName` enum via `current_platform()`. Open case preserved by `Platform = PlatformName \| str` |
| Numeric sign | was `NumericSign = NewType(str)` with values `"-"`/`""` | **Was STRINGLY_TYPED_DOMAIN** → now a two-member `StrEnum` |
| Solver tolerance identity | was `ToleranceName = NewType(str)` with exactly two call sites and values `root_atol`/`identity_atol` | **Was STRINGLY_TYPED_DOMAIN** (closed set of two) → now `ToleranceName(StrEnum)` with `ROOT_ABSOLUTE`/`IDENTITY_ABSOLUTE`; both call sites pass members. Error text is unchanged because `StrEnum` renders as its value |
| Telemetry search phase | was `TelemetryPhase = NewType(str)`; three static phases plus two dynamic per-batch phases | **Was PARTIALLY_CLOSED** → the three static phases are now `SearchPhase(StrEnum)` members used at the three projection call sites; the two dynamic batch phases are produced by `batch_phase(BatchPhasePrefix, BatchIndex)` where `BatchPhasePrefix` is itself a `StrEnum`, so no free-form phase string is constructed anywhere. `TelemetryPhase = SearchPhase \| str` retains the genuinely open set for future phases, and the log call sites are `%s`-formatted so the rendered log line is unchanged |
| Failure-boundary axis | `FailureBoundaryAxis(StrEnum)` | Already correct; used as enum end-to-end |
| Failure-boundary probe value | was `FiniteFloat \| PositiveInt` | Not a string domain, but a **DOMAIN_LEAK**; now a union of per-axis domain types |
| Failure-boundary coordinate | `FailureBoundaryCoordinate(DomainModel)` | Now carries one required typed `level` |
| Experiment identity | `ExperimentName(StrEnum)` | Already correct |
| Laws / partitions | `LawKey(StrEnum)` for the closed key; `LawName`/`PartitionName` are generated display text | Correctly distinguished — not a false enum |
| Partition labels | `PartitionLabel(StrEnum)` | Already correct |
| Config files | `ConfigFile(StrEnum)` | Already correct |
| Seed grammar | `SeedMaterialGrammar(StrEnum)` | Already correct |
| Coordinate names/grammar | `CoordinateName`, `CoordinateGrammar`, `PathSyntax`, `WorkspacePathComponent`, leaf enums | Already correct |
| Statuses / regimes | `ScientificState`, `PublicExecutionState`, `NumericStatus`, `CompatibilityRegime`, `SafetyRegime`, `EvidenceClass`, `ReasonCode` | Already correct |
| Real-trajectory strata / exclusions / devices | `RealTrajectoryStratumKind`, `RealTrajectoryExclusionReason`, `HitlIotDeviceType`, `AnnotatorExpertise`, `RealTrajectoryDatasetName` | Already correct |
| Comparators | `ComparatorObservationAccess`, `ComparatorAssumption` | Already correct |
| Telemetry logger/fallback labels | `TelemetryLoggerName`, `TelemetryFallbackLabel` | Already correct |
| Dataset contract fields | `DatasetColumnName`, `DatasetFilename`, `DatasetVersionTag`, `DatasetChecksumHex` | Correctly **not** enums — open values from the external release |

## Raw string comparison sweep

`grep -rnE '(==|!=)\s*"[^"]*"' src/` after remediation returns only three hits, all in
`paths.py` and all legitimate:

| Site | Text | Verdict |
|---|---|---|
| `paths.py` decimal-digit processing | `lstrip("0")`, `rstrip("0")`, `== "0"` | `LEGITIMATE_GENERAL_PURPOSE_CODE` — digit-string arithmetic |
| `provenance.py:89` | `numeric < 0.0` | Numeric comparison, not a string |

No `if mode == "…"`, `if status == "…"`, `if dataset == "…"`, `if strategy == "…"`,
`if policy == "…"`, `if objective == "…"`, `if experiment == "…"`, or `if split == "…"`
pattern remains anywhere in production source. `grep -rn 'case "' src/` returns nothing
(no string-literal `match`/`case` arms).

## Enum propagation

The two enums introduced are propagated as enum instances internally:

* `current_platform()` returns a `PlatformName` member; `paths.long_path_safe`,
  `paths.fsync_directory` and `scaling._peak_resident_set_mib` all compare against
  `PlatformName.WIN32` with `is`. No `.value` unwrapping, no `str(...)` round trip, and no
  `PlatformName(x)` re-parsing at any internal call site.
* `NumericSign` members are compared with `is` in `canonical_number_token` and produced by
  `_parsed_coefficient`; no string intermediate is used internally. `paths.py` is
  `LEGITIMATE_BOUNDARY`-free of `.value`.

`tools/source_audit.py` `RULE_REDUNDANT_CONVERSION` (which flags `str(<enum>.value)` and
bare `enum.value` comparisons) reports zero findings across `src/trajcert`.
