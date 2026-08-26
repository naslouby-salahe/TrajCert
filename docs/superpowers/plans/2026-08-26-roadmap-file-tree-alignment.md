# Roadmap File-Tree Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Adaptation note:** This is a structural migration (merge/rename existing modules), not new-feature TDD. Each task's "test" step is "run the existing test suite + quality gates for the affected area," not a newly written unit test, since behavior must stay identical — only file layout changes. Every task still ends in a commit.

**Goal:** Make `src/trajcert/`, `tests/`, and the `results/project_summary` artifact-class contract match `docs/TrajCert_Roadmap.md` §10 file-for-file, with zero behavior change.

**Architecture:** The roadmap (`docs/TrajCert_Roadmap.md` §10) is the authoritative file tree. Where the current implementation has split a roadmap-named file's responsibility across several files, all of that content is merged verbatim (functions/classes concatenated, internal cross-references rewritten to local calls, external imports updated) into the single roadmap-named file. No public behavior, CLI contract, or scientific logic changes — this is pure code motion plus the accompanying import/test updates.

**Tech Stack:** Python 3.12, pydantic, ruff, basedpyright (`typeCheckingMode = "all"`), pytest, nox.

**Ground rules for every task below:**
- No comments, no docstrings added anywhere (repo convention — see `CLAUDE.md` §5 Code Hygiene).
- After each merge, delete the old source file(s) entirely — no re-export shims, no compatibility aliases (`CLAUDE.md` forbids this).
- After each merge, `grep -rn` the old module path across `src/` and `tests/` to catch every import site before running tests.
- Run `uv run ruff format <touched files>`, `uv run ruff check <touched files>`, `uv run basedpyright <touched files>`, then the relevant `pytest` slice, before committing.
- Commit message format: `refactor(<area>): merge <old files> into <target>`.

---

## Assumptions (flagged per your review — proceed unless corrected)

1. **`experiments/smoke.py`** has no entry in the roadmap tree. Its content (the `SmokeResult` model and the six deterministic smoke-fixture executors backing `trajcert smoke`, §16.1) is orchestration-level CLI-command backing, so it folds into **`experiments/runner.py`** alongside the other orchestration modules (Task 3), not into `anytime.py`.
2. **`experiments/dependencies.py`** (specification/dependency digests, import-closure scanning) implements the reuse/invalidation machinery described in roadmap §14 ("Semantic Identity, Dependency Reuse, Invalidation, and Recovery"), which is `runner.py`'s stated responsibility ("orchestration, resume, overwrite and failure handling") — folds into `runner.py` (Task 3).
3. The file-tree comment `# Public Typer CLI` next to `cli.py` is treated as descriptive flavor text, not a mandate to switch the working `argparse`-based CLI to Typer — §16 (Public CLI) only specifies the command/flag/exit-code contract, which the current CLI already satisfies. **No CLI framework change is in scope.** Flag if this reading is wrong.
4. Test-file mapping (Task 11 onward) places each current test file's cases into the nearest-matching roadmap-named test file by subject matter. Where a current test file's subject has no roadmap-named home (e.g. `test_runtime.py`'s determinism/seed-namespace cases — the roadmap tree has no `test_determinism.py`), those cases fold into the closest thematically-adjacent roadmap file and this is called out in that task explicitly.

---

## Part A — `src/trajcert/experiments/` consolidation

### Task 1: Fold `legacy_incoherence.py` into `mathematics.py`

**Files:**
- Merge from: `src/trajcert/experiments/legacy_incoherence.py` (128 lines)
- Merge into: `src/trajcert/experiments/mathematics.py` (349 lines)
- Update caller: `src/trajcert/experiments/dispatch.py` (`_dispatch_legacy_partition_incoherence` imports `evaluate_legacy_partition_incoherence` from `trajcert.experiments.legacy_incoherence`)
- Update caller: any test importing `trajcert.experiments.legacy_incoherence` (`grep -rn "legacy_incoherence" tests/`)

- [ ] **Step 1: Read both files fully**

Read `src/trajcert/experiments/legacy_incoherence.py` and `src/trajcert/experiments/mathematics.py` end to end to see current top import blocks and existing symbol names (avoid collisions).

- [ ] **Step 2: Append `legacy_incoherence.py`'s classes/functions into `mathematics.py`**

Move `EndpointDifferenceDirection`, `LegacyPartitionIncoherenceResult`, `evaluate_legacy_partition_incoherence`, `_tilted_probability`, `_response_masses` (and any other private helpers in the file) into `mathematics.py`, placed after the existing content. Merge the two files' import blocks (dedupe, alphabetize per existing `mathematics.py` convention), keeping only imports actually used post-merge.

- [ ] **Step 3: Delete `legacy_incoherence.py`**

```bash
git rm src/trajcert/experiments/legacy_incoherence.py
```

- [ ] **Step 4: Fix the import in `dispatch.py`**

Change:
```python
from trajcert.experiments.legacy_incoherence import evaluate_legacy_partition_incoherence
```
to:
```python
from trajcert.experiments.mathematics import evaluate_legacy_partition_incoherence
```
(adjust the existing `from trajcert.experiments.mathematics import (...)` block instead of adding a second import line if one already exists at that point in the file).

- [ ] **Step 5: Fix any test imports**

`grep -rln "legacy_incoherence" tests/` and update each hit to import from `trajcert.experiments.mathematics` instead.

- [ ] **Step 6: Verify**

```bash
uv run ruff format src/trajcert/experiments/mathematics.py src/trajcert/experiments/dispatch.py
uv run ruff check src/trajcert/experiments/mathematics.py src/trajcert/experiments/dispatch.py
uv run basedpyright src/trajcert/experiments/mathematics.py src/trajcert/experiments/dispatch.py
uv run pytest tests/unit/test_comparators.py tests/unit/test_scientific_cell_dispatch.py -q
```
Expected: all pass, no ruff/pyright errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(experiments): merge legacy_incoherence.py into mathematics.py"
```

---

### Task 2: Fold `coverage.py` into `anytime.py`

**Files:**
- Merge from: `src/trajcert/experiments/coverage.py` (354 lines)
- Merge into: `src/trajcert/experiments/anytime.py` (811 lines)
- Update caller: `src/trajcert/experiments/dispatch.py` (`_coverage_stress_case` / the "Anytime Coverage Stress" dispatch entry imports `evaluate_configured_coverage_stress` from `trajcert.experiments.coverage`)
- Update caller: `src/trajcert/reporting/publication_sources.py` (uses `CoverageEvidenceResult`, `CoverageMethodEvidence`, `AnytimePathEvidence` — will itself be merged away in Task 8, but fix the reference now regardless)
- Update caller: any test importing `trajcert.experiments.coverage`

- [ ] **Step 1: Read both files fully, note name collisions**

`coverage.py` already imports several names from `trajcert.experiments.anytime` (`SequentialMethod`, `run_coverage_stress`, `run_sequential_trace`) — after the merge these become plain local references (no import needed). Watch for duplicate top-level constant names (`coverage.py` has `_EXACT_COVERAGE_LEVEL`, `_REPRESENTATIVE_STREAMS` — confirm `anytime.py` has no clashing names).

- [ ] **Step 2: Append `coverage.py`'s content into `anytime.py`**

Move `CoverageMethodEvidence`, `AnytimePathEvidence`, `CoverageEvidenceResult`, `evaluate_configured_coverage_stress`, `_coverage_method_evidence`, `_clopper_pearson_upper`, `_trajcert_trajectory_evidence`, `_true_information`, `_parameters`, `_minimum_information_completion`, `_sensitivity_budget`, `_risk_budget`, `_float_tuple` into `anytime.py`. Drop the now-redundant `from trajcert.experiments.anytime import (...)` line from the old `coverage.py` content — those calls become direct local references. Merge import blocks, dedupe.

- [ ] **Step 3: Delete `coverage.py`**

```bash
git rm src/trajcert/experiments/coverage.py
```

- [ ] **Step 4: Fix imports in `dispatch.py` and `publication_sources.py`**

Change `from trajcert.experiments.coverage import evaluate_configured_coverage_stress` (and any `CoverageEvidenceResult` etc. imports in `publication_sources.py`) to `from trajcert.experiments.anytime import ...`.

- [ ] **Step 5: Fix any test imports**

`grep -rln "experiments.coverage\|experiments\.coverage" tests/` and redirect to `trajcert.experiments.anytime`.

- [ ] **Step 6: Verify**

```bash
uv run ruff format src/trajcert/experiments/anytime.py src/trajcert/experiments/dispatch.py
uv run ruff check src/trajcert/experiments/anytime.py src/trajcert/experiments/dispatch.py
uv run basedpyright src/trajcert/experiments/anytime.py src/trajcert/experiments/dispatch.py
uv run pytest tests/unit/test_scientific_cell_dispatch.py tests/integration/test_experiment_runner.py -q
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(experiments): merge coverage.py into anytime.py"
```

---

### Task 3: Fold `dispatch.py`, `execution.py`, `dependencies.py`, `analysis/locality.py`, `smoke.py` into `runner.py`

This is the largest single consolidation (~1540 lines landing in `runner.py`). Split into sub-steps per source file so a failure in one doesn't blow up the whole task.

**Files:**
- Merge from: `src/trajcert/experiments/dispatch.py`, `src/trajcert/experiments/execution.py`, `src/trajcert/experiments/dependencies.py`, `src/trajcert/analysis/locality.py`, `src/trajcert/experiments/smoke.py`
- Merge into: `src/trajcert/experiments/runner.py`
- Update callers: `src/trajcert/cli.py` (via `operator.py`, itself merged in Task 9 — do this task first, then Task 9 will already see the new locations), `src/trajcert/operator.py`, `src/trajcert/reporting/*.py`, `tests/architecture/test_locality.py`, any test importing `trajcert.experiments.dispatch`, `trajcert.experiments.execution`, `trajcert.experiments.dependencies`, `trajcert.analysis.locality`, `trajcert.experiments.smoke`.

- [ ] **Step 1: Read all six files in full**

`runner.py`, `dispatch.py`, `execution.py`, `dependencies.py`, `analysis/locality.py`, `smoke.py`. Note that `execution.py` calls `dispatch.py`'s `execute_scientific_cell`, and `smoke.py` likely calls into `mathematics.py`/`timing.py`/`inference/projection.py` directly (unaffected by this merge). Confirm no name collisions across the five source files plus `runner.py` (e.g. both `dispatch.py` and `runner.py` may define private helpers with generic names like `_law_from_name` — rename on merge if so, updating all internal call sites within the merged file).

- [ ] **Step 2: Append `dependencies.py` into `runner.py`**

Move `scientific_specification_digest`, `producer_component_digest`, `scientific_dependency_digest`, `cell_dependency_fingerprint`, `expected_seed_count`, `_first_party_import_closure`, `_first_party_imports`, `_non_scientific_module`, `_module_path` (plus the `ast` import and any other new imports) into `runner.py`.

- [ ] **Step 3: Append `analysis/locality.py` into `runner.py`**

Move `ScientificInputClass`, `StaticComponentDependency`, `RuntimeLineageArtifact`, `LocalValidityTarget`, `LocalValidityAuditResult`, `audit_local_validity`, `audit_local_validity_targets`, `static_dependency_audit`, `runtime_lineage_audit` into `runner.py`. Delete `src/trajcert/analysis/locality.py` and remove `src/trajcert/analysis/` from consideration if it becomes otherwise unaffected (it still holds `aggregation.py`, `bootstrap.py`, `materiality.py`, `metrics.py`, `multiplicity.py`, `sign_flip.py` — leave those, only remove `locality.py`).

- [ ] **Step 4: Append `dispatch.py` into `runner.py`**

Move `ScientificCellDispatchError`, `execute_scientific_cell`, every `_dispatch_*` handler, `_SUMMARY_COORDINATE_EXPERIMENTS`, `_DISPATCH_TABLE`, every `_summary_*` handler, `_SUMMARY_DISPATCH_TABLE`, `_execute_summary_cell`, and every remaining private helper (`_summary_from_coordinates`, `_law_level_finest_summary`, `_refinement_inputs`, `_population_summary`, `_law_from_name`, `_partition_from_coordinates`, `_partition_named`, `_rho_from_offset`, `_direct_rho`, `_variant_index`, `_safety_case`, `_safety_intrinsic_case`, `_coverage_stress_case`, `_execute_failure_boundary`, `_failure_coordinate`) into `runner.py`.

- [ ] **Step 5: Append `execution.py` into `runner.py`**

Move `scientific_result_artifact_key`, `scientific_result_path`, `execute_dispatched_cell`, `_RESULT_FILENAME` into `runner.py`. Its call to `execute_phase_one_cell`/`execute_scientific_cell` becomes a local reference.

- [ ] **Step 6: Append `smoke.py` into `runner.py`**

Move `SmokeResult` and all six smoke-fixture executors into `runner.py`.

- [ ] **Step 7: Reconcile the merged import block and delete the five source files**

```bash
git rm src/trajcert/experiments/dispatch.py src/trajcert/experiments/execution.py src/trajcert/experiments/dependencies.py src/trajcert/experiments/smoke.py src/trajcert/analysis/locality.py
```

- [ ] **Step 8: Fix every caller**

```bash
grep -rln "experiments\.dispatch\|experiments\.execution\|experiments\.dependencies\|experiments\.smoke\|analysis\.locality" src/ tests/
```
Update each hit to import from `trajcert.experiments.runner` instead. Expect hits at minimum in: `src/trajcert/operator.py`, `src/trajcert/reporting/publication_sources.py`, `src/trajcert/reporting/export.py`, `tests/architecture/test_locality.py`, `tests/integration/test_experiment_runner.py`, `tests/integration/test_resume.py`, `tests/e2e/test_smoke.py`.

- [ ] **Step 9: Verify**

```bash
uv run ruff format src/trajcert/experiments/runner.py
uv run ruff check src/trajcert/experiments/runner.py
uv run basedpyright src/trajcert/experiments/runner.py
uv run pytest tests/ -q
```
This is the highest-risk merge in the plan — run the **full** suite, not a slice.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(experiments): merge dispatch, execution, dependencies, locality, smoke into runner.py"
```

---

### Task 4: Fold `synthesis_execution.py`, `synthesis_evidence.py`, `synthesis_inputs.py` into `synthesis.py`

**Files:**
- Merge from: `src/trajcert/experiments/synthesis_execution.py` (293), `synthesis_evidence.py` (550), `synthesis_inputs.py` (149)
- Merge into: `src/trajcert/experiments/synthesis.py` (456)
- Update callers: `src/trajcert/experiments/runner.py` (post Task 3, calls into synthesis execution for the "Statistical Synthesis" cell), `src/trajcert/reporting/*.py`, any test referencing these three modules.

- [ ] **Step 1: Read all four files fully**, noting `synthesis_evidence.py` imports from `synthesis_inputs.py` and `synthesis_execution.py` imports from both — these become local references after merge.

- [ ] **Step 2: Append `synthesis_inputs.py` into `synthesis.py`**

Move `SynthesisDependencyReference`, `read_verified_scientific_result`, `synthesis_dependency_fingerprint`, `verify_synthesis_dependency_fingerprint`, `_dependency_reference`, `_verified_completion_and_index`, `_cell_order`.

- [ ] **Step 3: Append `synthesis_evidence.py` into `synthesis.py`**

Move `SynthesisEvidenceBundle`, `build_synthesis_evidence`, and every private helper it defines.

- [ ] **Step 4: Append `synthesis_execution.py` into `synthesis.py`**

Move `SynthesisLocalValidityInput`, `StatisticalSynthesisRecord`, `synthesis_artifact_keys`, `make_statistical_synthesis_executor`, `execute_statistical_synthesis`, `synthesis_artifact_paths`, `_aggregate`, `_validate_synthesis_cell`.

- [ ] **Step 5: Reconcile imports, delete the three source files**

```bash
git rm src/trajcert/experiments/synthesis_execution.py src/trajcert/experiments/synthesis_evidence.py src/trajcert/experiments/synthesis_inputs.py
```

- [ ] **Step 6: Fix every caller**

```bash
grep -rln "synthesis_execution\|synthesis_evidence\|synthesis_inputs" src/ tests/
```

- [ ] **Step 7: Verify**

```bash
uv run ruff format src/trajcert/experiments/synthesis.py
uv run ruff check src/trajcert/experiments/synthesis.py
uv run basedpyright src/trajcert/experiments/synthesis.py
uv run pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(experiments): merge synthesis_execution, synthesis_evidence, synthesis_inputs into synthesis.py"
```

---

## Part B — `src/trajcert/reporting/` consolidation

### Task 5: Fold `publication_sources.py` and `synthesis_rows.py` into `source_data.py`

**Files:**
- Merge from: `src/trajcert/reporting/publication_sources.py` (664), `src/trajcert/reporting/synthesis_rows.py` (392)
- Merge into: `src/trajcert/reporting/source_data.py` (769)
- Update callers: `src/trajcert/reporting/export.py`, `src/trajcert/reporting/tables.py`, `src/trajcert/reporting/figures.py`, `src/trajcert/cli.py`/`operator.py` (via `report` command), any test referencing these two modules.

- [ ] **Step 1: Read all three files fully**, note `synthesis_rows.py` likely depends on types from `publication_sources.py` or `synthesis.py` (post Task 4) — resolve to local references after merge.

- [ ] **Step 2: Append `publication_sources.py` into `source_data.py`**

Move every row/model class (`SolverOracleValidationRow`, `AnytimeCoverageRow`, `FailureBoundaryRow`, `ComputationalScalingRow`, `TimingValueFigureRow`, `InformationProfileFigureRow`, `AnytimePathFigureRow`, `AnytimeCoverageFigureRow`, `RhoSensitivityFigureRow`, `FailureBoundaryFigureRow`, `ComputationalScalingFigureRow`, `PublicationSourceRows`) and every function (`build_publication_source_rows` and all `_*` helpers).

- [ ] **Step 3: Append `synthesis_rows.py` into `source_data.py`**

Move `TheoremValidationObservation`, `PartitionTimingEvidence`, `CompatibilitySafetyEvidence`, `CompatibilityFloorSourceEvidence`, `SharpnessSourceEvidence`, `SafetySourceEvidence`, `PopulationFigureEvidence`, `SameEndpointFigureEvidence`, `theorem_validation_summary_rows`, `partition_timing_rows`, `partition_coherence_figure_rows`, `compatibility_safety_evidence`, `compatibility_safety_rows`, `_solver_comparison_evidence`, `_partition_timing_row`, and any remaining helpers.

- [ ] **Step 4: Reconcile imports (watch for name collisions with `source_data.py`'s existing row/model types), delete the two source files**

```bash
git rm src/trajcert/reporting/publication_sources.py src/trajcert/reporting/synthesis_rows.py
```

- [ ] **Step 5: Fix every caller**

```bash
grep -rln "publication_sources\|synthesis_rows" src/ tests/
```

- [ ] **Step 6: Verify**

```bash
uv run ruff format src/trajcert/reporting/source_data.py
uv run ruff check src/trajcert/reporting/source_data.py
uv run basedpyright src/trajcert/reporting/source_data.py
uv run pytest tests/unit/test_reporting_renderers.py tests/integration/test_reporting.py -q
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(reporting): merge publication_sources.py and synthesis_rows.py into source_data.py"
```

---

## Part C — CLI consolidation

### Task 6: Fold `operator.py` into `cli.py`

**Files:**
- Merge from: `src/trajcert/operator.py` (550 lines, post Tasks 1-5 its internal imports now point at `runner.py`/`synthesis.py`/`source_data.py`)
- Merge into: `src/trajcert/cli.py` (156 lines)
- Update callers: any test importing `trajcert.operator`

- [ ] **Step 1: Read both files fully.**

`cli.py` already imports specific names from `trajcert.operator` (`RunExperimentResult`, `doctor`, `experiment_status`, `plan_view`, `preprocess`, `report`, `run_experiment`, `smoke`) — after merge these become local references, drop that import block entirely.

- [ ] **Step 2: Append `operator.py`'s content into `cli.py`**, placed after the existing exit-code/dispatch machinery so the public `main()`/`_parser()`/`_dispatch()` stay at the top of the file as the entry point, with the command implementations below.

Move `RunExperimentResult`, `DoctorResult`, `doctor`, `preprocess`, `plan_view`, `smoke`, `run_experiment`, `experiment_status`, `report`, `_load_config`, `_known_experiment_name`, `_experiment_status`, `_current_cell_status`, `_dependency_readiness`, `_executor`, and any other helpers.

- [ ] **Step 3: Delete `operator.py`**

```bash
git rm src/trajcert/operator.py
```

- [ ] **Step 4: Fix every caller**

```bash
grep -rln "trajcert\.operator\|trajcert import operator" src/ tests/
```

- [ ] **Step 5: Verify**

```bash
uv run ruff format src/trajcert/cli.py
uv run ruff check src/trajcert/cli.py
uv run basedpyright src/trajcert/cli.py
uv run pytest tests/integration/test_cli.py tests/unit/test_runtime.py -q
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(cli): merge operator.py into cli.py"
```

---

## Part D — `results/project_summary` artifact-class contract

### Task 7: Remove the `claims/` artifact class and align `export.py`'s allowed-children sets with roadmap §10

Roadmap §10 lists `results/project_summary/`'s children as exactly `figures/`, `tables/`, `metrics/`, `statistics/`, `reproducibility/` — no `claims/`, no `source_data/`. §10's responsibilities note also states synthesis is "No claims/evidence-manifest/hostile-review subsystem," and `docs/TrajCert_Roadmap.md` §10's `experiments/<slug>/` roadmap-results children are `figures/`, `tables/`, `metrics/`, `statistics/` — no `source_data/` there either (source_data lives only under `outputs/`, never `results/`, per §11's "NEVER consumed as scientific computation input" framing — confirm this reading against §12 Manuscript Evidence Contract before changing the constant, since that section governs what `results/` may contain).

**Files:**
- Modify: `src/trajcert/reporting/export.py:68-71` (`_ALLOWED_EXPERIMENT_CHILDREN`, `_ALLOWED_PROJECT_CHILDREN`)
- Delete: `results/project_summary/claims/` (currently just a `.gitkeep`)
- Test: `tests/integration/test_reporting.py`, `tests/unit/test_runtime.py::test_cli_doctor_validates_inputs_and_reports_success`

- [ ] **Step 1: Read roadmap §12 (Manuscript Evidence Contract) in full**

```bash
sed -n '3052,3097p' docs/TrajCert_Roadmap.md
```
Confirm whether `source_data/` is a legitimate `results/` child anywhere, and confirm the exact allowed child sets for both `results/experiments/<slug>/` and `results/project_summary/`.

- [ ] **Step 2: Update `_ALLOWED_EXPERIMENT_CHILDREN` and `_ALLOWED_PROJECT_CHILDREN` in `export.py`**

Set them to match what Step 1 confirms — expected result based on §10 alone: `_ALLOWED_EXPERIMENT_CHILDREN = frozenset({"figures", "tables", "metrics", "statistics"})`, `_ALLOWED_PROJECT_CHILDREN = frozenset({"figures", "tables", "metrics", "statistics", "reproducibility"})`. Adjust if §12 says otherwise.

- [ ] **Step 3: Remove the stray `claims/` directory**

```bash
git rm -r results/project_summary/claims
```

- [ ] **Step 4: Verify**

```bash
uv run ruff check src/trajcert/reporting/export.py
uv run basedpyright src/trajcert/reporting/export.py
uv run pytest tests/integration/test_reporting.py tests/unit/test_runtime.py -q
```
Expected: `test_cli_doctor_validates_inputs_and_reports_success` (currently failing on `project_summary contains invalid artifact classes: ['claims', 'metrics', 'statistics']`) now passes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix(reporting): align results/ artifact-class contract with roadmap section 10/12"
```

---

## Part E — Test-tree reorganization

The roadmap's test tree (§10) names one file per topic and splits `architecture/` differently from what exists. This part remaps current test content into that shape. Do this **after** Parts A-D so import paths in the merged tests are already correct.

### Task 8: Re-survey the test tree after Parts A-D land

**Files:** none (read-only)

- [ ] **Step 1: List current tests and re-diff against roadmap §10's test tree**

```bash
find tests -name "*.py" | sort
sed -n '2565,2649p' docs/TrajCert_Roadmap.md
```
Produce a concrete current-file → roadmap-file mapping table before touching anything (the merges in Parts A-D may have already changed what some test files need to import). Where roadmap names a test file that doesn't exist yet (e.g. `test_hardcoded_values.py`, `test_no_claim_machinery.py`, `test_no_roadmap_runtime.py`, `test_no_compatibility_shims.py`, `test_code_quality.py`), check whether an existing file already covers that behavior under a different name (`tests/architecture/test_guardrail_integrity.py` is a strong candidate — read it before assuming a rename vs. a split) rather than assuming new content is needed.

### Task 9: Split `tests/architecture/test_guardrail_integrity.py` per roadmap `architecture/` file list

**Files:**
- Read: `tests/architecture/test_guardrail_integrity.py`, `tests/architecture/test_no_suppressions.py`
- Target roadmap files: `test_import_boundaries.py`, `test_primitive_leaks.py` (exists), `test_hardcoded_values.py`, `test_config_ownership.py` (exists), `test_locality.py` (exists), `test_no_claim_machinery.py`, `test_no_roadmap_runtime.py`, `test_no_compatibility_shims.py`, `test_code_quality.py`

- [ ] **Step 1: Read `test_guardrail_integrity.py` and `test_no_suppressions.py` in full**, and map each test function/fixture (`tests/architecture/fixtures/invalid/*.py` — `raw_string_identifier`, `raw_float_domain_value`, `raw_dict_boundary`, `any_boundary`, `hardcoded_rho`, `hardcoded_seed`, `direct_yaml_load`, `environment_scientific_value`, `compatibility_alias`, `compatibility_wrapper`, `roadmap_runtime_read`, `claim_registry`, `noqa_suppression`, `type_ignore`, `semgrep_ignore`) to the roadmap file whose description matches (e.g. `hardcoded_rho`/`hardcoded_seed`/`raw_*` fixtures → `test_hardcoded_values.py` and/or `test_primitive_leaks.py`; `compatibility_alias`/`compatibility_wrapper` → `test_no_compatibility_shims.py`; `claim_registry` → `test_no_claim_machinery.py`; `roadmap_runtime_read` → `test_no_roadmap_runtime.py`; `noqa_suppression`/`type_ignore`/`semgrep_ignore` → `test_no_suppressions.py`, which already exists and matches no roadmap name — fold it into whichever of `test_no_compatibility_shims.py`/`test_code_quality.py` fits the suppression-detection rule it enforces, based on what you read).

- [ ] **Step 2: Split the tests file-by-file**, moving each test function into its target file (new files get the same `audit_path`/fixture-loading helpers currently in `test_guardrail_integrity.py` — check whether those helpers belong in a shared `conftest.py` under `tests/architecture/` instead of being duplicated across the new files).

- [ ] **Step 3: Delete `test_guardrail_integrity.py` and `test_no_suppressions.py` once every case has a new home**

```bash
git rm tests/architecture/test_guardrail_integrity.py tests/architecture/test_no_suppressions.py
```

- [ ] **Step 4: Verify**

```bash
uv run pytest tests/architecture/ -q
```
Expected: same pass count as before the split, just redistributed across files.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(architecture): split test_guardrail_integrity.py and test_no_suppressions.py into roadmap-named files"
```

### Task 10: Redistribute `tests/unit/test_data_models.py`, `test_math.py`, `test_reporting_renderers.py`, `test_runtime.py`, `test_scientific_cell_dispatch.py`

**Files:**
- Read: all five files listed above
- Target roadmap files: `test_config.py` (exists), `test_entropy.py` (exists), `test_information.py` (exists), `test_solver.py`/`test_oracle.py` (exist), `test_storage.py` (exists), `test_metrics.py` (exists) — plus `tests/integration/test_planning.py`, `tests/integration/test_experiment_runner.py` for the dispatch/execution-shaped cases currently in `test_scientific_cell_dispatch.py`

- [ ] **Step 1: Read all five files fully** and classify every test function by subject (config parsing, entropy math, storage round-trips, cell dispatch, reporting rendering, determinism/seeding) against the roadmap unit/integration test list from Task 8's survey.

- [ ] **Step 2: For each file, move each test function into its roadmap-named target**, following the target file's existing style/fixtures (read the target file first — do not introduce a second, inconsistent testing style within it).

For `test_runtime.py` specifically (config cross-field-contract tests, vector-annotation test, seed-namespace tests, CLI doctor test): the config-model tests move into `test_config.py`; the CLI doctor test moves into `tests/integration/test_cli.py`; the seed-namespace/seed-descriptor tests have no roadmap-named home (see Assumption 4) — fold them into `test_config.py` as well, in a clearly separate section by import grouping, since `determinism.py`'s only current test coverage is here and dropping it would reduce coverage below the repo's mandatory gate. Flag this specific fold for a second opinion if you disagree once you see the actual test content.

For `test_scientific_cell_dispatch.py`: the plan/registry-shaped assertions (`test_recovered_plan_has_no_configuration_gap_cells`, `test_sequential_utility_family_is_fully_planned`, `test_coverage_stress_cells_match_authoritative_configuration`) move to `tests/integration/test_planning.py`; the dispatch-execution assertions (`test_recovered_scientific_families_dispatch`, `test_terminal_selection_failure_boundary_dispatches`) move to `tests/integration/test_experiment_runner.py`; the source-data parquet round-trip tests move to `test_storage.py`.

For `test_reporting_renderers.py`: move into `test_metrics.py` if the assertions are about metric rendering, or `tests/integration/test_reporting.py` if they exercise the export/render pipeline end to end — check which before deciding.

- [ ] **Step 3: Delete the five source files once every test function has a confirmed new home**

```bash
git rm tests/unit/test_data_models.py tests/unit/test_math.py tests/unit/test_reporting_renderers.py tests/unit/test_runtime.py tests/unit/test_scientific_cell_dispatch.py
```

- [ ] **Step 4: Verify**

```bash
uv run pytest tests/ -q
uv run pytest --cov=trajcert --cov-branch tests/ -q
```
Expected: identical total pass count to before the split (redistributed, not lost), and coverage does not drop below the `fail_under = 90` gate in `pyproject.toml`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(unit): redistribute test_data_models, test_math, test_reporting_renderers, test_runtime, test_scientific_cell_dispatch into roadmap-named files"
```

---

## Part F — Final verification

### Task 11: Full quality-gate pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full mandatory gate**

```bash
uv run ruff format src tools tests noxfile.py
uv run ruff check src tools tests noxfile.py
uv run basedpyright
uv run semgrep --config semgrep src/trajcert
uv run lint-imports
uv run python tools/source_audit.py src/trajcert
uv run complexipy src/trajcert
uv run vulture src/trajcert --min-confidence 100
uv run deptry .
uv run pytest --cov=trajcert --cov-branch
```

- [ ] **Step 2: Fix anything the gate surfaces**

Any remaining `# type:` comments, unused imports, or leftover references to deleted modules (`trajcert.operator`, `trajcert.experiments.dispatch`, `trajcert.experiments.execution`, `trajcert.experiments.coverage`, `trajcert.experiments.legacy_incoherence`, `trajcert.experiments.dependencies`, `trajcert.experiments.smoke`, `trajcert.experiments.synthesis_execution`, `trajcert.experiments.synthesis_evidence`, `trajcert.experiments.synthesis_inputs`, `trajcert.analysis.locality`, `trajcert.reporting.publication_sources`, `trajcert.reporting.synthesis_rows`) should already be gone by this point — treat any surviving reference as a bug from an earlier task and fix it there, not with a patch here.

- [ ] **Step 3: Re-diff `src/trajcert/` against roadmap §10 one final time**

```bash
find src/trajcert -name "*.py" | sort
```
Compare directly against the `docs/TrajCert_Roadmap.md` §10 tree. Confirm exact match (modulo `__init__.py`/`__pycache__`).

- [ ] **Step 4: Commit if Step 2 produced any fixes**

```bash
git add -A
git commit -m "fix: resolve remaining quality-gate findings from roadmap file-tree alignment"
```

---

## Self-review notes

- **Spec coverage:** Parts A-C cover every `src/trajcert` discrepancy found in the initial diff (§10). Part D covers the `results/` artifact-class drift found via the failing `test_cli_doctor_validates_inputs_and_reports_success` test. Part E covers the `tests/` tree discrepancy. Part F is the final gate. Sections of the roadmap not touched by this plan (§11 outputs contract, §16 CLI command/flag/exit-code contract) were checked against the current implementation during planning and found already compliant — no task needed.
- **Known open question carried into Task 7:** whether `source_data/` is a legitimate `results/` child per §12 — resolve by reading §12 before changing `export.py`'s constants, do not guess.
- **Known open question carried into Task 10:** where seed-namespace/determinism tests land, given the roadmap tree has no `test_determinism.py` — Assumption 4 proposes folding into `test_config.py`; flag if that's wrong once the actual test content is in front of you.
