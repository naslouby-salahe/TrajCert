# Call-graph audit

The latest independent AST/Graphify extraction was performed on 2026-09-25 with
Graphify 0.9.64 using `graphify extract src/trajcert --out
/tmp/trajcert-graphify-post-final --no-cluster`. It recorded 79 code files, 1,738
nodes, and 7,920 edges. These raw node/edge counts are not directly comparable to the
prior saved extractor output because the installed Graphify version changed.

## Public command closures

The static dispatcher has direct `calls` edges to all seven public workflow roots:
`doctor`, `preprocess`, `plan_view`, `smoke`, `run_experiment`,
`experiment_status`, and `report`. Command behavior was exercised without any
scientific `run` execution:

The final source AST has 854 runtime production callables: 754 functions and 100
class methods. Ten `typing.overload` declaration stubs are excluded from that runtime
count. Runtime profiling of the six allowed commands reached 360 unique production
callables in union. Graphify flags 192 callables without a static incoming `calls`
edge; source review classifies them as typed-registry targets, Pydantic hooks or
properties, callbacks/partials, multiprocessing targets, telemetry hooks, or
publication renderers. Thus the final counts are 360 directly observed
CLI-reachable callables, 192 dynamic/framework-reachability candidates, zero
unexplained unreachable callables, and zero confirmed-dead callables.

| Command | Observed contract |
|---|---|
| `doctor` | Passed read-only prerequisites and dependency-lock validation. |
| `preprocess` | Materialized/reused synthetic manifests and the pinned real-data inventory/cohort. |
| `plan` | Expanded 1,738 executable cells across 29 experiment families. |
| `smoke` | Passed all 6 permitted smoke fixtures. |
| `status` | Reported 0 completed, 0 failed, 29 blocked, and 0 running families. |
| `report` | Refused incomplete evidence with declared exit code 30. |

## Measured command closure statistics

These are runtime-profiled counts from the final worktree. A terminal leaf is a
profiled TrajCert callable with no profiled TrajCert child in that command's call
tree. Each safe command has one direct workflow branch from `_dispatch`; parsing
and output helpers account for the three direct callees of `cli.main`.

| Command | Direct workflow branches | Unique transitive callables | Terminal leaves | Maximum in-repository depth | Unresolved branch |
|---|---:|---:|---:|---:|---|
| `doctor` | 1 | 181 | 71 | 21 | None |
| `preprocess` | 1 | 72 | 38 | 21 | None; reused validated current inventory |
| `plan` | 1 | 153 | 54 | 21 | None |
| `smoke` | 1 | 170 | 77 | 16 | None |
| `status` | 1 | 210 | 78 | 31 | None |
| `report` | 1 | 168 | 60 | 23 | Expected pre-experiment evidence refusal |
| `run` | 1 prospective | Not executed | Not executed | Prospective only | Deliberately not executed by audit constraint |

The maximum observed CLI-to-leaf depth is 31 (`status`). `run` and each of the 29
experiment families remain prospectively wired through `run_experiment` →
`execute_dispatched_cell` → `execute_scientific_cell` → catalog-selected typed
handler. The catalog and dispatch exact-coverage guards prevent a disconnected
experiment family without executing a scientific cell.

## Method-by-method workflow traces

```text
doctor
  cli.main → parse_args → _dispatch → workflows.doctor
    → _load_config → build_plan → validate_results_layout → final DoctorResult

preprocess
  cli.main → parse_args → _dispatch → workflows.preprocess
    → _load_config → synthetic inventory currentness check
    → prepared_synthetic_law / atomic_write_model (cache-miss branch)
    → final preprocessing inventory; real-name branch additionally verifies source,
      inventories observed structure, validates schema, builds eligibility, and writes cohort

plan
  cli.main → parse_args → _dispatch → workflows.plan_view
    → _load_config → build_plan → catalog coordinate handlers → ExperimentPlan validation

smoke
  cli.main → parse_args → _dispatch → workflows.smoke
    → _load_config → run_smoke_fixtures → confidence/projection fixture leaves → SmokeResult

status
  cli.main → parse_args → _dispatch → workflows.experiment_status
    → _load_config → build_plan → inspect_cell_status → aggregate_experiment_status

report
  cli.main → parse_args → _dispatch → workflows.report
    → _load_config → report export/verified completion gate
    → InvalidScientificDataError for missing pre-experiment evidence (exit 30)

run (prospective only)
  cli.main → parse_args → _dispatch → workflows.run_experiment → build_plan
    → runner.execute_dispatched_cell → dispatch.execute_scientific_cell
    → execution_handler_for → _EXECUTION_DISPATCH handler → scientific leaf/artifact writer
```

## Dynamic closure reconciliation

The latest static incoming-call analysis flags 192 production callable candidates. They are not
treated as dead code solely on that signal: Graphify does not model enum-keyed
registries, Pydantic validation hooks, properties, multiprocessing targets, or
callback/partial invocation. Source review reconciled the material workflow groups:

- `EXPERIMENT_CATALOG` registers every `ExperimentName` exactly once.
- `build_plan` expands that authoritative catalog, and its coordinate handlers are
  catalog-selected rather than statically called.
- `execute_scientific_cell` resolves the catalog handler, then invokes the typed
  `_EXECUTION_DISPATCH` mapping. Import-time set equality verifies all direct
  `ExecutionHandler` values occur exactly once; synthesis and real-trajectory
  handlers are separately workspace-aware.
- Pydantic model validators/properties, telemetry callbacks, figure/table renderers,
  multiprocessing workers, and callback objectives account for the remaining
  framework-mediated candidates.

No candidate was deleted on the basis of static reachability alone. The catalog and
dispatch set-equality invariants, plan tests, CLI contract tests, smoke fixture, and
full test suite provide the reachability evidence for the prospective workflows.

## Graph integrity qualification

`graphify diagnose multigraph` on the current raw graph reports 1,860 post-build nodes,
7,920 raw edges, 720 dangling endpoints, two self loops, and zero exact duplicate edges.
These are
extractor graph-normalization diagnostics, not application dangling imports: the
quality suite's import-contract checks and all runtime command checks passed. They
are retained as Graphify limitations rather than hidden or interpreted as production
dead-code findings.
