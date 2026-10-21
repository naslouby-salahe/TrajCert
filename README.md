# TrajCert

Reference implementation for trajectory-aware partial-identification and sensitivity certification.

Core experiments generate synthetic data from configured laws; no scientific dataset is bundled. An optional HITL-IoT retrospective replay reads an externally supplied CSV at the path set in `configs/trajcert.yaml` — diagnostic-only, not for external-validation or deployment claims.

## Setup

```bash
uv sync
```

## Workflow

```bash
trajcert doctor
trajcert preprocess
trajcert smoke
trajcert plan

trajcert run "<experiment name>"   # repeat per experiment, in plan order
trajcert run "Statistical Synthesis"   # always last

trajcert doctor
trajcert report
```

Reissuing a failed or downstream `run` command resumes from the nearest valid checkpoint; it does not restart the project.

## Experiments

Run in this order (`Statistical Synthesis` last, after every other experiment it depends on):

```bash
trajcert run "Legacy Partition Incoherence Check"
trajcert run "Path Information Decomposition"
trajcert run "Information Profile Convexity"
trajcert run "Minimum Compatibility Identity"
trajcert run "Sharp-Set Constructive Identity"
trajcert run "Refinement Dominance Identity"
trajcert run "Strict Timing-Gain Identity"
trajcert run "Safety-Boundary Identity"
trajcert run "Endpoint Special-Case Identity"
trajcert run "Anytime Projection Proof Check"
trajcert run "Population Complexity Proof Check"
trajcert run "Production Solver vs Independent Oracle"
trajcert run "Callback-Model Reduction Falsification"
trajcert run "Generic Information-Optimization Reduction"
trajcert run "Partition Coherence"
trajcert run "Same Endpoint, Different Timing"
trajcert run "Strict Timing Gain"
trajcert run "Compatibility Floor Behavior"
trajcert run "Sharpness Against Generic Oracle"
trajcert run "Safety and Intrinsic Impossibility"
trajcert run "Anytime Implementation Hand Cases"
trajcert run "Anytime Coverage Stress"
trajcert run "Anytime Certification Power"
trajcert run "Population Sensitivity Utility"
trajcert run "Trajectory Decision Value"
trajcert run "Failure Boundary Atlas"
trajcert run "Real-Trajectory Validation"
trajcert run "Foreign-Information Negative Control"
trajcert run "Computational Scaling"
trajcert run "Statistical Synthesis"
```

Pass `--overwrite` to force recomputation of an experiment's cells.

## Quality gates

```bash
make quality   # ruff, pyright, semgrep, import-linter, vulture, deptry
make tests     # pytest with coverage
make verify    # architecture tests + mutation testing
```
