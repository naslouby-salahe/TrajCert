# Wiring audit

## CLI → leaf traces

| Workflow | Entry point | Chain reviewed | Leaf operations | Finding |
|---|---|---|---|---|
| Experiment run | `cli.main` → `workflows.run_experiment` | plan → runner → dispatch → per-experiment handler | scientific cell evaluators | No alternative forwarding path. `dispatch._EXECUTION_DISPATCH` is asserted at import to cover every `ExecutionHandler` exactly once |
| Failure boundary (refactored) | `plan._failure_boundary_coordinates` → `SemanticCoordinates.failure_boundary_axis_and_level` | `dispatch._execute_failure_boundary` → `_failure_boundary_probe` / `_node_budget_level` → `evaluate_failure_boundary` / `evaluate_optimizer_node_budget` / `evaluate_terminal_selection_asymmetry` → `_population_coordinate` + axis narrowing helpers → `sharp_risk_set` | risk-set solve, information point | Fully wired. Graphify confirms all five outgoing call edges, including the new `_node_budget_level` |
| Real trajectory | preprocessing command | `workflows._preprocess_real_trajectory` → integrity/schema/eligibility → persisted cohort → dispatch cache → `evaluate_real_trajectory_cell` | empirical summary/oracle | Fully wired; the dataset contract is read at preprocessing and planning through active config |
| Publication reporting | `report` CLI action | `publication_rows.build_publication_source_rows` → `_anytime_path_rows` / `_coverage_rows` / `_scaling_rows` → `read_verified_scientific_result` | table/figure renderers, CSV/TeX/SVG writers | Fully wired. `_runtime_milliseconds` and `_principal_coverage_stress_case` are each reached from the row builders and replace duplicated inline logic |
| Smoke | `smoke` CLI action | `workflows` → `experiments.smoke` | confidence/projection smoke checks | Unchanged |

## Counts

* Distinct production modules participating in the four traced workflows: all 80 modules
  under `src/trajcert` are reachable from `cli.main` plus the package entry (`__init__`).
* Reachable callables per workflow were not counted mechanically (the AST extractor does
  not distinguish `calls` from `references`); instead the orphan query in
  `graphify-audit.md` was used, which is a stronger test: **0 production callables or
  classes have zero inbound links**.

## Suspicious isolated methods

None. Category counts:

| Classification | Count |
|---|---|
| `TRULY_DEAD` | 0 |
| `MISSING_WIRING` | 0 |
| `TEST_ONLY` | 0 (all production symbols are reachable from production code) |
| `BOUNDARY_ENTRYPOINT` | `cli.main`, `noxfile` sessions, `tools.source_audit.main` — retained |
| `REFLECTION_OR_FRAMEWORK_ENTRYPOINT` | Pydantic `model_validator`/`field_validator`/`field_serializer` methods and `@property` accessors — retained as extractor false positives |
| `FALSE_POSITIVE` | module-file nodes; numerical-library endpoints |

## Unnecessary layers

None introduced. The refactor **removed** a layer rather than adding one:
`dispatch._failure_boundary_probe` went from a four-branch option-null unwrapper to
`return coordinate.level`, and the four mutually exclusive optional coordinate fields
collapsed into one required typed field.
