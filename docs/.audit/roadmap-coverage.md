# Roadmap coverage audit

The 29 authoritative experiment families are represented once in the catalog and
expand to 1,738 currently executable prospective cells. `trajcert plan` verified
the count without executing any scientific cell. The per-family expansion is:

| Family | Cells |
|---|---:|
| Legacy Partition Incoherence Check | 6 |
| Path Information Decomposition | 48 |
| Information Profile Convexity | 48 |
| Minimum Compatibility Identity | 48 |
| Sharp-Set Constructive Identity | 192 |
| Refinement Dominance Identity | 36 |
| Strict Timing-Gain Identity | 18 |
| Safety Boundary Identity | 60 |
| Endpoint Special-Case Identity | 12 |
| Anytime Projection Proof Check | 1 |
| Population Complexity Proof Check | 1 |
| Production Solver vs Independent Oracle | 240 |
| Callback Comparator Reduction | 12 |
| Generic Comparator Reduction | 12 |
| Partition Coherence | 54 |
| Same Endpoint, Different Timing | 24 |
| Strict Timing Gain | 18 |
| Compatibility Floor Behavior | 24 |
| Sharpness Against Generic Oracle | 40 |
| Safety and Intrinsic Impossibility | 40 |
| Anytime Implementation Hand Cases | 30 |
| Anytime Coverage Stress | 12 |
| Population Sensitivity Utility | 360 |
| Sequential Sensitivity Utility | 18 |
| Failure Boundary Atlas | 63 |
| Real-Trajectory Validation | 72 |
| Foreign-Information Negative Control | 240 |
| Computational Scaling | 8 |
| Statistical Synthesis | 1 |
| **Total** | **1,738** |

The catalog validates exact `ExperimentName` coverage; the dispatch mapping validates
exact direct-handler coverage; and the plan, experiment, mathematical, statistical,
reporting, and integration tests supply prospective evidence without scientific runs.
The audit corrected the roadmap's stale Same Endpoint, Different Timing references
from 20 to 24 cells and its stale 1,422 total to 1,738.

## Prospective registry-to-leaf wiring

Every catalog entry has one typed execution handler. The execution dispatch mapping
has import-time exact-set validation for all direct handlers; real trajectory and
synthesis use their explicitly separate workspace-aware executor paths. This is the
prospective CLI-to-leaf route for every entry and was inspected without calling
`run`.

| Experiment | Handler | Route class |
|---|---|---|
| Legacy Partition Incoherence Check | `legacy_partition_incoherence` | direct typed dispatch |
| Path Information Decomposition | `summary_path_information` | summary typed dispatch |
| Information Profile Convexity | `summary_information_profile` | summary typed dispatch |
| Minimum Compatibility Identity | `summary_minimum_compatibility` | summary typed dispatch |
| Sharp-Set Constructive Identity | `summary_sharp_set` | summary typed dispatch |
| Refinement Dominance Identity | `refinement_dominance` | direct typed dispatch |
| Strict Timing-Gain Identity | `strict_timing_identity` | direct typed dispatch |
| Safety-Boundary Identity | `safety_boundary` | summary typed dispatch |
| Endpoint Special-Case Identity | `summary_endpoint` | summary typed dispatch |
| Anytime Projection Proof Check | `anytime_projection_proof` | cell-independent typed dispatch |
| Population Complexity Proof Check | `population_complexity_proof` | cell-independent typed dispatch |
| Production Solver vs Independent Oracle | `summary_solver_oracle` | summary typed dispatch |
| Callback-Model Reduction Falsification | `summary_comparator_reduction` | summary typed dispatch |
| Generic Information-Optimization Reduction | `summary_comparator_reduction` | summary typed dispatch |
| Partition Coherence | `partition_coherence` | direct typed dispatch |
| Same Endpoint, Different Timing | `same_endpoint_timing` | direct typed dispatch |
| Strict Timing Gain | `strict_timing_gain` | direct typed dispatch |
| Compatibility Floor Behavior | `summary_compatibility_floor` | summary typed dispatch |
| Sharpness Against Generic Oracle | `sharpness` | direct typed dispatch |
| Safety and Intrinsic Impossibility | `safety_intrinsic` | direct typed dispatch |
| Anytime Implementation Hand Cases | `anytime_hand_case` | direct typed dispatch |
| Anytime Coverage Stress | `coverage_stress` | direct typed dispatch |
| Population Sensitivity Utility | `population_utility` | direct typed dispatch |
| Sequential Sensitivity Utility | `sequential_utility` | direct typed dispatch |
| Failure Boundary Atlas | `failure_boundary` | direct typed dispatch |
| Real-Trajectory Validation | `real_trajectory_validation` | workspace-aware dispatch |
| Foreign-Information Negative Control | `foreign_information_negative_control` | summary typed dispatch |
| Computational Scaling | `computational_scaling` | direct typed dispatch |
| Statistical Synthesis | `synthesis` | workspace-aware executor |

## Prospective static handler closures

The following counts are static callable closures rooted at each resolved handler
(including functions bound into `partial` handlers). They intentionally exclude the
shared runner/atomic result-writing tail; every ordinary handler is reached by
`execute_dispatched_cell`, which writes the semantic scientific-result artifact and
completion/index records, while real trajectory and synthesis use their documented
workspace-aware routes. Dynamic configuration branches can add calls at runtime, so
these counts are lower-bound prospective closures rather than simulated executions.

| Experiment | Callables | Leaves | Depth | Scientific subsystems |
|---|---:|---:|---:|---|
| Legacy Partition Incoherence Check | 14 | 8 | 5 | comparators, data, experiments |
| Path Information Decomposition | 24 | 10 | 5 | data, experiments, math |
| Information Profile Convexity | 27 | 10 | 6 | data, experiments, math |
| Minimum Compatibility Identity | 26 | 9 | 5 | data, experiments, math |
| Sharp-Set Constructive Identity | 49 | 15 | 7 | data, experiments, math |
| Refinement Dominance Identity | 28 | 9 | 6 | data, experiments, math |
| Strict Timing-Gain Identity | 41 | 13 | 8 | data, experiments, math |
| Safety-Boundary Identity | 33 | 13 | 7 | data, experiments, math |
| Endpoint Special-Case Identity | 20 | 8 | 5 | data, experiments, math |
| Anytime Projection Proof Check | 2 | 2 | 1 | experiments |
| Population Complexity Proof Check | 2 | 2 | 1 | experiments |
| Production Solver vs Independent Oracle | 49 | 16 | 7 | data, experiments, math |
| Callback-Model Reduction Falsification | 65 | 24 | 10 | comparators, data, experiments, math |
| Generic Information-Optimization Reduction | 65 | 24 | 10 | comparators, data, experiments, math |
| Partition Coherence | 43 | 13 | 7 | data, experiments, math |
| Same Endpoint, Different Timing | 37 | 13 | 8 | data, experiments, math |
| Strict Timing Gain | 43 | 13 | 7 | data, experiments, math |
| Compatibility Floor Behavior | 49 | 16 | 8 | data, experiments, math |
| Sharpness Against Generic Oracle | 48 | 15 | 8 | data, experiments, math |
| Safety and Intrinsic Impossibility | 32 | 13 | 6 | data, experiments, math |
| Anytime Implementation Hand Cases | 8 | 4 | 5 | data, experiments |
| Anytime Coverage Stress | 149 | 50 | 12 | comparators, data, determinism, experiments, inference, math |
| Population Sensitivity Utility | 41 | 16 | 8 | analysis, data, experiments, math |
| Sequential Sensitivity Utility | 127 | 49 | 14 | data, determinism, experiments, inference, math |
| Failure Boundary Atlas | 138 | 51 | 10 | data, experiments, inference, math |
| Real-Trajectory Validation | 64 | 22 | 8 | data, experiments, math, storage |
| Foreign-Information Negative Control | 49 | 16 | 7 | data, experiments, math |
| Computational Scaling | 4 | 1 | 4 | experiments |
| Statistical Synthesis | 173 | 68 | 9 | analysis, data, experiments, math, reporting, storage |
