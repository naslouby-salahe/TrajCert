# Type audit

`types.py` inventory was reviewed before this audit's change. It owns open semantic
aliases (`ClientId`, `DatasetColumnName`, digests, display text), constrained numeric
types (`BandCount`, `AgeUnit`, `Probability`, `RoundoffUlpCount`), domain models, and
cross-cutting enums.

| Type / family | Meaning | Underlying type | Validity / action |
|---|---|---|---|
| `ClientId`, dataset names/columns/files, digests, slugs | External or generated identifiers | `NewType(str)` | Valid: open vocabularies, retained as distinct contracts. |
| Numeric aliases | Scientific values and counts | constrained strict numeric | Valid: reused for dataset/event/config contracts. |
| `ConfigFile`, `SeedMaterialGrammar`, `PartitionLabel` | Closed cross-cutting vocabularies | `StrEnum` | Valid: centralized in `types.py`; old seed-constant forwarding layer removed. |
| YAML/JSON/table cells | Parser/serializer boundary data | unions/mappings | Valid only at the named external boundary; does not enter workflow contracts. |
| `FailureDiagnostic` | Related diagnostic data | `DomainModel` | Valid structured record; replaced three flat values. |

Changed APIs were traced through config → preprocessing → dispatch → real-trajectory
evaluation → reporting. The only direct primitive conversions in the altered ingest
path are gone; Polars values enter Pydantic's typed event model directly.

## Corrective follow-up

The first static check found that the prior relocation of cross-cutting aliases to
`types.py` had not been propagated to every consumer: production and test modules
still imported aliases from `storage` and `provenance`. Those imports were changed to
the true owner (`types.py`) without adding re-exports or compatibility shims. The
post-fix configured type check reports zero errors.

Static checking caught and this audit corrected a partial title migration: rendering
helpers accept `FigureTitle | FigureLabel`, preserving both generated and closed title
domains without string conversion.
