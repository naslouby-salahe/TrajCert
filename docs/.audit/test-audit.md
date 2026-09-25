# Test and quality audit

The final Linux full suite ran without skipped or xfailed tests: 893 passed in
172.94 seconds with the configured coverage gate passing at 91.49%. Fourteen warnings
are third-party matplotlib/pyparsing deprecations. This run used the final 6,000-stream
configuration. The final focused micro-audit regression selection passed 117 tests in
21.25 seconds. After the final UNC-path formatting/type correction, the focused path
regression suite passed 46 tests in 1.21 seconds.

The micro-audit locks the Same Endpoint, Different Timing family to the four configured
partitions and all six configured rho values (24 executable cells). The one-sided raw
mean sign-flip procedure is asymptotically valid under the independent bounded-stream
conditions documented in `sign-flip-validity.md`; without sign symmetry it is not
finite-sample exact for a general mean null.

The final `nox -s quality` session passed formatting, Ruff, BasedPyright, Semgrep,
import contracts, source audit, complexity, Vulture, dependency audit, and
vulnerability audit. The architecture suite includes primitive-leak, hardcoded-value,
configuration ownership, artifact-layout, data-isolation, import-boundary, and
experiment-catalog checks.

Focused deterministic coverage spans entropy/information/oracle boundaries
(`tests/unit/math`), partitions and synthetic construction (`tests/unit/data`),
certification/confidence/projection (`tests/unit/inference`), metrics/bootstrap/
sign-flip/Holm (`tests/unit/analysis`), semantic identity and storage/provenance
(`tests/unit/test_provenance.py`, `test_storage.py`), and completion/reporting
validation (`tests/unit/experiments`, `tests/unit/reporting`). Integration coverage
spans planning, CLI, reporting, provenance, resume/invalidation, and representative
runner behavior. These test routes are deliberately fixture-scale; none invokes the
public scientific experiment runner.

## Deterministic unit-fixture coverage

| Required behavior | Focused test area |
|---|---|
| Entropy boundaries, empty bands, information profile, derivatives, `c=0`, `A+G=0`, compatibility, singleton sets, roots/brackets/residuals | `tests/unit/math/test_information.py`, `test_solver.py`, `test_oracle.py` |
| Partition maps, synthetic-law simplex, apportionment, balanced prefixes, canonical ordering | `tests/unit/data/test_partitions.py`, `test_laws.py`, `test_streams.py` |
| Semantic identity, path rendering, seed derivation, fingerprints and selective sensitivity | `tests/unit/test_provenance.py`, `test_paths.py`, `test_determinism.py` |
| Confidence-sequence inversion, running intersections, finite-sample bounds and state precedence | `tests/unit/inference/` |
| Bootstrap, sign-flip, Holm, linear quantiles and no-imputation behavior | `tests/unit/analysis/` |
| Completion validation, atomic artifacts and verified reporting reads | `tests/unit/experiments/`, `tests/unit/reporting/test_export.py` |

## Deterministic property inventory

The project intentionally uses bounded, fixed-seed parameterized property fixtures
rather than a randomized property-testing dependency. They cover simplex validity
(`tests/unit/data/test_laws.py`), `S(u) >= tau - identity_atol`, convexity and
`u_dagger` range (`tests/unit/math/test_information.py`), refinement monotonicity
and interval feasibility (`tests/unit/math/test_solver.py`), low-dimensional
independent-oracle agreement (`tests/unit/math/test_oracle.py`), cache/no-cache
equality (`tests/integration/test_resume.py`), and semantic-identity/fingerprint
invariance (`tests/unit/test_provenance.py`).

## Integration and wiring coverage

| Required workflow property | Regression coverage |
|---|---|
| Validation/preprocess flow, idempotent rerun and selective overwrite | `tests/unit/test_cli.py`, `tests/integration/test_resume.py` |
| Sibling reuse, parent regeneration, descendant invalidation, partial/stale rejection | `tests/integration/test_resume.py`, `test_provenance.py` |
| Checkpoint/recovery and missing-range behavior | `tests/integration/test_resume.py` |
| Raw-source validation and real-cohort preparation | `tests/unit/data/test_real_trajectories.py`, `tests/unit/test_cli.py` |
| Report-only verified reads and results cleanliness | `tests/unit/reporting/test_export.py`, `tests/architecture/test_artifact_layout.py` |
| Every public CLI handler | `tests/unit/test_cli.py`, `tests/integration/test_cli.py`, `tests/e2e/test_smoke.py` |
| Dynamic catalog/dispatch coverage for all 29 families | `tests/architecture/test_experiment_catalog.py`, `tests/integration/test_experiment_runner.py` |

The CLI tests exercise every `_dispatch` branch with controlled workflow doubles;
integration/e2e tests exercise the real safe leaves. `run` is tested only through
fixture-scale runner/dispatch calls, never through the public scientific CLI command.
