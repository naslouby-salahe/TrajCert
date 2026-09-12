# TODO remediation inventory

Status legend: `DISCOVERED -> ANALYZED -> IN_PROGRESS -> IMPLEMENTED -> REVIEWED -> VERIFIED`.

Initial scan command (run before source edits):

```sh
rg -n -i --glob '!docs/todo-remediation-tmp/**' --glob '!*.pyc' \
  '(TODO|FIXME|HACK|XXX|not implemented|unfinished|placeholder)' src/trajcert
```

The scan reported 226 markers. The exact source locations are deliberately retained in
the source-level pre-edit scan above and are reconciled by file/range below; no tests,
generated files, or the remediation ledger are task targets.

| Files / original lines | Markers | Surrounding area | Category and root cause | Required action | Status |
|---|---:|---|---|---|---|
| `types.py:12-37,148,152,371-375` | 28 | central semantic types | dynamic identifiers, rendered text, tabular scalars, and dataset schema tokens were incorrectly treated as closed enums or forbidden primitives | centralised provenance/storage aliases here; documented the open-domain `NewType` policy; retained only genuine serialization scalar boundaries | VERIFIED |
| `constants.py:12-13` | 2 | endpoint partition labels | fixed partition/category labels were raw strings used by partition construction | introduced `PartitionLabel` and migrated constants/callers | VERIFIED |
| `constants.py:20-22` | 3 | repository configuration paths | production and override filenames are a closed repository domain | introduced `ConfigFile`; retain `Path` values at the filesystem boundary | VERIFIED |
| `constants.py:8-9` | 2 | deterministic seed serialization | seed prefix and separator are fixed grammar tokens, not namespaces | introduced `SeedMaterialGrammar`; verified namespace derivation consumers | VERIFIED |
| `constants.py:18` | 1 | information roundoff control | a numerical tolerance was global despite being a configurable numerical policy | added validated `NumericsConfig.information_roundoff_ulps` and migrated the information guard | VERIFIED |
| `constants.py:17` | 1 | safety-boundary control | resolved-harm margin was global despite defining a numerical policy | added validated `NumericsConfig.resolved_harm_boundary_offset` and migrated safety cases | VERIFIED |
| `constants.py:19,24-31` | 9 | projection search policy | root scan, incumbent bisection, and stall thresholds were split global controls for one solver policy | added `NumericsConfig.arb_search` and migrated each projection phase | VERIFIED |
| `constants.py:10-11,14-16` | 4 | mathematical and deterministic constants | distinguish invariants from tunable configuration and serialization grammar | endpoint band count now belongs to validated `MethodConfig`; remaining values are mathematical invariants or enum grammar | VERIFIED |
| `paths.py:24-33,215-217,313-340` | 16 | artifact naming/path construction | generated slugs/tokens are dynamic values, while path roots, fixed subdirectories, and serialization grammar are closed domains | moved generated aliases to `types.py`; introduced `WorkspacePathComponent` and `PathSyntax`; reviewed all source/test callers | VERIFIED |
| `data/real_trajectories.py:37-135,267-328` | 94 | HITL-IoT ingest and eligibility | pinned dataset contract belongs in configuration; CSV field names must be typed contract values at data boundary | dataset contract is validated configuration and ingest consumes it with typed columns end-to-end | VERIFIED |
| `config.py:78-82,788,818,855` | 6 | YAML parsing/override merge | YAML is an external primitive serialization boundary; fields require named keys rather than enum conversion | parser/coercion/validation chain reviewed and verified; raw values do not cross into domain workflows | VERIFIED |
| `storage.py:173` | 1 | canonical JSON serialization | raw object mapping leaked through a serialization boundary | introduced central `JsonObject` alias and applied it to canonical object serialization | VERIFIED |
| `storage.py:24-29` | 6 | persistence identities/digests | cryptographic and generated identifiers are dynamic strings, not enums | moved each semantically distinct identity/digest alias to `types.py`; persistence models retain typed fields | VERIFIED |
| `provenance.py:61-70,142-144,281-282` | 14 | provenance coordinate formatting | generated display/identity values are dynamic; coordinate labels are a closed internal domain | moved open identity/display aliases to `types.py`; introduced closed `CoordinateName` and reused `CoordinateGrammar` for generated tokens | VERIFIED |
| `skeleton.py:24-59` | 18 | output directory skeleton | duplicated closed path leaves and `.gitkeep` filename | reused path enums and added the missing skeleton leaf/file vocabulary | VERIFIED |
| `experiments/plan.py:419`; `dispatch.py:620` | 2 | real-trajectory variant grammar | pooled was a raw member of the existing stratum domain | migrated to `RealTrajectoryStratumKind.POOLED` | VERIFIED |
| `experiments/models.py:28-29` | 2 | persisted execution failures | exception names and tracebacks are dynamic diagnostics, not closed enums; flat fields obscured their shared record boundary | introduced `FailureDiagnostic` with semantic central aliases and migrated runner/status/resume callers | VERIFIED |
| `experiments/anytime.py:878,1416` | 2 | generated experiment labels | `type(parameters.name)` concealed the actual law-name contract; hand-case identity duplicated existing grammar | use `LawName` directly and centralize `CoordinateGrammar` in `types.py` to avoid the resulting cycle | VERIFIED |
| `reporting/export.py:65,104,311` | 3 | report export/reproducibility | lock authority and staged results root were raw fixed tokens | `DependencyAuthority` is now a closed enum, and staging derives from `RESULTS_ROOT`; callers/tests reviewed | VERIFIED |
| `reporting/tables.py:42-43,134` | 3 | tabular rendering | extensions were raw fixed tokens; TeX escaping processes arbitrary presentation text | derive suffixes from `PublicationExtension`; retain the explicit text-output boundary | VERIFIED |
| `reporting/publication_rows.py:100-102` | 3 | publication-row semantics | theorem and method names are generated display values; a generic regime alias incorrectly erased the distinction between compatibility and safety regimes | moved generated names to central types and replaced `RegimeName` with `CompatibilityRegime | SafetyRegime` | VERIFIED |
| `reporting/figures.py:616,620`; `publication_rows.py:790` | 3 | presentation/rendering boundaries | title rendering and evidence-family diagnostics lacked distinct contracts | introduced `FigureTitle` for dynamic titles and `EvidenceFamilyLabel` for the closed validation family | VERIFIED |
| `telemetry.py:27,29` | 2 | logger labels | logger identity and missing-cell fallback are closed choices; phases/labels themselves remain dynamic because batch labels include coordinates | introduced `TelemetryLoggerName` and `TelemetryFallbackLabel`; reviewed callers | VERIFIED |

Affected usages were located with repository-wide searches for each existing type and enum
class before edits. `types.py` already contains the relevant domain aliases, numeric
constraints, dataset/trajectory enums, execution enums, and `DomainModel` boundary.
