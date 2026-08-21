# Roadmap Coverage Inventory

## 1. Authority

**Roadmap:** `docs/TrajCert_Roadmap.md`  
**Repository:** `naslouby-salahe/TrajCert`

This document is the canonical traceability index between the authoritative roadmap and GitHub implementation work.

It does not redefine, replace, weaken, extend, or reinterpret the roadmap.

---

## 2. Inventory Rules

1. Every roadmap obligation must appear in this inventory.
2. One row must represent one atomic, independently verifiable requirement.
3. Requirement IDs are immutable once referenced by a GitHub issue.
4. Every implementation-bearing requirement must map to at least one GitHub issue and one milestone.
5. Every implementation-bearing requirement must define concrete acceptance evidence.
6. Scope constraints, exclusions, rationale, and claim boundaries must remain traceable as `NON_IMPLEMENTATION` requirements even when they create no direct implementation task.
7. Requirement wording must preserve the roadmap meaning and must not introduce new scientific, mathematical, architectural, experimental, or execution decisions.
8. The roadmap remains authoritative whenever this inventory and the roadmap disagree.

---

## 3. Classification

### 3.1 Coverage

- `MAPPED` — the requirement is mapped to one or more GitHub issues.
- `UNMAPPED` — the requirement has not yet been mapped to implementation work.
- `NON_IMPLEMENTATION` — the requirement defines scope, rationale, exclusions, assumptions, terminology, or claim boundaries and creates no direct implementation task.

### 3.2 Readiness

- `READY` — the requirement is sufficiently specified for implementation or verification.
- `AMBIGUOUS` — the requirement contains an unresolved detail that must be resolved before correct implementation.
- `BLOCKED` — implementation or verification cannot proceed because a required dependency, decision, artifact, or prerequisite is unavailable.

### 3.3 Requirement Types

Use the single most appropriate primary type:

- Architecture
- Algorithm
- Mathematics
- Configuration
- Dataset
- Preprocessing
- Training
- Evaluation
- Experiment
- Comparator
- Ablation
- Robustness
- Metric
- Statistical Analysis
- Artifact
- Reporting
- Provenance
- Reproducibility
- Failure Semantics
- Claim Boundary
- CLI / Execution
- Testing

---

## 4. Requirement Inventory

| ID | Roadmap Reference | Atomic Requirement | Type | Milestone | Issue(s) | Acceptance Evidence | Coverage | Readiness |
|---|---|---|---|---|---|---|---|---|
| REQ-001 | §1 | Treat the roadmap as the authoritative standalone scientific and execution specification; lower-level code, plans, manifests, configuration snapshots, and derived artifacts may transcribe but never override it. | Architecture | — | — | Architecture/validation tests prove authority ordering and reject conflicting lower-authority values. | UNMAPPED | READY |
| REQ-002 | §1 | Use the exact comparator name `Legacy bandwise odds-ratio sensitivity` wherever the partition-dependent legacy comparator is named. | Configuration | — | — | Enum/name validation and rendered registry evidence show the exact string. | UNMAPPED | READY |
| REQ-003 | §1 | Represent the five scientific states exactly: CERTIFIED, UNCERTIFIED, MODEL_INCOMPATIBLE, INTRINSICALLY_UNCERTIFIABLE, INSUFFICIENT_EVIDENCE. | Failure Semantics | — | — | Typed state enum and state tests cover exactly the five values. | UNMAPPED | READY |
| REQ-004 | §1 | Represent the seven public experiment execution states exactly: NOT_STARTED, BLOCKED, READY, RUNNING, COMPLETED, FAILED, INVALID. | Failure Semantics | — | — | Typed enum and lifecycle tests cover exactly the seven values. | UNMAPPED | READY |
| REQ-005 | §1 | Represent the five internal execution states exactly: PLANNED, RUNNING, COMPLETED, FAILED, INVALID. | Failure Semantics | — | — | Typed enum and internal lifecycle tests cover exactly the five values. | UNMAPPED | READY |
| REQ-006 | §1 | Represent the evidence classes and authoritative registry classes exactly as specified, with EXPLORATORY available but absent from the authoritative registry. | Configuration | — | — | Evidence-class enum plus registry validation proves exact allowed and used values. | UNMAPPED | READY |
| REQ-007 | §1 | Forbid retrospective promotion of exploratory evidence to confirmatory evidence. | Claim Boundary | — | — | Claim/evidence validation rejects promotion. | NON_IMPLEMENTATION | READY |
| REQ-008 | §1 | Keep execution state distinct from scientific state; valid null, unfavorable-bound, incompatibility, intrinsic-impossibility, and theorem-falsification outcomes remain completed scientific evidence rather than technical failures. | Failure Semantics | — | — | State-precedence tests and completed-result fixtures cover every listed scientific outcome. | UNMAPPED | READY |
| REQ-009 | §1 | Permit only one execution per semantic experiment cell for each material dependency identity; identical re-execution is idempotent reuse unless `--overwrite` is supplied. | Reproducibility | — | — | Idempotent rerun/overwrite integration tests and dependency-fingerprint evidence. | UNMAPPED | READY |
| REQ-010 | §2.1 | Define the target estimand as latent action-error risk theta=P(L=1), where L=1 denotes a wrong or harmful automatic action. | Mathematics | — | — | Domain/metric tests confirm binary outcome semantics and theta definition. | UNMAPPED | READY |
| REQ-011 | §2.1 | Treat each certificate as local to one immutable (client_id, action_channel_id, epoch_id) tuple. | Architecture | — | — | Identity model and lineage tests prove local immutable certificate identity. | UNMAPPED | READY |
| REQ-012 | §2.1 | Require the epoch manifest to fix detector/model identity, action policy, adjudication regime, event/logging semantics, terminal horizon, and finest trajectory representation. | Provenance | — | — | Epoch-manifest schema and validation tests cover all required fields. | UNMAPPED | READY |
| REQ-013 | §2.1 | Close an epoch on any material change while keeping pending actions assigned to the epoch in which they were issued. | Failure Semantics | — | — | Epoch-transition tests prove closure and pending-action retention. | UNMAPPED | READY |
| REQ-014 | §2.2 | Treat the eight listed research questions as the governing questions addressed by the roadmap evidence and Section 21 claims. | Claim Boundary | — | — | Claim registry crosswalk includes all eight questions. | NON_IMPLEMENTATION | READY |
| REQ-015 | §2.2 | Use Section 21 as the authoritative source for confirmatory claim names, exact wording, evidence gates, scopes, and failure states. | Claim Boundary | — | — | Claim-registry generation cross-checks Section 21 authority. | NON_IMPLEMENTATION | READY |
| REQ-016 | §2.3 | Do not claim invention of callback/repeated-attempt data, outcome-dependent timing as missing-data information, mutual information, entropy/divergence sensitivity generally, partial identification, sharp bounds generally, falsification/breakdown frontiers generally, data processing, confidence sequences/e-processes, delayed-outcome inference generally, active querying/abstention/selective acting, or federated evidence borrowing. | Claim Boundary | — | — | Hostile-review claim scan shows none of the prohibited novelty claims. | NON_IMPLEMENTATION | READY |
| REQ-017 | §2.3 | Do not claim finite-sample minimax optimality, universal rho calibration, universal odds-ratio-to-rho conversion, continuous-time or unrestricted serial-drift validity, covariate-conditional validity, active-adjudication optimality, detector-training superiority, privacy protection, poisoning/Byzantine robustness, OOD/zero-day superiority, constrained-device deployment feasibility, or current real-trajectory validation. | Claim Boundary | — | — | Hostile-review claim scan shows none of the prohibited extrapolations. | NON_IMPLEMENTATION | READY |
| REQ-018 | §2.3 | Assume trustworthy event IDs, issue/adjudication timestamps, terminal status, and resolved correctness labels. | Claim Boundary | — | — | Assumption registry/manuscript scope records these theorem assumptions. | NON_IMPLEMENTATION | READY |
| REQ-019 | §2.3 | Treat tampering, malicious adjudicators/clients, poisoning, detector evasion, secure aggregation, and privacy leakage as out of scope. | Claim Boundary | — | — | Scope audit verifies exclusions. | NON_IMPLEMENTATION | READY |
| REQ-020 | §2.3 | Return no certificate on a data-integrity violation. | Failure Semantics | — | — | Integrity-failure end-to-end tests prove no scientific certificate is emitted. | UNMAPPED | READY |
| REQ-021 | §2.3 | Do not use federation for local validity and do not feed foreign-client information into the core inference procedure. | Architecture | — | — | Static dependency and runtime lineage audits prove foreign information absence. | UNMAPPED | READY |
| REQ-022 | §3 | Represent an analysis partition as ordered resolved horizons H1<...<HK with J_Pi in {1,...,K,infinity}. | Mathematics | — | — | Partition-domain tests validate order and category set. | UNMAPPED | READY |
| REQ-023 | §3 | Define observable harmful masses a_k, correct masses b_k, and unresolved mass c exactly as probabilities of the specified J_Pi/L events. | Mathematics | — | — | Population-identity tests compare definitions with direct full-law tables. | UNMAPPED | READY |
| REQ-024 | §3 | Compute A=sum a_k and G=sum b_k and enforce A+G+c=1. | Mathematics | — | — | Simplex validation/property tests. | UNMAPPED | READY |
| REQ-025 | §3 | Model the only hidden terminal binary mass as u=P(J_Pi=infinity,L=1) with 0<=u<=c and theta(u)=A+u. | Mathematics | — | — | Risk-set unit/property tests. | UNMAPPED | READY |
| REQ-026 | §3 | For each band compute m_k=a_k+b_k and r_k=a_k/m_k only when m_k>0; represent r_k as undefined when m_k=0. | Mathematics | — | — | Empty-band tests verify r_k null semantics. | UNMAPPED | READY |
| REQ-027 | §3 | Make empty resolved bands contribute exactly zero to entropy sums. | Mathematics | — | — | Empty-band entropy tests. | UNMAPPED | READY |
| REQ-028 | §3 | Use natural logarithms for all information quantities and report information in nats. | Mathematics | — | — | Numerical reference tests and metadata-unit validation. | UNMAPPED | READY |
| REQ-029 | §3 | Implement binary entropy h(x) with the exact continuous extension 0 log 0 = 0. | Mathematics | — | — | Boundary entropy tests at 0 and 1. | UNMAPPED | READY |
| REQ-030 | §3 | Define R as the resolved indicator 1{J_Pi<infinity}. | Mathematics | — | — | Direct-table decomposition tests. | UNMAPPED | READY |
| REQ-031 | §3.1 | Each action record must contain immutable event_id, client_id, action_channel_id, epoch_id, t_issue, and terminal_horizon fields. | Dataset | — | — | Ledger schema and immutability tests. | UNMAPPED | READY |
| REQ-032 | §3.1 | Allow zero or one valid adjudication record per action. | Dataset | — | — | Ledger cardinality validation tests. | UNMAPPED | READY |
| REQ-033 | §3.1 | Ingest an action inferentially only when it reaches terminal age H_K, even if adjudication was recorded earlier. | Preprocessing | — | — | Maturation chronology integration tests. | UNMAPPED | READY |
| REQ-034 | §3.1 | At maturity assign the permanent category exactly as (k,1), (k,0), or infinity according to resolved harmful/correct or terminal-unresolved status. | Preprocessing | — | — | Maturity categorization tests. | UNMAPPED | READY |
| REQ-035 | §3.1 | Do not let faster-resolving actions enter the sequential statistical sample before terminal maturity. | Statistical Analysis | — | — | Sequential sample chronology tests. | UNMAPPED | READY |
| REQ-036 | §3.1 | Order matured actions by (maturity_timestamp,event_id), using lexicographic event_id tie-breaking. | Reproducibility | — | — | Deterministic ordering tests. | UNMAPPED | READY |
| REQ-037 | §3.1 | Update the sequential estimator exactly once per matured event. | Statistical Analysis | — | — | Duplicate-update/idempotence tests. | UNMAPPED | READY |
| REQ-038 | §3.1 | Enforce the stable-epoch conditional-mean categorical probability contract E[1{Y_n=j}\|F_{n-1}]=p_j for one fixed p vector throughout the epoch. | Statistical Analysis | — | — | Model/assumption validation and sequential theorem tests. | UNMAPPED | READY |
| REQ-039 | §3.1 | Use IID categorical observations for all confirmatory synthetic sequential streams and make no theorem claim under arbitrary serial drift. | Claim Boundary | — | — | Generator tests plus claim-scope audit. | NON_IMPLEMENTATION | READY |
| REQ-040 | §3.1 | Reject as ledger integrity failures exactly the seven listed conditions: duplicate event_id; maturity before issue; adjudication before issue; finite adjudication after terminal horizon; correctness label on unresolved status; finite resolved status without correctness label; category/partition inconsistency. | Failure Semantics | — | — | Parameterized integrity tests cover all seven failure modes. | UNMAPPED | READY |
| REQ-041 | §3.1 | Treat integrity failures as data-validity failures, not evidence-count shortfalls. | Failure Semantics | — | — | State-precedence tests. | UNMAPPED | READY |
| REQ-042 | §3.2 | Fix the finest trajectory representation J* before inspecting corresponding outcomes. | Reproducibility | — | — | Protocol/manifest timing audit proves pre-outcome fixation. | UNMAPPED | READY |
| REQ-043 | §3.2 | Impose the PIS sensitivity model I(L;J*)<=rho. | Mathematics | — | — | Direct-table and profile tests. | UNMAPPED | READY |
| REQ-044 | §3.2 | Require every analysis partition to be a deterministic coarsening g_Pi(J*) and reuse the same numerical rho after coarsening. | Mathematics | — | — | Partition-map and refinement tests. | UNMAPPED | READY |
| REQ-045 | §3.3 | Compute observable timing information tau_Pi=(A+G) I(L;J_Pi\|R=1) using the stated entropy formula when A+G>0. | Mathematics | — | — | Decomposition identity tests. | UNMAPPED | READY |
| REQ-046 | §3.4 | Implement the exact information profile S_Pi(u)=h(A+u)-sum m_k h(r_k)-c h(u/c). | Mathematics | — | — | Profile-vs-direct-table tests. | UNMAPPED | READY |
| REQ-047 | §3.4 | Implement/check the stated first and second derivatives on 0<u<c and nondegenerate domains. | Mathematics | — | — | Symbolic/high-precision derivative tests. | UNMAPPED | READY |
| REQ-048 | §3.5 | When A+G>0 compute u_dagger=Ac/(A+G), theta_dagger=A/(A+G), and rho_min=tau_Pi. | Mathematics | — | — | Minimum-compatibility identity tests. | UNMAPPED | READY |
| REQ-049 | §3.6 | Define U_Pi(rho)={u in [0,c]:S_Pi(u)<=rho} and classify rho<tau as empty, rho=tau as singleton {u_dagger}, and rho>tau as interval [u_L,u_U]. | Mathematics | — | — | Risk-set regime tests. | UNMAPPED | READY |
| REQ-050 | §3.6 | Return the sharp latent-risk interval Theta_Pi(rho)=[A+u_L,A+u_U]. | Mathematics | — | — | Oracle sharpness validation. | UNMAPPED | READY |
| REQ-051 | §3.7 | Under fixed terminal horizon, enforce refinement monotonicity S_coarse(u)<=S_fine(u) and Theta_fine(rho) subseteq Theta_coarse(rho). | Mathematics | — | — | Refinement identity/property tests. | UNMAPPED | READY |
| REQ-052 | §3.7 | Compute exact timing value Delta tau=S_fine(u)-S_coarse(u)=I(L;J_fine\|J_coarse). | Mathematics | — | — | Timing-decomposition tests. | UNMAPPED | READY |
| REQ-053 | §3.7 | Under compatibility and interior-upper-root conditions, enforce Delta tau>0 iff u_U^fine(rho)<u_U^coarse(rho). | Mathematics | — | — | Strict-timing-gain identity tests. | UNMAPPED | READY |
| REQ-054 | §3.8 | Implement the four safety regimes for beta relative to A, theta_dagger, and A+c exactly as specified, including rho_star=S_Pi(beta-A) only in the interior frontier regime. | Mathematics | — | — | Safety-regime table-driven tests. | UNMAPPED | READY |
| REQ-055 | §3.8 | For deterministic safety-boundary validation derive theta_max=A+c and exactly the five specified beta cases, including DEGENERATE_SAFETY_INTERVAL when A=theta_dagger makes the between-boundaries case invalid. | Evaluation | — | — | Safety-boundary experiment fixtures and expected-status tests. | UNMAPPED | READY |
| REQ-056 | §3.8 | Treat the five safety-budget constructions as fixed derived scientific constructions, not editable configuration. | Configuration | — | — | Configuration ownership test rejects independent beta-case constants. | UNMAPPED | READY |
| REQ-057 | §3.9 | For K=1 enforce tau=0 and S(u)=I(L;R), and use this as the mandatory endpoint-only PIS baseline. | Comparator | — | — | Endpoint special-case tests. | UNMAPPED | READY |
| REQ-058 | §3.10 | Use O(K) sufficient-statistic accumulation in the production population solver. | Algorithm | — | — | Operation-count proof check. | UNMAPPED | READY |
| REQ-059 | §3.10 | Use numerically stable xlogy-equivalent entropy evaluation with exact continuous boundary extensions. | Algorithm | — | — | Boundary numerical tests. | UNMAPPED | READY |
| REQ-060 | §3.10 | Classify compatibility and exact boundary cases before iterative root solving. | Algorithm | — | — | Solver branch-order tests. | UNMAPPED | READY |
| REQ-061 | §3.10 | For compatible nondegenerate cases use bisection, solving lower and upper branches separately on [0,u_dagger] and [u_dagger,c]. | Algorithm | — | — | Solver-bracket tests. | UNMAPPED | READY |
| REQ-062 | §3.10 | Maintain an exact sign-valid bracket for S_Pi(u)-rho on each branch. | Algorithm | — | — | Bracket invariant tests. | UNMAPPED | READY |
| REQ-063 | §3.10 | Terminate population bisection only when bracket width <= numerics.population_root_absolute_tolerance and return the midpoint. | Algorithm | — | — | Tolerance tests. | UNMAPPED | READY |
| REQ-064 | §3.10 | Persist final bracket endpoints, width, returned root, residual, and iteration count for each solved branch. | Artifact | — | — | Solver result schema validation. | UNMAPPED | READY |
| REQ-065 | §3.10 | Derive the bisection iteration cap as ceil(log2(w0/tolerance))+2 rather than configuring it independently. | Algorithm | — | — | Iteration-cap derivation test. | UNMAPPED | READY |
| REQ-066 | §3.10 | Require final root bracket width <= population_root_absolute_tolerance and returned-root absolute information residual <= deterministic_identity_tolerance. | Evaluation | — | — | Production-solver validation records. | UNMAPPED | READY |
| REQ-067 | §3.10 | Return explicit degeneracy/scientific states, never round scientific quantities before comparison, and never clip sensitivity budgets to force compatibility. | Failure Semantics | — | — | Boundary and anti-clipping tests. | UNMAPPED | READY |
| REQ-068 | §4 | Use `configs/trajcert.yaml` as the single authoritative production configuration file for genuinely supplied/selected/swept configuration values. | Configuration | — | — | Configuration loading/ownership tests. | UNMAPPED | READY |
| REQ-069 | §4 | Keep derived formulas, fixed algorithms, validation/failure semantics, provenance rules, reporting procedures, semantic identity, registry definitions, and claim wording outside YAML. | Configuration | — | — | Configuration schema rejects non-authoritative derived/behavior fields. | UNMAPPED | READY |
| REQ-070 | §4 | Limit `configs/tests.yml` and `configs/smoke.yml` to runner settings; they must not define independently editable production scientific values. | Configuration | — | — | Config ownership tests. | UNMAPPED | READY |
| REQ-071 | §4 | Set `schema_version: 1` in the production YAML. | Configuration | — | — | Snapshot validation. | UNMAPPED | READY |
| REQ-072 | §4 | Set `method.primary_finest_resolved_bands` to exactly 8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-073 | §4 | Set `method.synthetic_terminal_horizon_age_units` to exactly 8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-074 | §4 | Set `budgets.primary_risk` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-075 | §4 | Set `budgets.primary_information_nats` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-076 | §4 | Set `confidence.anytime_delta` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-077 | §4 | Set `confidence.non_anytime_level` to exactly 0.95. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-078 | §4 | Set `confidence.confirmatory_alpha` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-079 | §4 | Set `minimum_evidence.matured_events` to exactly 200. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-080 | §4 | Set `minimum_evidence.resolved_events` to exactly 50. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-081 | §4 | Configure synthetic law `No outcome-path dependence` with exactly theta=0.05, q1=0.1, q0=0.1, lambda1=0, and lambda0=0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-082 | §4 | Configure synthetic law `Timing only: harmful outcomes resolve late` with exactly theta=0.05, q1=0.1, q0=0.1, lambda1=0.45, and lambda0=-0.15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-083 | §4 | Configure synthetic law `Terminal only: harmful outcomes remain unresolved` with exactly theta=0.05, q1=0.3, q0=0.05, lambda1=0, and lambda0=0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-084 | §4 | Configure synthetic law `Timing and terminal: harmful outcomes resolve late` with exactly theta=0.05, q1=0.3, q0=0.05, lambda1=0.45, and lambda0=-0.15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-085 | §4 | Configure synthetic law `Timing and terminal: harmful outcomes resolve early` with exactly theta=0.05, q1=0.05, q0=0.3, lambda1=-0.45, and lambda0=0.15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-086 | §4 | Configure synthetic law `High terminal unresolvedness` with exactly theta=0.05, q1=0.7, q0=0.4, lambda1=0.35, and lambda0=-0.1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-087 | §4 | Configure synthetic law `Low error prevalence` with exactly theta=0.01, q1=0.3, q0=0.05, lambda1=0.45, and lambda0=-0.15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-088 | §4 | Configure synthetic law `High error prevalence` with exactly theta=0.2, q1=0.3, q0=0.05, lambda1=0.45, and lambda0=-0.15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-089 | §4 | Configure synthetic law `Intrinsic safety impossibility` with exactly theta=0.15, q1=0.1, q0=0.1, lambda1=0, and lambda0=0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-090 | §4 | Configure synthetic law `Near numerical degeneracy` with exactly theta=0.01, q1=0.9, q0=0.01, lambda1=0.8, and lambda0=-0.8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-091 | §4 | Configure synthetic law `Same endpoint without timing information` with exactly theta=0.05, q1=0.2, q0=0.1, lambda1=0, and lambda0=0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-092 | §4 | Configure synthetic law `Same endpoint with timing information` with exactly theta=0.05, q1=0.2, q0=0.1, lambda1=0.6, and lambda0=-0.2. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-093 | §4 | Preserve the twelve `synthetic_data.laws` entries in the exact roadmap file order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-094 | §4 | Set `synthetic_data.utility_and_coherence_laws` to exactly the six listed law names in roadmap order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-095 | §4 | Set `synthetic_data.sharpness_oracle_laws` to exactly the ten listed law names in roadmap order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-096 | §4 | Set `synthetic_data.safety_and_impossibility_laws` to exactly the eight listed law names in roadmap order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-097 | §4 | Configure `8-band partition` with groups [[1],[2],[3],[4],[5],[6],[7],[8]]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-098 | §4 | Configure `4-band partition` with groups [[1,2],[3,4],[5,6],[7,8]]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-099 | §4 | Configure `2-band partition` with groups [[1,2,3,4],[5,6,7,8]]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-100 | §4 | Configure `Endpoint-only partition` with groups [[1,2,3,4,5,6,7,8]]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-101 | §4 | Set `partitions.computational_scaling_resolved_bands` to exactly [1,2,4,8,16,32,64,128]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-102 | §4 | Set `sensitivity.primary_rho_grid` to exactly [0,0.0025,0.005,0.01,0.02,0.03,0.05,0.075,0.10,0.15,0.20,0.30,0.40,0.50]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-103 | §4 | Set `sensitivity.primary_beta_grid` to exactly [0.01,0.025,0.05,0.10,0.20]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-104 | §4 | Set `sensitivity.same_endpoint_rho_grid` to exactly [0.01,0.05,0.10,0.20,0.40]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-105 | §4 | Set `sensitivity.theorem_rho_offsets.sharp_set` to exactly [0,0.005,0.025,0.100]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-106 | §4 | Set `sensitivity.theorem_rho_offsets.oracle_validation` to exactly [0,0.0025,0.010,0.050,0.150]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-107 | §4 | Set `sensitivity.theorem_rho_offsets.refinement_above_fine_tau` to exactly [0.005,0.025,0.100]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-108 | §4 | Set `sensitivity.confirmatory_sharpness_oracle_offset_above_tau` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-109 | §4 | Set `numerics.population_root_absolute_tolerance` to exactly 1.0e-12. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-110 | §4 | Set `numerics.deterministic_identity_tolerance` to exactly 1.0e-10. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-111 | §4 | Set `numerics.scientific_comparison_guard` to exactly 1.0e-12. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-112 | §4 | Set `numerics.oracle_boundary_bracket_width` to exactly 1.0e-14. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-113 | §4 | Set `numerics.oracle_decimal_digits` to exactly 100. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-114 | §4 | Set `numerics.callback_equality_tolerance` to exactly 1.0e-10. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-115 | §4 | Set `numerics.callback_root_dedup_tolerance` to exactly 1.0e-12. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-116 | §4 | Set `numerics.callback_grid_points` to exactly 10001. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-117 | §4 | Set `numerics.callback_golden_section_width` to exactly 1.0e-30. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-118 | §4 | Set `numerics.callback_q_acceptance` to exactly 1.0e-20. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-119 | §4 | Set `numerics.pattern_mixture_initial_probability_clip` to exactly 1.0e-8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-120 | §4 | Set `numerics.pattern_mixture_bound_touch_tolerance` to exactly 1.0e-8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-121 | §4 | Set `numerics.pattern_mixture_gradient_infinity_limit` to exactly 1.0e-8. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-122 | §4 | Set `numerics.anytime_category_root_tolerance` to exactly 1.0e-12. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-123 | §4 | Set `numerics.outer_certified_gap` to exactly 1.0e-6. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-124 | §4 | Set `numerics.outer_max_visited_nodes` to exactly 2000000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-125 | §4 | Set `numerics.outer_minimum_arbitrary_precision_bits` to exactly 128. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-126 | §4 | Set `numerics.outer_split_tie_tolerance` to exactly 1.0e-30. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-127 | §4 | Set `numerics.constructive_profile_grid_points` to exactly 2001. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-128 | §4 | Set `numerics.convexity_profile_grid_points` to exactly 1001. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-129 | §4 | Set `numerics.information_profile_figure_grid_points` to exactly 1001. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-130 | §4 | Include zero-information strict-timing case `No outcome-path dependence` with fine `8-band partition` and coarse `4-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-131 | §4 | Include zero-information strict-timing case `Terminal only: harmful outcomes remain unresolved` with fine `8-band partition` and coarse `4-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-132 | §4 | Include zero-information strict-timing case `Same endpoint without timing information` with fine `8-band partition` and coarse `2-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-133 | §4 | Include positive-information strict-timing case `Timing only: harmful outcomes resolve late` with fine `8-band partition` and coarse `4-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-134 | §4 | Include positive-information strict-timing case `Timing and terminal: harmful outcomes resolve late` with fine `8-band partition` and coarse `4-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-135 | §4 | Include positive-information strict-timing case `Same endpoint with timing information` with fine `8-band partition` and coarse `2-band partition`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-136 | §4 | Set `legacy_partition_incoherence.gamma_values` to exactly [1.5,2,4]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-137 | §4 | Set `legacy_partition_incoherence.q_values` to exactly [0.1,0.3]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-138 | §4 | Set `legacy_partition_incoherence.latent_outcome_probabilities` to exactly [0.5,0.5]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-139 | §4 | Set `comparators.legacy_bandwise_odds_ratio_sensitivity.gamma_grid` to exactly [1,1.25,1.5,2,4,8]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-140 | §4 | Set `comparators.repeated_attempt_pattern_mixture.c_grid` to exactly [0,1,2,3]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-141 | §4 | Set `comparators.repeated_attempt_pattern_mixture.coefficient_bounds` to exactly [-20,20]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-142 | §4 | Set `comparators.repeated_attempt_pattern_mixture.ftol` to exactly 1.0e-15. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-143 | §4 | Set `comparators.repeated_attempt_pattern_mixture.gtol` to exactly 1.0e-12. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-144 | §4 | Set `comparators.repeated_attempt_pattern_mixture.max_iterations` to exactly 10000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-145 | §4 | Set `comparators.repeated_attempt_pattern_mixture.initial_zeta1` to exactly 0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-146 | §4 | Set `sequential_inference.coverage_validation.n_max` to exactly 500. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-147 | §4 | Set coverage-validation seed indices to exactly start=0 and stop_exclusive=5000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-148 | §4 | Set `sequential_inference.coverage_validation.checkpoint_batch_size` to exactly 100. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-149 | §4 | Set `sequential_inference.coverage_validation.clopper_pearson_confidence` to exactly 0.95. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-150 | §4 | Set `sequential_inference.coverage_validation.acceptance_upper_limit` to exactly 0.06. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-151 | §4 | Set `sequential_inference.sequential_utility.n_max` to exactly 2000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-152 | §4 | Set sequential-utility seed indices to exactly start=0 and stop_exclusive=500. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-153 | §4 | Set `sequential_inference.sequential_utility.checkpoint_batch_size` to exactly 50. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-154 | §4 | Set `sequential_inference.sequential_utility.rho_grid` to exactly [0.05,0.10,0.20]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-155 | §4 | Set `statistics.bootstrap.resamples` to exactly 10000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-156 | §4 | Set `statistics.sign_flip.randomizations` to exactly 20000. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-157 | §4 | Set `statistics.practical_metrics` to exactly [`Time to first certification`,`Certified update fraction`,`Final risk upper bound`] in roadmap order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-158 | §4 | Set `materiality.population.minimum_absolute_tightening` to exactly 0.005. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-159 | §4 | Set `materiality.population.minimum_relative_unresolved_gain` to exactly 0.20. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-160 | §4 | Set `materiality.population.minimum_qualifying_laws` to exactly 3. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-161 | §4 | Set `materiality.population.minimum_compatible_rho_values_per_qualifying_law` to exactly 2. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-162 | §4 | Set `materiality.sequential.minimum_certified_update_fraction_gain` to exactly 0.05. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-163 | §4 | Set `materiality.sequential.minimum_qualifying_laws` to exactly 3. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-164 | §4 | Set `materiality.sequential.paired_bootstrap_lower_bound_must_exceed` to exactly 0. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-165 | §4 | Set display decimals exactly to risk_probability=4, information_nats=5, p_value=4, runtime_milliseconds=2. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-166 | §4 | Set `display.pvalue_display_below` to exactly 0.0001. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-167 | §4 | Set `failure_boundary.base_law` to exactly `Timing and terminal: harmful outcomes resolve late`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-168 | §4 | Set failure-boundary `Terminal unresolved severity` levels to exactly q1_equals_q0_values=[0,0.1,0.2,0.3,0.5,0.7,0.9]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-169 | §4 | Set failure-boundary `Timing contrast` levels to exactly d_values=[0,0.1,0.2,0.4,0.6,0.8,1.0]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-170 | §4 | Set failure-boundary `Harmful prevalence` levels to exactly theta_values=[0.001,0.005,0.01,0.025,0.05,0.10,0.20]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-171 | §4 | Set failure-boundary `Path resolution` levels to exactly resolved_band_values=[1,2,4,8,16,32,64]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-172 | §4 | Set failure-boundary `Sensitivity margin above compatibility` levels to exactly d_values=[0,0.001,0.0025,0.005,0.01,0.025,0.05]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-173 | §4 | Set failure-boundary `Risk-budget offset from intrinsic boundary` levels to exactly d_values=[-0.05,-0.02,-0.005,0,0.005,0.02,0.05]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-174 | §4 | Set failure-boundary `Matured sample size` levels to exactly n_values=[25,50,100,200,500,1000,2000]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-175 | §4 | Set failure-boundary `Terminal-selection asymmetry` levels to exactly q1_q0_pairs=[[0.01,0.50],[0.02,0.40],[0.05,0.30],[0.10,0.10],[0.30,0.05],[0.40,0.02],[0.50,0.01]]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-176 | §4 | Set failure-boundary `Optimizer-node budget` levels to exactly node_values=[1000,5000,20000,100000,500000,1000000,2000000]. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-177 | §4 | Set failure-boundary optimizer-node deterministic matured sample size to exactly 500. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-178 | §4 | Configure sequential stress case `Independent resolution control` with law `No outcome-path dependence`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-179 | §4 | Configure sequential stress case `Timing-only harmful-late stress` with law `Timing only: harmful outcomes resolve late`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-180 | §4 | Configure sequential stress case `Terminal-selection harmful-unresolved stress` with law `Terminal only: harmful outcomes remain unresolved`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-181 | §4 | Configure sequential stress case `Timing-and-terminal harmful-late stress` with law `Timing and terminal: harmful outcomes resolve late`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-182 | §4 | Configure sequential stress case `Timing-and-terminal harmful-early stress` with law `Timing and terminal: harmful outcomes resolve early`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-183 | §4 | Configure sequential stress case `High unresolvedness stress` with law `High terminal unresolvedness`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-184 | §4 | Configure sequential stress case `Low error-prevalence stress` with law `Low error prevalence`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-185 | §4 | Configure sequential stress case `Near-degeneracy stress` with law `Near numerical degeneracy`, resolved_bands=8, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-186 | §4 | Configure sequential stress case `Sixteen-band resolution stress` with law `Timing and terminal: harmful outcomes resolve late`, resolved_bands=16, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-187 | §4 | Configure sequential stress case `Thirty-two-band resolution stress` with law `Timing and terminal: harmful outcomes resolve late`, resolved_bands=32, and rho_offset_above_true_information=0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-188 | §4 | Configure sequential stress case `Minimum-information completion stress` with law `Minimum-information completion of Timing and terminal: harmful outcomes resolve late`, resolved_bands=8, and rho_offset_above_compatibility_floor=0.002. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-189 | §4 | Configure sequential stress case `Near-certification risk-budget stress` with law `Timing and terminal: harmful outcomes resolve late`, resolved_bands=8, and rho_offset_above_true_information=0.01; beta_offset_above_true_upper_bound=0.002. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-190 | §4 | Set `sequential_stress_methods` to exactly [`TrajCert`,`Time-uniform observable-law projection`,`Repeated-static-monitoring negative control`,`Ignorable-delay anytime reference`] in roadmap order. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-191 | §4 | Set `runtime_benchmark.warmup_repetitions` to exactly 5. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-192 | §4 | Set `runtime_benchmark.measured_repetitions` to exactly 30. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-193 | §4 | Set `runtime_benchmark.law` to exactly `Timing and terminal: harmful outcomes resolve late`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-194 | §4 | Set `runtime_benchmark.outer_projection_input.n` to exactly 500. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-195 | §4 | Set `runtime_benchmark.outer_projection_rho_offset_above_true_information` to exactly 0.01. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-196 | §4 | Set `runtime_environment.architecture` to exactly `Linux x86_64`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-197 | §4 | Set `runtime_environment.container_base_family` to exactly `Debian 12 / bookworm`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-198 | §4 | Set `runtime_environment.python_image` to exactly `python:3.13.15-slim-bookworm`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-199 | §4 | Set `runtime_environment.python_implementation` to exactly `CPython`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-200 | §4 | Set `runtime_environment.python_version` to exactly `3.13.15`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-201 | §4 | Set `runtime_environment.locale` to exactly `C.UTF-8`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-202 | §4 | Set `runtime_environment.timezone` to exactly `UTC`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-203 | §4 | Set runtime environment variable `PYTHONHASHSEED` to exactly `0`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-204 | §4 | Set runtime environment variable `OMP_NUM_THREADS` to exactly `1`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-205 | §4 | Set runtime environment variable `OPENBLAS_NUM_THREADS` to exactly `1`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-206 | §4 | Set runtime environment variable `MKL_NUM_THREADS` to exactly `1`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-207 | §4 | Set runtime environment variable `NUMEXPR_NUM_THREADS` to exactly `1`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-208 | §4 | Set `runtime_environment.authoritative_execution` to exactly `CPU`. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-209 | §4 | Pin direct dependency `numpy` to exactly version 2.5.2. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-210 | §4 | Pin direct dependency `scipy` to exactly version 1.18.0. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-211 | §4 | Pin direct dependency `pandas` to exactly version 2.3.3. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-212 | §4 | Pin direct dependency `pyarrow` to exactly version 25.0.1. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-213 | §4 | Pin direct dependency `python-flint` to exactly version 0.9.0. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-214 | §4 | Pin direct dependency `sympy` to exactly version 1.13.3. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-215 | §4 | Pin direct dependency `mpmath` to exactly version 1.3.0. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-216 | §4 | Pin direct dependency `matplotlib` to exactly version 3.10.0. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-217 | §4 | Pin direct dependency `pyyaml` to exactly version 6.0.3. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-218 | §4 | Pin direct dependency `pytest` to exactly version 8.3.5. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-219 | §4 | Pin direct dependency `hypothesis` to exactly version 6.125.3. | Reproducibility | — | — | Lock-file and environment-manifest validation. | UNMAPPED | READY |
| REQ-220 | §4 | Pin reproducibility tool `pip-tools` to exactly version 7.6.0. | Reproducibility | — | — | Lock generation environment validation. | UNMAPPED | READY |
| REQ-221 | §4 | Set the transitive lock file to exactly `requirements.lock`. | Reproducibility | — | — | Repository path and lock validation. | UNMAPPED | READY |
| REQ-222 | §4 | Set `artifacts.execution_workspace_root` to exactly `outputs`. | Artifact | — | — | Workspace path validation. | UNMAPPED | READY |
| REQ-223 | §4 | Set `artifacts.execution_workspace_directories` to exactly [`preprocessing`,`artifacts`,`experiments`,`cache`]. | Artifact | — | — | Workspace path validation. | UNMAPPED | READY |
| REQ-224 | §4 | Set `artifacts.reusable_artifact_directories` to exactly [`fitted`,`baselines`,`derived/plans`,`derived/streams`,`derived/population`,`derived/sequential`]. | Artifact | — | — | Workspace path validation. | UNMAPPED | READY |
| REQ-225 | §4 | Set `artifacts.results_root` to exactly `results`. | Artifact | — | — | Results path validation. | UNMAPPED | READY |
| REQ-226 | §4 | Set `artifacts.results_experiments_directory` to exactly `experiments`. | Artifact | — | — | Results path validation. | UNMAPPED | READY |
| REQ-227 | §4 | Set `artifacts.results_project_summary_directory` to exactly `project_summary`. | Artifact | — | — | Results path validation. | UNMAPPED | READY |
| REQ-228 | §4 | Set `artifacts.result_experiment_directories` to exactly the twelve roadmap-listed experiment result subdirectories. | Artifact | — | — | Results tree validation. | UNMAPPED | READY |
| REQ-229 | §4 | Set `artifacts.project_summary_directories` to exactly the sixteen roadmap-listed project-summary subdirectories. | Artifact | — | — | Results tree validation. | UNMAPPED | READY |
| REQ-230 | §4 | Set `artifacts.plan_json_filename` to exactly `experiment_plan.json`. | Artifact | — | — | Path/name validation. | UNMAPPED | READY |
| REQ-231 | §4 | Set `artifacts.plan_parquet_filename` to exactly `experiment_plan.parquet`. | Artifact | — | — | Path/name validation. | UNMAPPED | READY |
| REQ-232 | §4 | Set `artifacts.completion_marker_file` to exactly `COMPLETED.json`. | Artifact | — | — | Path/name validation. | UNMAPPED | READY |
| REQ-233 | §4 | Set `smoke.compatible_population_cases` to exactly 1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-234 | §4 | Set `smoke.incompatible_population_cases` to exactly 1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-235 | §4 | Set `smoke.endpoint_only_partition_cases` to exactly 1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-236 | §4 | Set `smoke.refinement_cases` to exactly 1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-237 | §4 | Set `smoke.deterministic_cs_event_count` to exactly 25. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-238 | §4 | Set `smoke.low_dimensional_interval_optimizer_hand_cases` to exactly 1. | Configuration | — | — | Configuration snapshot plus schema/value validation test. | UNMAPPED | READY |
| REQ-239 | §4 | Set CLI exit code `success_or_scientific_noop` to exactly 0. | CLI / Execution | — | — | CLI exit-code tests. | UNMAPPED | READY |
| REQ-240 | §4 | Set CLI exit code `usage_or_unknown_name` to exactly 2. | CLI / Execution | — | — | CLI exit-code tests. | UNMAPPED | READY |
| REQ-241 | §4 | Set CLI exit code `environment_or_prerequisite_block` to exactly 10. | CLI / Execution | — | — | CLI exit-code tests. | UNMAPPED | READY |
| REQ-242 | §4 | Set CLI exit code `technical_execution_failure` to exactly 20. | CLI / Execution | — | — | CLI exit-code tests. | UNMAPPED | READY |
| REQ-243 | §4 | Set CLI exit code `completion_or_evidence_failure` to exactly 30. | CLI / Execution | — | — | CLI exit-code tests. | UNMAPPED | READY |
| REQ-244 | §4 | Use no generic scientific epsilon; formulas must use exact continuous extensions and declared algorithms. | Mathematics | — | — | Search/architecture tests plus numerical boundary tests. | UNMAPPED | READY |
| REQ-245 | §4 | Allow scientific_comparison_guard only to prevent false strong classification from representation error; it must never relax certification, which still requires proven upper risk <= beta. | Failure Semantics | — | — | Boundary classification tests around guard. | UNMAPPED | READY |
| REQ-246 | §4 | Use exact mathematical log(2) where specified rather than an approximate configurable constant. | Mathematics | — | — | Symbolic-token and numerical endpoint tests. | UNMAPPED | READY |
| REQ-247 | §4 | Treat synthetic law file order as authoritative wherever deterministic law ordering is required. | Reproducibility | — | — | Registry ordering tests. | UNMAPPED | READY |
| REQ-248 | §4 | Treat Section 17 experiment ordering as authoritative. | Reproducibility | — | — | Plan ordering tests. | UNMAPPED | READY |
| REQ-249 | §4 | Treat primary_beta_grid as descriptive Table-1/configuration provenance only; no current registry experiment independently sweeps it. | Experiment | — | — | Registry validation proves no independent beta-grid sweep. | UNMAPPED | READY |
| REQ-250 | §4 | Treat YAML categorical values as semantic names only where they actually select configured laws, partitions, methods, or runtime identifiers. | Configuration | — | — | Typed configuration validation. | UNMAPPED | READY |
| REQ-251 | §4 | Treat scientific/statistical grid membership as prespecified and changes as material only to artifacts that actually consume the changed parameter. | Provenance | — | — | Selective invalidation tests. | UNMAPPED | READY |
| REQ-252 | §4.1 | Use pyproject.toml as the canonical direct dependency declaration. | Reproducibility | — | — | Dependency-hygiene test. | UNMAPPED | READY |
| REQ-253 | §4.1 | Generate requirements.lock inside the authoritative Python 3.13.15 container using exactly the prescribed pip-tools commands/options and hashes. | Reproducibility | — | — | Lock-generation reproducibility check. | UNMAPPED | READY |
| REQ-254 | §4.1 | Use the default public PyPI unless an explicitly documented organization mirror is required. | Reproducibility | — | — | Dependency-resolution provenance. | UNMAPPED | READY |
| REQ-255 | §4.1 | Commit requirements.lock as the authoritative transitive dependency artifact. | Reproducibility | — | — | Repository/lock validation. | UNMAPPED | READY |
| REQ-256 | §4.1 | Install authoritative dependencies with `python -m pip install --require-hashes -r requirements.lock`. | CLI / Execution | — | — | Environment build test. | UNMAPPED | READY |
| REQ-257 | §4.1 | Never re-resolve dependencies during scientific execution when a valid requirements.lock exists. | Reproducibility | — | — | Execution/environment tests. | UNMAPPED | READY |
| REQ-258 | §5.1 | Generate resolved-band weights w_k(lambda) using the exact normalized exponential formula centered at (K+1)/2. | Dataset | — | — | Synthetic-law numerical tests. | UNMAPPED | READY |
| REQ-259 | §5.1 | Generate P(J=k\|L=1)=(1-q1)w_k(lambda1), P(J=infinity\|L=1)=q1, and analogous L=0 probabilities with q0/lambda0. | Dataset | — | — | Full-law table tests. | UNMAPPED | READY |
| REQ-260 | §5.1 | Sample L with P(L=1)=theta and hide L for terminal-unresolved observations. | Dataset | — | — | Generator distribution/schema tests. | UNMAPPED | READY |
| REQ-261 | §5.1 | Interpret positive lambda as later resolved mass and negative lambda as earlier resolved mass. | Claim Boundary | — | — | Law-role documentation/validation. | NON_IMPLEMENTATION | READY |
| REQ-262 | §5.1 | Use the configured synthetic terminal horizon and equally spaced resolved boundaries H_k=(k/K)H_K for every K so resolution changes do not change the terminal horizon. | Dataset | — | — | Partition-boundary tests. | UNMAPPED | READY |
| REQ-263 | §5.1 | Admit every generated synthetic action to the ledger with action coverage 1.0 and no hidden subsampling. | Dataset | — | — | Generator count tests. | UNMAPPED | READY |
| REQ-264 | §5.2 | Assign the twelve synthetic laws exactly the scientific roles listed in Section 5.2. | Claim Boundary | — | — | Inventory/experiment role validation. | NON_IMPLEMENTATION | READY |
| REQ-265 | §5.3 | Construct each derived minimum-information law by preserving all observable masses and setting hidden terminal harmful mass to u_dagger=Ac/(A+G). | Dataset | — | — | Derived-law tests. | UNMAPPED | READY |
| REQ-266 | §5.3 | Require each derived minimum-information law to have full-law path information exactly tau and use it only in declared compatibility-boundary stress tests. | Evaluation | — | — | Direct-table identity and registry-use tests. | UNMAPPED | READY |
| REQ-267 | §5.4 | For K-scaling laws preserve theta,q1,q0,lambda1,lambda0 and change only K across configured scaling values. | Dataset | — | — | Scaling-law manifest tests. | UNMAPPED | READY |
| REQ-268 | §5.5 | Generate each stochastic stream by Bernoulli(theta) outcome sampling followed by conditional J sampling, revealing (J,L) if finite and only infinity if unresolved, with IID events. | Dataset | — | — | Seeded generator tests/statistical smoke checks. | UNMAPPED | READY |
| REQ-269 | §5.6 | Use the exact synthetic ledger identities for client_id, action_channel_id, epoch_id, event_id, issue_age_unit, and maturity_age_unit. | Dataset | — | — | Ledger-format tests. | UNMAPPED | READY |
| REQ-270 | §5.6 | For finite band k set adjudication_completion_age=t+H_k and correctness_label to sampled L; for unresolved set both adjudication completion and correctness label to null. | Dataset | — | — | Ledger-row tests. | UNMAPPED | READY |
| REQ-271 | §5.6 | Insert synthetic events inferentially only at maturity. | Preprocessing | — | — | Pipeline chronology tests. | UNMAPPED | READY |
| REQ-272 | §5.7 | Restrict synthetic preprocessing to the nine listed operations: schema validation, normalization verification, duplicate rejection, finite/range verification, deterministic trajectory construction, deterministic coarsening, canonical sorting, checksumming, and law-manifest generation. | Preprocessing | — | — | Pipeline step audit and tests. | UNMAPPED | READY |
| REQ-273 | §5.7 | Do not perform normalization, imputation, feature scaling, train/validation/test split, duplicate collapsing, label remapping, or learned preprocessing. | Preprocessing | — | — | Negative architecture/pipeline tests. | UNMAPPED | READY |
| REQ-274 | §5.7 | Require probability sums to equal one within scientific_comparison_guard. | Preprocessing | — | — | Probability-validation tests. | UNMAPPED | READY |
| REQ-275 | §5.7 | Invalidate preprocessing on NaN, infinity, duplicate ID, impossible category, invalid label, or probability outside [0,1]. | Failure Semantics | — | — | Parameterized invalid-input tests. | UNMAPPED | READY |
| REQ-276 | §5.8 | Use Hamilton apportionment whenever deterministic finite-sample construction converts target category probabilities to integer counts. | Algorithm | — | — | Apportionment tests. | UNMAPPED | READY |
| REQ-277 | §5.8 | Use the exact canonical category order (1,1),(1,0),(2,1),(2,0),...,infinity for apportionment and ties. | Reproducibility | — | — | Tie-order tests. | UNMAPPED | READY |
| REQ-278 | §5.8 | Implement Hamilton quotas/floors/remainder assignment exactly and break equal fractional-remainder ties by canonical category order. | Algorithm | — | — | Exact apportionment fixtures. | UNMAPPED | READY |
| REQ-279 | §5.8 | Implement the deterministic balanced-prefix construction using the stated argmax deficit rule and canonical tie-breaking. | Algorithm | — | — | Balanced-prefix property tests. | UNMAPPED | READY |
| REQ-280 | §5.8 | When starting from exact terminal counts, derive probabilities as counts/n, apply balanced-prefix, and invalidate preprocessing if the final prefix does not reproduce the supplied exact counts. | Preprocessing | — | — | Exact-count reconstruction tests. | UNMAPPED | READY |
| REQ-281 | §6 | For every external dataset record both documented_expected_value and observed_raw_dataset_value. | Dataset | — | — | Dataset manifest schema. | UNMAPPED | READY |
| REQ-282 | §6 | Use official documentation and primary publication for expected release semantics, but treat execution-time raw files as authoritative for observed filenames/counts/entity counts/schemas/available fields. | Dataset | — | — | Expected-vs-observed inventory evidence. | UNMAPPED | READY |
| REQ-283 | §6 | Persist exactly the listed dataset inventory fields including source/references/checksum/counts/schema/labels/times/entities/exclusions/discrepancy/mapping/eligibility. | Artifact | — | — | Dataset inventory schema validation. | UNMAPPED | READY |
| REQ-284 | §6 | Never assume dataset-specific counts, schema, features, timestamps, client identity, or row totals solely from documentation. | Dataset | — | — | Dataset validation policy test. | UNMAPPED | READY |
| REQ-285 | §6 | When raw data differ from documentation preserve both values and determine semantic equivalence of observed vs required fields. | Dataset | — | — | Discrepancy handling tests. | UNMAPPED | READY |
| REQ-286 | §6 | When a raw field is semantically equivalent, record the deterministic mapping and use the observed field. | Dataset | — | — | Field-mapping manifest tests. | UNMAPPED | READY |
| REQ-287 | §6 | Adapt physical discovery/column types/file counts/row counts to the actual release without changing scientific event semantics. | Dataset | — | — | Dataset adapter validation. | UNMAPPED | READY |
| REQ-288 | §6 | Never fabricate missing action identity, adjudication timing, correctness, terminal status, or stream identity. | Dataset | — | — | Eligibility negative tests. | UNMAPPED | READY |
| REQ-289 | §6 | Mark a dataset INELIGIBLE when a required scientific semantic cannot be established from raw source. | Failure Semantics | — | — | Dataset eligibility tests. | UNMAPPED | READY |
| REQ-290 | §6 | Never silently substitute unrelated timestamps, derived pseudo-clients, reconstructed verdicts, or inferred terminal status. | Dataset | — | — | Negative mapping tests. | UNMAPPED | READY |
| REQ-291 | §6 | Set current real-trajectory planning status exactly to NOT_IN_CURRENT_CONFIRMATORY_PLAN. | Configuration | — | — | Registry/status validation. | UNMAPPED | READY |
| REQ-292 | §6 | Use only the synthetic benchmark for current confirmatory execution; Real-Trajectory Validation must be a zero-cell nonapplicability and Real-Trajectory Value must remain NOT_TESTED. | Experiment | — | — | Registry and claim-state validation. | UNMAPPED | READY |
| REQ-293 | §6 | Require generated and expected synthetic probability tables to agree within deterministic numerical tolerance. | Evaluation | — | — | Synthetic inventory validation. | UNMAPPED | READY |
| REQ-294 | §6 | A future real study is eligible only if all eight listed same-action ledger semantics are present and provenance proves adjudication time is not an event/capture timestamp. | Dataset | — | — | Eligibility checklist/manifests. | UNMAPPED | READY |
| REQ-295 | §6 | Treat any future real study as a separate study that does not alter the current synthetic registry. | Claim Boundary | — | — | Registry guard. | NON_IMPLEMENTATION | READY |
| REQ-296 | §7.1 | Implement complete-case arrival-only estimate A/(A+G) when A+G>0, ignoring unresolved mass, and label it an optimistic descriptive reference rather than a PIS certificate. | Comparator | — | — | Baseline numerical and reporting tests. | UNMAPPED | READY |
| REQ-297 | §7.2 | Implement unresolved-as-harm worst-case upper risk A+c as assumption-free. | Comparator | — | — | Baseline numerical tests. | UNMAPPED | READY |
| REQ-298 | §7.3 | Implement endpoint-only path-information baseline by merging all finite bands to K=1 while keeping the same numerical rho. | Comparator | — | — | Coarsening/baseline tests. | UNMAPPED | READY |
| REQ-299 | §7.4 | Implement A_k^+ and B_k^+ tail masses and the exact legacy response-hazard odds ratio psi_k(u). | Comparator | — | — | Analytic formula tests. | UNMAPPED | READY |
| REQ-300 | §7.4 | Classify bands with both outcome-specific response hazards structurally zero as UNINFORMATIVE_BAND and omit them from the all-band constraint. | Failure Semantics | — | — | Structural-zero tests. | UNMAPPED | READY |
| REQ-301 | §7.4 | Use exact extended-real limits for other structural-zero legacy cases. | Comparator | — | — | Boundary comparator tests. | UNMAPPED | READY |
| REQ-302 | §7.4 | Enforce Gamma^{-1}<=psi_k(u)<=Gamma for every informative legacy band. | Comparator | — | — | Feasibility tests. | UNMAPPED | READY |
| REQ-303 | §7.4 | Report no universal mapping between Gamma and rho. | Claim Boundary | — | — | Comparator reporting audit. | NON_IMPLEMENTATION | READY |
| REQ-304 | §7.4 | Solve the legacy feasible interval analytically from linear-rational inequalities with exact boundary limits; do not use a numerical-optimizer default. | Algorithm | — | — | Legacy solver tests/implementation audit. | UNMAPPED | READY |
| REQ-305 | §7.4.1 | For every configured (Gamma,q), construct the two-band full law with P(L=1)=P(L=0)=0.5 and hazards defined by T(q,gamma) exactly as specified. | Experiment | — | — | Counterexample fixture validation. | UNMAPPED | READY |
| REQ-306 | §7.4.1 | Require the fine two-band legacy model to contain the true hidden completion with psi1=Gamma and psi2=Gamma^{-1}. | Evaluation | — | — | Counterexample theorem check. | UNMAPPED | READY |
| REQ-307 | §7.4.1 | Coarsen the same observable law to endpoint-only and evaluate under identical numerical Gamma. | Experiment | — | — | Paired counterexample records. | UNMAPPED | READY |
| REQ-308 | §7.4.1 | Pass the legacy incoherence counterexample only when true hidden mass is fine-feasible, fine and endpoint feasible sets differ, and endpoint difference exceeds deterministic_identity_tolerance; report direction/magnitude but require only non-invariance. | Evaluation | — | — | Counterexample pass/fail record. | UNMAPPED | READY |
| REQ-309 | §7.5 | Implement ALHO common-slope callback using g_k=log psi_k over finite positive informative bands and Q(u)=sum(g_k-gbar)^2. | Comparator | — | — | Callback formula tests. | UNMAPPED | READY |
| REQ-310 | §7.5 | Classify ALHO compatibility only when an accepted root satisfies Q<=callback_q_acceptance. | Comparator | — | — | Acceptance-threshold tests. | UNMAPPED | READY |
| REQ-311 | §7.5 | Use exactly the prescribed 100-decimal-digit grid/local-minimum/golden-section algorithm, stopping width, acceptance, sorting, and deduplication semantics for ALHO. | Algorithm | — | — | Deterministic callback algorithm tests. | UNMAPPED | READY |
| REQ-312 | §7.5 | Return MODEL_INCOMPATIBLE when ALHO has no accepted root and use the convex hull of A+u over accepted roots as its risk set. | Comparator | — | — | No-root/multi-root tests. | UNMAPPED | READY |
| REQ-313 | §7.5 | Return NOT_APPLICABLE for ALHO when fewer than two informative bands remain. | Failure Semantics | — | — | Applicability tests. | UNMAPPED | READY |
| REQ-314 | §7.6 | Implement stable-resistance callback with log psi1(u)=log psi2(u), residual E(u), the same high-precision search, callback_equality_tolerance acceptance, sorting, and deduplication. | Comparator | — | — | Stable-resistance callback tests. | UNMAPPED | READY |
| REQ-315 | §7.6 | Treat attempts after the second as adding no identifying equality restriction and return NOT_APPLICABLE when K<2. | Comparator | — | — | Applicability/restriction tests. | UNMAPPED | READY |
| REQ-316 | §7.7 | Fit the repeated-attempt pattern-mixture logit model logit(r_k)=zeta0+zeta1 k over nonempty finite bands using weighted Bernoulli cross-entropy weights m_k and fixed L-BFGS-B. | Comparator | — | — | Fit objective/optimizer tests. | UNMAPPED | READY |
| REQ-317 | §7.7 | Use the configured coefficient bounds/tolerances/iterations, initial zeta1=0, and clipped complete-case logit initialization for zeta0. | Comparator | — | — | Initialization/configuration tests. | UNMAPPED | READY |
| REQ-318 | §7.7 | Declare pattern-mixture fit successful only when convergence, gradient norm, finite objective/gradient, and bound-distance conditions all pass; otherwise return BASELINE_NUMERICALLY_UNSTABLE. | Failure Semantics | — | — | Failure-mode tests. | UNMAPPED | READY |
| REQ-319 | §7.7 | For each sensitivity C compute r_infinity(C)=expit(zeta0+zeta1(K+C)) and theta(C)=A+c*r_infinity(C). | Comparator | — | — | Numerical formula tests. | UNMAPPED | READY |
| REQ-320 | §7.7 | Return NOT_APPLICABLE for pattern mixture with fewer than two nonempty finite bands. | Failure Semantics | — | — | Applicability tests. | UNMAPPED | READY |
| REQ-321 | §7.8 | Implement an independent generic full-law information oracle using direct 2x(K+1) mutual information with exact zero-cell limits. | Comparator | — | — | Oracle-vs-independent direct-table tests. | UNMAPPED | READY |
| REQ-322 | §7.8 | Keep the oracle structurally independent of production information-profile, derivatives, minimizer, and production root solver. | Architecture | — | — | Static dependency test. | UNMAPPED | READY |
| REQ-323 | §7.8 | Use exactly mpmath oracle_decimal_digits precision and oracle_boundary_bracket_width. | Comparator | — | — | Precision configuration tests. | UNMAPPED | READY |
| REQ-324 | §7.8 | Use the specified independent golden-section minimum, derived epsilon_oracle, incompatibility/singleton classification, and separate left/right direct-table bisection algorithm. | Algorithm | — | — | Oracle branch tests. | UNMAPPED | READY |
| REQ-325 | §7.8 | Require production endpoints to agree with oracle endpoints within deterministic_identity_tolerance. | Evaluation | — | — | Solver-oracle validation. | UNMAPPED | READY |
| REQ-326 | §7.9 | Implement the generic time-uniform observable-law projection as the Section 9 bound-producing core and expose distinct reporting roles for `TrajCert` and `Time-uniform observable-law projection`. | Comparator | — | — | Method-label/state reporting tests. | UNMAPPED | READY |
| REQ-327 | §7.9 | Share U_n(rho) computation by dependency identity between those two labels and never recompute it redundantly just because both labels are reported. | Reproducibility | — | — | Artifact-reuse tests. | UNMAPPED | READY |
| REQ-328 | §7.9 | Make no sequential-method novelty claim. | Claim Boundary | — | — | Claim audit. | NON_IMPLEMENTATION | READY |
| REQ-329 | §7.10 | Implement the repeated-static-monitoring negative control using per-category Wilson intervals at two-sided level 1-delta/d, Bonferroni across categories at each n, and no across-time correction. | Comparator | — | — | Wilson reference calculation tests. | UNMAPPED | READY |
| REQ-330 | §7.10 | Clip only Wilson interval endpoints to [0,1] and project each time point through the same outer routine. | Comparator | — | — | Boundary/reference tests. | UNMAPPED | READY |
| REQ-331 | §7.10 | Treat repeated-static monitoring as deliberately invalid under continuous monitoring and never allow it to support deployment. | Claim Boundary | — | — | Claim/method-ranking tests. | NON_IMPLEMENTATION | READY |
| REQ-332 | §7.11 | Implement the ignorable-delay anytime reference only under L independent of J, using the Section 9.2 Jeffreys beta-binomial mixture CS on resolved labels among matured events. | Comparator | — | — | Reference-method tests. | UNMAPPED | READY |
| REQ-333 | §7.11 | Update the ignorable-delay Bernoulli CS only on resolved labels, retain the prior CS on unresolved updates, and use its upper endpoint as risk upper under the ignorable assumption. | Comparator | — | — | Update-sequence tests. | UNMAPPED | READY |
| REQ-334 | §7.11 | Apply the same evidence-count gates to the ignorable-delay reference. | Comparator | — | — | Evidence-gate tests. | UNMAPPED | READY |
| REQ-335 | §7.11 | Mark the ignorable-delay reference ASSUMPTION_VIOLATED and exclude it from valid-method ranking in outcome-dependent cells. | Failure Semantics | — | — | Assumption/applicability tests. | UNMAPPED | READY |
| REQ-336 | §7.12 | Provide exactly the three ablations: Endpoint-only path information; Same Endpoint, Different Timing; rho=log(2). | Ablation | — | — | Registry validation. | UNMAPPED | READY |
| REQ-337 | §7.12 | Use exact binary maximum-information budget log(2) for the third ablation so the PIS restriction is effectively removed for binary L. | Ablation | — | — | Exact-symbolic endpoint tests. | UNMAPPED | READY |
| REQ-338 | §8 | Define metric `Latent error risk` exactly as `theta=A+u` with roadmap direction `lower safer`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Latent error risk`. | UNMAPPED | READY |
| REQ-339 | §8 | Define metric `Observed timing information` exactly as `tau` with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Observed timing information`. | UNMAPPED | READY |
| REQ-340 | §8 | Define metric `Conditional timing gain` exactly as `Delta tau` with roadmap direction `larger indicates more timing information`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Conditional timing gain`. | UNMAPPED | READY |
| REQ-341 | §8 | Define metric `Minimum compatible sensitivity budget` exactly as `tau` with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Minimum compatible sensitivity budget`. | UNMAPPED | READY |
| REQ-342 | §8 | Define metric `Minimum-information risk` exactly as `theta_dagger` with roadmap direction `lower safer`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Minimum-information risk`. | UNMAPPED | READY |
| REQ-343 | §8 | Define metric `Risk lower bound` exactly as `A+u_L` with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Risk lower bound`. | UNMAPPED | READY |
| REQ-344 | §8 | Define metric `Risk upper bound` exactly as `A+u_U` with roadmap direction `lower better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Risk upper bound`. | UNMAPPED | READY |
| REQ-345 | §8 | Define metric `Identified-set width` exactly as `u_U-u_L` with roadmap direction `lower tighter`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Identified-set width`. | UNMAPPED | READY |
| REQ-346 | §8 | Define metric `Safety-frontier sensitivity budget` exactly as `rho_star` with roadmap direction `larger more robust`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Safety-frontier sensitivity budget`. | UNMAPPED | READY |
| REQ-347 | §8 | Define metric `Anytime upper risk` exactly as proven `U_n(rho)` with roadmap direction `lower better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Anytime upper risk`. | UNMAPPED | READY |
| REQ-348 | §8 | Define metric `Anytime compatibility floor` exactly as certified lower envelope of `tau` with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Anytime compatibility floor`. | UNMAPPED | READY |
| REQ-349 | §8 | Define metric `Ever-violation indicator` exactly as `1{exists n: theta>U_n}` with roadmap direction `lower`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Ever-violation indicator`. | UNMAPPED | READY |
| REQ-350 | §8 | Define metric `Bound gain versus endpoint-only` exactly as endpoint upper minus fine upper with roadmap direction `higher better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Bound gain versus endpoint-only`. | UNMAPPED | READY |
| REQ-351 | §8 | Define metric `Absolute tightening versus unresolved-as-harm` exactly as `(A+c)-theta_U` with roadmap direction `higher better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Absolute tightening versus unresolved-as-harm`. | UNMAPPED | READY |
| REQ-352 | §8 | Define metric `Relative unresolved-mass gain` exactly as `((A+c)-theta_U)/c` with roadmap direction `higher better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Relative unresolved-mass gain`. | UNMAPPED | READY |
| REQ-353 | §8 | Define metric `Time to first certification` exactly as first eligible certified `n` with roadmap direction `lower better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Time to first certification`. | UNMAPPED | READY |
| REQ-354 | §8 | Define metric `Certified update fraction` exactly as certified eligible updates / eligible updates with roadmap direction `higher better`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Certified update fraction`. | UNMAPPED | READY |
| REQ-355 | §8 | Define metric `State frequency` exactly as state count / eligible updates with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `State frequency`. | UNMAPPED | READY |
| REQ-356 | §8 | Define metric `Compatibility-budget consumption` exactly as `tau/rho` with roadmap direction `descriptive`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Compatibility-budget consumption`. | UNMAPPED | READY |
| REQ-357 | §8 | Define metric `Oracle absolute error` exactly as production-oracle absolute difference with roadmap direction `lower`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Oracle absolute error`. | UNMAPPED | READY |
| REQ-358 | §8 | Define metric `Runtime seconds` exactly as monotonic elapsed target-computation time with roadmap direction `lower`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Runtime seconds`. | UNMAPPED | READY |
| REQ-359 | §8 | Define metric `Peak RSS MiB` exactly as peak resident memory with roadmap direction `lower`. | Metric | — | — | Metric unit tests and schema/report source evidence for `Peak RSS MiB`. | UNMAPPED | READY |
| REQ-360 | §8 | For numeric comparison statistics assign never-certified streams N_max+1 for Time to first certification, while storing raw first_certified_n=null and never_certified=true. | Metric | — | — | Never-certified metric tests. | UNMAPPED | READY |
| REQ-361 | §8 | Define eligible updates as evidence-gate-passed, data/technical-valid updates in substantive states; exclude INSUFFICIENT_EVIDENCE from the certified-update-fraction denominator. | Metric | — | — | Denominator/state tests. | UNMAPPED | READY |
| REQ-362 | §8.1 | When A+G=0 store tau, u_dagger, and theta_dagger as null and do not assign a finite-sample substantive state. | Failure Semantics | — | — | Zero-resolved-mass tests. | UNMAPPED | READY |
| REQ-363 | §8.1 | When c=0 set u=0 and risk set={A}. | Mathematics | — | — | No-unresolved-mass tests. | UNMAPPED | READY |
| REQ-364 | §8.1 | When m_k=0 store r_k=null and entropy contribution 0. | Metric | — | — | Empty-band tests. | UNMAPPED | READY |
| REQ-365 | §8.1 | When rho=0 store Compatibility-budget consumption as null. | Metric | — | — | Division-by-zero semantic test. | UNMAPPED | READY |
| REQ-366 | §8.1 | When c=0 store Relative unresolved-mass gain as null. | Metric | — | — | Undefined-gain test. | UNMAPPED | READY |
| REQ-367 | §8.1 | Store undefined scientific quantities as null and forbid NaN/+inf/-inf in claim-bearing numeric fields; represent exceptional states explicitly instead. | Artifact | — | — | Schema serialization tests. | UNMAPPED | READY |
| REQ-368 | §8.1 | Do not treat detector AUC, F1, TPR, FPR, calibration, privacy, communication, or energy metrics as claim-bearing. | Claim Boundary | — | — | Reporting/claim registry audit. | NON_IMPLEMENTATION | READY |
| REQ-369 | §9.1 | Use the exact independent unit definitions for theorem identities, production/oracle cells, anytime streams, paired utility streams, runtime invocations, and future real streams. | Statistical Analysis | — | — | Experiment/statistics schema validation. | UNMAPPED | READY |
| REQ-370 | §9.1 | Never treat monitoring times within one stream or optimizer evaluations as independent replicates. | Statistical Analysis | — | — | Aggregation unit tests. | UNMAPPED | READY |
| REQ-371 | §9.2 | For K finite bands use d=2K+1 categorical CS categories in exact canonical order and per-category alpha_j=delta/d. | Statistical Analysis | — | — | CS configuration tests. | UNMAPPED | READY |
| REQ-372 | §9.2 | Compute log Jeffreys beta-binomial mixture M_{j,n}(p) exactly as specified using betaln. | Statistical Analysis | — | — | Reference numerical tests. | UNMAPPED | READY |
| REQ-373 | §9.2 | Define raw CS set by strict log M < log(d/delta) and store its closure conservatively. | Statistical Analysis | — | — | Boundary equality tests. | UNMAPPED | READY |
| REQ-374 | §9.2 | Use exact p=0/1 limiting likelihood values and never numerically evaluate log(0). | Algorithm | — | — | Endpoint inversion tests. | UNMAPPED | READY |
| REQ-375 | §9.2 | For each non-boundary endpoint maintain sign-valid bisection brackets and stop only at anytime_category_root_tolerance. | Algorithm | — | — | Root-bracket tests. | UNMAPPED | READY |
| REQ-376 | §9.2 | Store outward CS endpoints using the lower coordinate of the lower-root bracket and upper coordinate of the upper-root bracket, using exact 0/1 when touched; never store inward midpoints. | Statistical Analysis | — | — | Coverage-oriented endpoint tests. | UNMAPPED | READY |
| REQ-377 | §9.2 | Maintain running CS intersections by max previous/current lower and min previous/current upper. | Statistical Analysis | — | — | Sequential intersection tests. | UNMAPPED | READY |
| REQ-378 | §9.2 | Intersect category intervals with the simplex and test rectangular simplex feasibility by sum lower <=1<=sum upper. | Statistical Analysis | — | — | Simplex-feasibility tests. | UNMAPPED | READY |
| REQ-379 | §9.2 | Update the monitor at every matured event and forbid favorable early stopping. | Statistical Analysis | — | — | Stream execution tests. | UNMAPPED | READY |
| REQ-380 | §9.2 | Treat an unexpectedly empty rectangle/simplex intersection after valid CS construction as TECHNICAL_FAIL and execution FAILED. | Failure Semantics | — | — | Empty-region failure tests. | UNMAPPED | READY |
| REQ-381 | §9.3 | Compute conservative summary envelope bounds A_L/A_U, G_L/G_U, c via 1-A-G plus terminal interval, and C_L/C_U using q(a,b) exactly as specified. | Statistical Analysis | — | — | Envelope reference tests. | UNMAPPED | READY |
| REQ-382 | §9.3 | Use the exact E_n set over A,G,c,C and claim finite-sample validity rather than shortest possible width. | Claim Boundary | — | — | Envelope schema/claim audit. | NON_IMPLEMENTATION | READY |
| REQ-383 | §9.4 | Define certified outer upper risk U_n(rho) as the stated supremum over E_n,u with S<=rho, and set C=C_U because S decreases in C. | Algorithm | — | — | Projection reference tests. | UNMAPPED | READY |
| REQ-384 | §9.4 | Use Arb interval/ball arithmetic through python-flint at exactly outer_minimum_arbitrary_precision_bits bits for authoritative projection. | Algorithm | — | — | Environment/numerical tests. | UNMAPPED | READY |
| REQ-385 | §9.4 | On indeterminate interval arithmetic at that precision use conservative fallback rather than silently increasing precision. | Failure Semantics | — | — | Forced-ambiguity tests. | UNMAPPED | READY |
| REQ-386 | §9.4 | Initialize outer branch-and-bound on A,G,u domains and enforce all simplex, terminal interval, and 0<=u<=c constraints. | Algorithm | — | — | Feasible-domain tests. | UNMAPPED | READY |
| REQ-387 | §9.4 | Split boxes crossing c=0 at c=0 before terminal entropy evaluation and use exact continuous boundary entropy extensions. | Algorithm | — | — | Boundary-box tests. | UNMAPPED | READY |
| REQ-388 | §9.4 | Prune boxes only when interval lower bound of S exceeds rho and use min(1,A_hi+u_hi) as objective upper bound. | Algorithm | — | — | Pruning/upper-bound tests. | UNMAPPED | READY |
| REQ-389 | §9.4 | Generate midpoint feasible incumbents and compute maximal feasible u via deterministic upper-branch bisection with population root tolerance; accept only when direct Arb upper S<=rho. | Algorithm | — | — | Incumbent verification tests. | UNMAPPED | READY |
| REQ-390 | §9.4 | Split the longest normalized-width coordinate with zero-width normalization and A,G,u tie order within outer_split_tie_tolerance. | Algorithm | — | — | Deterministic splitting tests. | UNMAPPED | READY |
| REQ-391 | §9.4 | Stop outer projection when queue proven upper minus best verified feasible incumbent <= outer_certified_gap or node cap reached. | Algorithm | — | — | Termination tests. | UNMAPPED | READY |
| REQ-392 | §9.4 | On node cap, arithmetic failure, or unresolved ambiguity return current proven queue upper, or 1.0 if none; never return feasible incumbent as certified upper. | Failure Semantics | — | — | Conservative fallback tests. | UNMAPPED | READY |
| REQ-393 | §9.4 | Record initial envelope, precision, visited nodes, surviving boxes, feasible incumbent, proven upper, final gap, and termination reason at every update. | Artifact | — | — | Projection diagnostic schema tests. | UNMAPPED | READY |
| REQ-394 | §9.5 | Compute finite-sample compatibility lower bound as inf tau(A,G,C) over E_n with C=C_U. | Statistical Analysis | — | — | Compatibility optimizer tests. | UNMAPPED | READY |
| REQ-395 | §9.5 | Use deterministic Arb branch-and-bound over A,G with exact constraints, global_lower/feasible_upper bookkeeping, A-then-G normalized-width splitting, shared gap/cap/precision, and conservative global_lower return on cap/ambiguity. | Algorithm | — | — | Compatibility optimizer deterministic/fallback tests. | UNMAPPED | READY |
| REQ-396 | §9.5 | Assign MODEL_INCOMPATIBLE only when proven rho_comp_lower > rho_deploy + scientific_comparison_guard. | Failure Semantics | — | — | Threshold boundary tests. | UNMAPPED | READY |
| REQ-397 | §9.6 | Compute finite-sample intrinsic-impossibility lower bound over the compatible subset using theta_dagger(A,G)=A/(A+G). | Statistical Analysis | — | — | Intrinsic optimizer tests. | UNMAPPED | READY |
| REQ-398 | §9.6 | Use the specified Arb branch-and-bound over A,G,u, pruning incompatible boxes and tracking zero_resolved_mass_plausible when a surviving box includes A+G=0. | Algorithm | — | — | Intrinsic optimizer tests. | UNMAPPED | READY |
| REQ-399 | §9.6 | Withhold strong intrinsic state whenever zero_resolved_mass_plausible=true; otherwise use the minimum surviving lower endpoint as proven lower bound with stated split order/gap/cap/fallback. | Failure Semantics | — | — | Zero-mass and cap tests. | UNMAPPED | READY |
| REQ-400 | §9.6 | Assign INTRINSICALLY_UNCERTIFIABLE only after evidence gates, zero_resolved_mass_plausible=false, and theta_dagger_lower > beta + guard. | Failure Semantics | — | — | State-threshold tests. | UNMAPPED | READY |
| REQ-401 | §9.7 | Apply failure precedence exactly: data/manifest invalidity -> INVALID/no scientific state; technical/numerical invalidity -> FAILED/TECHNICAL_FAIL/no scientific state; then evidence-count gate; then substantive state. | Failure Semantics | — | — | Comprehensive precedence table tests. | UNMAPPED | READY |
| REQ-402 | §9.7 | Classify ledger/epoch-manifest integrity failures, invalid probability/simplex input, duplicate semantic identity, and authoritative-input schema violations as INVALID. | Failure Semantics | — | — | Parameterized invalidity tests. | UNMAPPED | READY |
| REQ-403 | §9.7 | Classify unexpected empty simultaneous region, arithmetic exception, corrupt artifact, unresolved interval failure without fallback, serialization/checksum failure, and implementation invariant violation as FAILED/TECHNICAL_FAIL. | Failure Semantics | — | — | Parameterized technical-failure tests. | UNMAPPED | READY |
| REQ-404 | §9.7 | Require n_matured>=200, n_resolved>=50, and nonempty simultaneous confidence region before substantive state; otherwise assign INSUFFICIENT_EVIDENCE, with no separate harmful-event minimum. | Failure Semantics | — | — | Evidence-gate boundary tests. | UNMAPPED | READY |
| REQ-405 | §9.7 | After preceding gates, assign substantive states in exact order: MODEL_INCOMPATIBLE, INTRINSICALLY_UNCERTIFIABLE, CERTIFIED if U_n<=beta, otherwise UNCERTIFIED. | Failure Semantics | — | — | State precedence tests. | UNMAPPED | READY |
| REQ-406 | §9.8 | Compute exact one-sided Clopper-Pearson upper limit with configured confidence and exact beta-quantile arguments, including v=m -> 1. | Statistical Analysis | — | — | Reference CP tests. | UNMAPPED | READY |
| REQ-407 | §9.8 | Require every configured primary TrajCert coverage stress cell to have CP upper <= acceptance_upper_limit; keep delta as theoretical target and acceptance limit as Monte Carlo validation tolerance only. | Evaluation | — | — | Coverage aggregate gate. | UNMAPPED | READY |
| REQ-408 | §9.9 | Define favorable paired differences with baseline-method orientation for upper-risk/time-to-certification and method-baseline for certified fraction so positive always favors TrajCert. | Statistical Analysis | — | — | Paired-difference tests. | UNMAPPED | READY |
| REQ-409 | §9.9 | Report mean paired difference, sample SD with n-1, d_z when SD>0, percentile-bootstrap CI, and one-sided favorable sign-flip p-value. | Statistical Analysis | — | — | Statistics artifact validation. | UNMAPPED | READY |
| REQ-410 | §9.9 | Implement paired bootstrap with exact semantic namespace, seed index 0, PCG64, configured 10000 resamples, pair-index resampling, sorted means, and linear quantiles at (B-1)q. | Statistical Analysis | — | — | Deterministic bootstrap tests. | UNMAPPED | READY |
| REQ-411 | §9.9 | Implement sign-flip test with exact statistic, semantic namespace, seed index 0, configured 20000 randomizations, iid +/-1 signs, and plus-one p-value formula. | Statistical Analysis | — | — | Deterministic sign-flip tests. | UNMAPPED | READY |
| REQ-412 | §9.9 | Handle effect-size edges exactly: all-zero differences -> standardized_effect=0/FINITE; SD=0 with nonzero mean -> null effect with POSITIVE_INFINITY or NEGATIVE_INFINITY status. | Statistical Analysis | — | — | Degenerate effect tests. | UNMAPPED | READY |
| REQ-413 | §9.9 | Construct the Trajectory operational gain Holm family as exactly 54 tests from 6 laws x 3 rho x 3 metrics. | Statistical Analysis | — | — | Multiplicity-family cardinality test. | UNMAPPED | READY |
| REQ-414 | §9.9 | Apply Holm adjustment with ascending raw p, ties by semantic_comparison_name then metric_name, cumulative maximum formula, mapping back to records, and alpha=confirmatory_alpha. | Statistical Analysis | — | — | Holm tie/reference tests. | UNMAPPED | READY |
| REQ-415 | §9.10 | Never delete failed stochastic seeds, substitute seeds, restrict analysis to successful streams, or treat scientific nulls as failures; rerun technical interruptions with same semantic cell/seeds; retain planned invalid combinations in plan but exclude them from executable totals. | Reproducibility | — | — | Failure/recovery/statistics integration tests. | UNMAPPED | READY |
| REQ-416 | §9.11 | Derive every stochastic seed from SHA256(`TrajCert\|`+namespace+`\|`+decimal(index)) first 8 bytes big-endian uint64 mod 2^63. | Reproducibility | — | — | Seed derivation test vectors. | UNMAPPED | READY |
| REQ-417 | §9.11 | Use exactly the seven namespace roles and the exact current Event stream, Bootstrap, and Permutation namespace constructions; keep unused roles reserved until genuinely consumed. | Reproducibility | — | — | Namespace construction tests. | UNMAPPED | READY |
| REQ-418 | §9.11 | Exclude experiment name, role, requested prefix length, rho, beta, and method from event-stream namespace so compatible consumers share streams/prefixes. | Reproducibility | — | — | Stream-identity tests. | UNMAPPED | READY |
| REQ-419 | §9.11 | Use seed index 0 per unique bootstrap/permutation comparison namespace and configured stream seed index for event streams. | Reproducibility | — | — | Seed manifest tests. | UNMAPPED | READY |
| REQ-420 | §9.11 | Pair compared methods by sharing the same event-stream artifact, not merely numerically equal seeds. | Reproducibility | — | — | Parent-artifact identity tests. | UNMAPPED | READY |
| REQ-421 | §9.11 | Use exactly numpy.random.Generator(numpy.random.PCG64(seed)) and forbid module-global RNGs. | Reproducibility | — | — | Static RNG audit and deterministic tests. | UNMAPPED | READY |
| REQ-422 | §10 | Implement the required repository/project structure and named modules/directories in Section 10. | Architecture | — | — | Architecture tree test verifies required structure. | UNMAPPED | READY |
| REQ-423 | §10 | Keep configuration responsibilities in configuration models/loading/validation/protocol exactly as described. | Architecture | — | — | Dependency/responsibility architecture tests. | UNMAPPED | READY |
| REQ-424 | §10 | Keep immutable operational identities, enums, schemas, manifests, artifact/dependency/execution/result/claim records in domain. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-425 | §10 | Keep population mathematics pure and filesystem-side-effect-free in math. | Architecture | — | — | Dependency/side-effect tests. | UNMAPPED | READY |
| REQ-426 | §10 | Keep confidence sequences, envelope, certified projection, compatibility/intrinsic calculations, and state assignment in inference. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-427 | §10 | Keep synthetic laws/partitions/preprocessing/integrity/streams/apportionment/coarsening in data. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-428 | §10 | Keep comparator/reference implementations only in baselines. | Architecture | — | — | Dependency/responsibility tests. | UNMAPPED | READY |
| REQ-429 | §10 | Keep registry expansion, semantic-cell lifecycle, dependency resolution, invalidation, recovery, idempotency, completion, and experiment contracts in experiments. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-430 | §10 | Keep theorem/oracle/coverage/projection validation and isolated benchmarking in evaluation. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-431 | §10 | Keep metrics/statistics/materiality/claims/evidence/synthesis in analysis. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-432 | §10 | Keep workspace/storage/digests/artifact validation/atomic promotion/provenance/environment/evidence manifests/diagnostics in infrastructure. | Architecture | — | — | Module responsibility tests. | UNMAPPED | READY |
| REQ-433 | §10 | Keep reporting as deterministic render/export of verified evidence with no scientific recomputation. | Architecture | — | — | Reporting dependency tests. | UNMAPPED | READY |
| REQ-434 | §10 | Keep CLI limited to public command dispatch/command implementations from Section 16. | Architecture | — | — | CLI architecture tests. | UNMAPPED | READY |
| REQ-435 | §10 | Keep the generic full-law oracle structurally independent of the production information-profile/population solver. | Architecture | — | — | Import/dependency independence test. | UNMAPPED | READY |
| REQ-436 | §10 | Implement the full required test tree including architecture, unit, scientific, integration, e2e, and smoke tests named in Section 10. | Testing | — | — | Test-tree architecture validation. | UNMAPPED | READY |
| REQ-437 | §10 | Enforce the roadmap-listed architecture governance tests, including no inappropriate Any/dicts/primitives/hardcoded values/duplicate constants/dead code/unused enums/test-only production code/redirects or shims/generic naming/stale vocabulary/comments-docstrings/TODOs and mandatory static quality/dependency hygiene. | Testing | — | — | Architecture test suite passes. | UNMAPPED | READY |
| REQ-438 | §10 | Resolve the required project-tree roadmap path `docs/Roadmap.md` against the repository's immutable authoritative roadmap currently stored as `docs/TrajCert_Roadmap.md` without duplicating or weakening roadmap authority. | Architecture | — | — | Clarification decision and architecture-path test. | UNMAPPED | AMBIGUOUS |
| REQ-439 | §11 | Root the computational workspace at configured outputs and implement exactly the declared workspace layout. | Artifact | — | — | Workspace path tests. | UNMAPPED | READY |
| REQ-440 | §11 | Store preprocessing outputs under outputs/preprocessing and project-wide reusable artifacts under exactly one canonical producer/path in outputs/artifacts. | Artifact | — | — | Artifact-owner/path validation. | UNMAPPED | READY |
| REQ-441 | §11 | Store experiment-owned products only under outputs/experiments/<descriptive-experiment-name>/ with the declared sublayout. | Artifact | — | — | Experiment artifact layout tests. | UNMAPPED | READY |
| REQ-442 | §11 | Use descriptive semantic coordinates in active cell paths; do not create an execution-phase directory. | Artifact | — | — | Path rendering tests. | UNMAPPED | READY |
| REQ-443 | §11.1 | Canonicalize all digest-bearing JSON according to RFC 8785 JCS using one internal implementation with RFC-derived regression vectors. | Provenance | — | — | Canonicalization test vectors. | UNMAPPED | READY |
| REQ-444 | §11.1 | Forbid duplicate JSON keys, NaN, and infinities in digest-bearing JSON; use finite binary64 runtime values and semantic string tokens for exact symbolic constants while storing evaluated numeric values separately. | Artifact | — | — | Serialization schema tests. | UNMAPPED | READY |
| REQ-445 | §11.1 | Preserve scientific array order and canonicalize object keys according to RFC 8785. | Reproducibility | — | — | Canonicalization tests. | UNMAPPED | READY |
| REQ-446 | §11.2 | Render descriptive semantic path names by lowercase/maximal-nonalnum-to-hyphen/trim rules and numeric coordinates with canonical JSON number tokens. | Artifact | — | — | Path rendering test vectors. | UNMAPPED | READY |
| REQ-447 | §11.2 | Render exact log(2) coordinate as `rho=log2`, omit inapplicable dimensions, and never substitute hashes for semantic paths. | Artifact | — | — | Path rendering tests. | UNMAPPED | READY |
| REQ-448 | §11.2 | Use temporary sibling paths for incomplete writes and atomically promote only after checksum/schema/invariant/dependency validation. | Artifact | — | — | Atomic-write interruption tests. | UNMAPPED | READY |
| REQ-449 | §11.2 | Never treat recoverable checkpoints as completion evidence and never treat outputs/cache as authoritative. | Failure Semantics | — | — | Completion/cache validation tests. | UNMAPPED | READY |
| REQ-450 | §12 | Root manuscript-facing exports at configured results and export only completed schema/dependency/provenance-valid evidence. | Reporting | — | — | Report filter tests. | UNMAPPED | READY |
| REQ-451 | §12 | Publish experiment evidence under results/experiments and cross-experiment synthesis under results/project_summary owned by Statistical Synthesis. | Reporting | — | — | Export path tests. | UNMAPPED | READY |
| REQ-452 | §12 | Render every figure/table only from authoritative machine-readable outputs evidence; never consume results as scientific computational input. | Reporting | — | — | Reverse-dependency tests. | UNMAPPED | READY |
| REQ-453 | §12 | Make table/figure ordering deterministic and forbid favorable axis selection, seed subset selection, hiding incompatible points, undeclared smoothing, or fitted claim trends. | Reporting | — | — | Renderer/source-data tests and hostile review. | UNMAPPED | READY |
| REQ-454 | §12 | Allow rendering-only changes to regenerate display formats without invalidating scientific source data/metrics/statistics/cells. | Provenance | — | — | Selective invalidation tests. | UNMAPPED | READY |
| REQ-455 | §12 | Exclude caches, debug logs, failed/invalid/stale/temporary/partial artifacts, drafts, checkpoints, and authoritative computational provenance payloads from results. | Reporting | — | — | Results evidence filter tests. | UNMAPPED | READY |
| REQ-456 | §13.1 | Use the exact Arrow-compatible physical type conventions for authoritative Parquet and schema_version=1 for every authoritative schema. | Artifact | — | — | Schema tests. | UNMAPPED | READY |
| REQ-457 | §13.1 | Forbid NaN/infinity in claim-bearing float columns, use Arrow null for undefined values, and reject undeclared string-enum values. | Artifact | — | — | Parquet validation tests. | UNMAPPED | READY |
| REQ-458 | §13.2 | Implement the common artifact envelope with exactly the listed required/common/applicable fields and non-null rules. | Artifact | — | — | Common-envelope schema validation. | UNMAPPED | READY |
| REQ-459 | §13.2 | Define artifact_key as deterministic descriptive type+semantic/dependency coordinates and semantic_cell_key as descriptive experiment name plus RFC-8785 semantic coordinate serialization, never a hash. | Provenance | — | — | Identity test vectors. | UNMAPPED | READY |
| REQ-460 | §13.3 | Materialize experiment_plan.json and experiment_plan.parquet under outputs/artifacts/derived/plans during `run` when required; `plan` computes the same rows without mutating active scientific artifacts. | CLI / Execution | — | — | Plan/run integration and read-only tests. | UNMAPPED | READY |
| REQ-461 | §13.3 | Include exactly the listed plan-specific fields and apply the exact canonical plan ordering/null/string/numeric ordering rules. | Artifact | — | — | Plan schema/order tests. | UNMAPPED | READY |
| REQ-462 | §13.3 | Compute plan_digest as SHA-256 of canonical ordered-row array and cell_plan_digest as SHA-256 of one canonical row object. | Provenance | — | — | Digest test vectors. | UNMAPPED | READY |
| REQ-463 | §13.3 | Implement dataset manifest with the exact listed source/event/label/time/population/full-law/known-value/preprocessing/eligibility fields; current execution must be SYNTHETIC with known_full_law=true. | Artifact | — | — | Dataset-manifest schema tests. | UNMAPPED | READY |
| REQ-464 | §13.3 | Implement partition manifest with exact listed fields including coarsening map, parent, endpoint/precommit flags, and checksum. | Artifact | — | — | Partition-manifest schema tests. | UNMAPPED | READY |
| REQ-465 | §13.3 | Implement seed manifest with exact listed fields and store the actual seed list as unsigned decimal strings. | Artifact | — | — | Seed-manifest schema/content tests. | UNMAPPED | READY |
| REQ-466 | §13.3 | Implement reusable artifact manifest with exact listed identity/dependency/content/payload/schema/status/timestamp/consumer fields. | Artifact | — | — | Reusable-manifest schema tests. | UNMAPPED | READY |
| REQ-467 | §13.4 | Implement active semantic-cell manifest, execution-state record, and aggregate experiment record with exactly the listed fields. | Artifact | — | — | Record schema tests. | UNMAPPED | READY |
| REQ-468 | §13.4 | Do not create run IDs, UUIDs, attempt numbers, timestamps, or hash-derived scientific identifiers. | Reproducibility | — | — | Identity architecture tests. | UNMAPPED | READY |
| REQ-469 | §13.4 | Compute provenance_fingerprint from complete canonical lineage and dependency_fingerprint from only material dependencies exactly as specified. | Provenance | — | — | Fingerprint unit/property tests. | UNMAPPED | READY |
| REQ-470 | §13.4 | Exclude commit/dirty flag/timestamps/unrelated plan rows/source/tests/docs/log/report-only code from dependency fingerprint unless materially consumed. | Provenance | — | — | Selective-fingerprint tests. | UNMAPPED | READY |
| REQ-471 | §13.5 | Implement population metric, sequential update, stream metric, paired-comparison, statistical-test, effect-size, confidence-interval, and theorem-validation records with exactly the listed fields. | Artifact | — | — | Scientific result schema tests. | UNMAPPED | READY |
| REQ-472 | §13.5 | Do not include undefined `rho_star_anytime` in the current sequential schema. | Artifact | — | — | Schema negative test. | UNMAPPED | READY |
| REQ-473 | §13.6 | Implement failure records with exactly the listed fields and keep scientific nulls out of failure records. | Artifact | — | — | Failure schema/semantic tests. | UNMAPPED | READY |
| REQ-474 | §13.6 | Implement claim registry records with exactly the listed claim/evidence/scope/state fields. | Artifact | — | — | Claim-registry schema tests. | UNMAPPED | READY |
| REQ-475 | §13.6 | Write COMPLETED.json last and require all listed identity/digest/artifact/seed/metric/statistics/schema/invariant/dependency/provenance/exit fields to validate before a semantic cell is complete. | Failure Semantics | — | — | Atomic completion/evidence tests. | UNMAPPED | READY |
| REQ-476 | §13.6 | Interpret statistics_complete=true as 'not required at cell scope' only when no cell-level statistical artifact is required. | Failure Semantics | — | — | Completion semantic tests. | UNMAPPED | READY |
| REQ-477 | §13.6 | Never treat directory/checkpoint/log/partial payload/stale completion-marker existence alone as completion. | Failure Semantics | — | — | Completion rejection tests. | UNMAPPED | READY |
| REQ-478 | §14 | Use the exact scientific semantic coordinate tuple and omit/null inapplicable coordinates according to schema; exclude UUIDs/timestamps/attempt numbers/random IDs/hashes/incremental run IDs from scientific identity. | Reproducibility | — | — | Semantic identity tests. | UNMAPPED | READY |
| REQ-479 | §14 | Give every semantic cell exactly one canonical active location. | Artifact | — | — | Duplicate-active-result test. | UNMAPPED | READY |
| REQ-480 | §14.1 | Model the execution dependency chain as inputs -> preprocessing -> training -> scoring -> calibration/thresholding -> evaluation -> analysis -> reporting with TrajCert-specific meanings in the roadmap table. | Architecture | — | — | Artifact DAG validation. | UNMAPPED | READY |
| REQ-481 | §14.1 | Treat training as not applicable; introduce no predictive training, score generation, train/validation/test split, learned threshold selection, or post-hoc calibration. | Training | — | — | Negative architecture/registry tests. | UNMAPPED | READY |
| REQ-482 | §14.2 | Implement the ten canonical reusable artifact layers in the declared order and ownership. | Architecture | — | — | Artifact DAG/owner tests. | UNMAPPED | READY |
| REQ-483 | §14.2 | Allow validated shorter consumers to reuse prefixes of longer compatible streams and longer consumers to extend only when exact generator/seed identity proves same stream. | Reproducibility | — | — | Stream prefix/extension tests. | UNMAPPED | READY |
| REQ-484 | §14.2 | Never satisfy runtime benchmark target computations from cached target outputs inside the timed region. | Evaluation | — | — | Benchmark isolation tests. | UNMAPPED | READY |
| REQ-485 | §14.3 | Compute producer implementation-component digest as SHA-256 over sorted registered source files encoded relative_path+NUL+file_sha256+LF. | Provenance | — | — | Component-digest test vectors. | UNMAPPED | READY |
| REQ-486 | §14.3 | Implement at least the exact producer/artifact scientific-clause, component-file, runtime-dependency, and parent registrations listed in the producer dependency table; imported scientific components add transitively. | Provenance | — | — | Component registry validation. | UNMAPPED | READY |
| REQ-487 | §14.3 | Compute scientific_dependency_digest from the exact named roadmap subsection text plus applicable configuration fragments. | Provenance | — | — | Digest source tests. | UNMAPPED | READY |
| REQ-488 | §14.3 | Do not invalidate an artifact for changes to unrelated roadmap subsections. | Provenance | — | — | Selective invalidation tests. | UNMAPPED | READY |
| REQ-489 | §14.4 | Implement the selective invalidation table exactly for every artifact boundary, including both recompute triggers and explicit non-triggers. | Provenance | — | — | Parameterized invalidation matrix tests. | UNMAPPED | READY |
| REQ-490 | §14.5 | Before scientific work validate artifacts, reuse compatible ones, identify/remove stale active descendants, recompute only missing/invalid roots, then continue. | CLI / Execution | — | — | Recovery lifecycle integration test. | UNMAPPED | READY |
| REQ-491 | §14.5 | Represent artifact validation outcomes exactly as VALID, PARTIAL, STALE, CORRUPT, INCOMPATIBLE, MISSING and consume only VALID artifacts authoritatively. | Failure Semantics | — | — | Artifact validation enum/tests. | UNMAPPED | READY |
| REQ-492 | §14.5 | If regenerated canonical scientific content and dependency identity are unchanged, keep descendants valid even when provenance bytes differ. | Provenance | — | — | Content-identical regeneration test. | UNMAPPED | READY |
| REQ-493 | §14.6 | Reuse a complete active cell only when all required artifacts and completion marker validate against current dependency fingerprints. | Reproducibility | — | — | Reuse validation tests. | UNMAPPED | READY |
| REQ-494 | §14.6 | Make --overwrite recompute only the selected command's owned output roots, retain valid shared upstream artifacts, and invalidate descendants only when parent scientific-content/dependency identity changes. | Reproducibility | — | — | Overwrite/selective invalidation tests. | UNMAPPED | READY |
| REQ-495 | §14.7 | Use exactly 50 coverage and 10 utility checkpoint batches from configured ranges/sizes. | Reproducibility | — | — | Checkpoint planning tests. | UNMAPPED | READY |
| REQ-496 | §14.7 | Persist the exact listed checkpoint fields and apply the exact recovery validation/run-missing/concat/recompute/write-last sequence. | Reproducibility | — | — | Checkpoint recovery tests. | UNMAPPED | READY |
| REQ-497 | §15 | Keep doctor, plan, and status read-only with respect to active scientific artifacts. | CLI / Execution | — | — | Read-only command filesystem tests. | UNMAPPED | READY |
| REQ-498 | §15 | Record the exact reusable provenance envelope fields listed in Section 15. | Provenance | — | — | Environment/provenance schema tests. | UNMAPPED | READY |
| REQ-499 | §15 | Block claim-bearing `trajcert run` unless `git status --porcelain=v1 --untracked-files=all` is clean. | CLI / Execution | — | — | Dirty-tree block tests. | UNMAPPED | READY |
| REQ-500 | §15 | Obtain source commit with `git rev-parse HEAD` and block claim-bearing run with environment/prerequisite code if Git metadata is unavailable. | CLI / Execution | — | — | Missing-Git tests. | UNMAPPED | READY |
| REQ-501 | §15 | Require TRAJCERT_CONTAINER_IMAGE_DIGEST to be populated by launcher for claim-bearing run; validate and record a nonempty OCI/Docker digest or immutable image identifier, otherwise block execution. | CLI / Execution | — | — | Container-digest prerequisite tests. | UNMAPPED | READY |
| REQ-502 | §15 | Fix authoritative execution to CPU and forbid GPU acceleration from substituting for it. | CLI / Execution | — | — | Environment-mode validation. | UNMAPPED | READY |
| REQ-503 | §15 | Use provenance for audit lineage and dependency fingerprints for reuse compatibility. | Provenance | — | — | Lineage/reuse tests. | UNMAPPED | READY |
| REQ-504 | §16 | Expose executable `trajcert` and exactly the seven public command forms listed in Section 16. | CLI / Execution | — | — | CLI help/command tests. | UNMAPPED | READY |
| REQ-505 | §16 | Do not expose public flags for execution group, seed, rho, beta, delta, partition, baseline, method, variant, scientific config file, cache/checkpoint mode, or internal semantic cell. | CLI / Execution | — | — | CLI negative-option tests. | UNMAPPED | READY |
| REQ-506 | §16 | Use the exact five CLI exit codes and meanings from configuration. | CLI / Execution | — | — | Exit-code tests. | UNMAPPED | READY |
| REQ-507 | §16 | Implement each command contract exactly: doctor integrity/next-action; preprocess deterministic plan sources; plan read-only expansion; smoke fixtures; run one registry experiment with reuse/recovery; status lifecycle view; report verified export only. | CLI / Execution | — | — | CLI e2e tests. | UNMAPPED | READY |
| REQ-508 | §16 | Make preprocess with a name accept only an exact configured synthetic law or future external manifest name; unknown names exit 2; bare preprocess processes all current-plan sources. | CLI / Execution | — | — | Preprocess name tests. | UNMAPPED | READY |
| REQ-509 | §16.1 | Implement exactly the six smoke fixtures with the stated laws/partitions/rho/events/envelopes/expected outcomes. | Testing | — | — | Smoke suite validates all six fixtures. | UNMAPPED | READY |
| REQ-510 | §17 | Treat the Section 17 table as the authoritative and exhaustive experiment registry; no experiment may exist outside it. | Experiment | — | — | Registry reverse-traceability test. | UNMAPPED | READY |
| REQ-511 | §17 | Register `Scientific and Data Inventory` in execution group `Inventory validation` with evidence class `VALIDATION`, expansion `one protocol/inventory gate`, and exactly 1 registry cell(s). | Experiment | — | — | Registry expansion test proves `Scientific and Data Inventory` exact metadata and count. | UNMAPPED | READY |
| REQ-512 | §17 | Register `Legacy Partition Incoherence Check` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `3 Gamma x 2 q`, and exactly 6 registry cell(s). | Experiment | — | — | Registry expansion test proves `Legacy Partition Incoherence Check` exact metadata and count. | UNMAPPED | READY |
| REQ-513 | §17 | Register `Path Information Decomposition` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 4 partitions`, and exactly 48 registry cell(s). | Experiment | — | — | Registry expansion test proves `Path Information Decomposition` exact metadata and count. | UNMAPPED | READY |
| REQ-514 | §17 | Register `Information Profile Convexity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 4 partitions`, and exactly 48 registry cell(s). | Experiment | — | — | Registry expansion test proves `Information Profile Convexity` exact metadata and count. | UNMAPPED | READY |
| REQ-515 | §17 | Register `Minimum Compatibility Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 4 partitions`, and exactly 48 registry cell(s). | Experiment | — | — | Registry expansion test proves `Minimum Compatibility Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-516 | §17 | Register `Sharp-Set Constructive Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 4 partitions x 4 rho offsets`, and exactly 192 registry cell(s). | Experiment | — | — | Registry expansion test proves `Sharp-Set Constructive Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-517 | §17 | Register `Refinement Dominance Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 3 adjacent pairs`, and exactly 36 registry cell(s). | Experiment | — | — | Registry expansion test proves `Refinement Dominance Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-518 | §17 | Register `Strict Timing-Gain Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `6 cases x 3 offsets`, and exactly 18 registry cell(s). | Experiment | — | — | Registry expansion test proves `Strict Timing-Gain Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-519 | §17 | Register `Safety-Boundary Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws x 5 safety-budget cases`, and exactly 60 registry cell(s). | Experiment | — | — | Registry expansion test proves `Safety-Boundary Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-520 | §17 | Register `Endpoint Special-Case Identity` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `12 laws`, and exactly 12 registry cell(s). | Experiment | — | — | Registry expansion test proves `Endpoint Special-Case Identity` exact metadata and count. | UNMAPPED | READY |
| REQ-521 | §17 | Register `Anytime Projection Proof Check` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `one proof/dependency record`, and exactly 1 registry cell(s). | Experiment | — | — | Registry expansion test proves `Anytime Projection Proof Check` exact metadata and count. | UNMAPPED | READY |
| REQ-522 | §17 | Register `Population Complexity Proof Check` in execution group `Formal mathematics validation` with evidence class `VALIDATION`, expansion `one operation-count record`, and exactly 1 registry cell(s). | Experiment | — | — | Registry expansion test proves `Population Complexity Proof Check` exact metadata and count. | UNMAPPED | READY |
| REQ-523 | §17 | Register `Production Solver vs Independent Oracle` in execution group `Solver validation` with evidence class `VALIDATION`, expansion `12 laws x 4 partitions x 5 offsets`, and exactly 240 registry cell(s). | Experiment | — | — | Registry expansion test proves `Production Solver vs Independent Oracle` exact metadata and count. | UNMAPPED | READY |
| REQ-524 | §17 | Register `Callback-Model Reduction Falsification` in execution group `Comparator reduction` with evidence class `CONFIRMATORY`, expansion `12 finest-partition laws`, and exactly 12 registry cell(s). | Experiment | — | — | Registry expansion test proves `Callback-Model Reduction Falsification` exact metadata and count. | UNMAPPED | READY |
| REQ-525 | §17 | Register `Generic Information-Optimization Reduction` in execution group `Comparator reduction` with evidence class `CONFIRMATORY`, expansion `12 finest-partition laws`, and exactly 12 registry cell(s). | Experiment | — | — | Registry expansion test proves `Generic Information-Optimization Reduction` exact metadata and count. | UNMAPPED | READY |
| REQ-526 | §17 | Register `Partition Coherence` in execution group `Partition and timing mechanism` with evidence class `CONFIRMATORY`, expansion `6 laws x 3 pairs x 3 offsets`, and exactly 54 registry cell(s). | Experiment | — | — | Registry expansion test proves `Partition Coherence` exact metadata and count. | UNMAPPED | READY |
| REQ-527 | §17 | Register `Same Endpoint, Different Timing` in execution group `Partition and timing mechanism` with evidence class `ABLATION`, expansion `4 partitions x 5 rho paired-law cells`, and exactly 20 registry cell(s). | Experiment | — | — | Registry expansion test proves `Same Endpoint, Different Timing` exact metadata and count. | UNMAPPED | READY |
| REQ-528 | §17 | Register `Strict Timing Gain` in execution group `Partition and timing mechanism` with evidence class `CONFIRMATORY`, expansion `6 cases x 3 offsets`, and exactly 18 registry cell(s). | Experiment | — | — | Registry expansion test proves `Strict Timing Gain` exact metadata and count. | UNMAPPED | READY |
| REQ-529 | §17 | Register `Compatibility Floor Behavior` in execution group `Compatibility, sharpness, and safety` with evidence class `CONFIRMATORY`, expansion `12 laws x 2 partitions`, and exactly 24 registry cell(s). | Experiment | — | — | Registry expansion test proves `Compatibility Floor Behavior` exact metadata and count. | UNMAPPED | READY |
| REQ-530 | §17 | Register `Sharpness Against Generic Oracle` in execution group `Compatibility, sharpness, and safety` with evidence class `CONFIRMATORY`, expansion `10 laws x 4 partitions`, and exactly 40 registry cell(s). | Experiment | — | — | Registry expansion test proves `Sharpness Against Generic Oracle` exact metadata and count. | UNMAPPED | READY |
| REQ-531 | §17 | Register `Safety and Intrinsic Impossibility` in execution group `Compatibility, sharpness, and safety` with evidence class `CONFIRMATORY`, expansion `8 laws x 5 safety-budget cases`, and exactly 40 registry cell(s). | Experiment | — | — | Registry expansion test proves `Safety and Intrinsic Impossibility` exact metadata and count. | UNMAPPED | READY |
| REQ-532 | §17 | Register `Anytime Implementation Hand Cases` in execution group `Finite-sample implementation validation` with evidence class `VALIDATION`, expansion `10 hand cases x 3 partitions`, and exactly 30 registry cell(s). | Experiment | — | — | Registry expansion test proves `Anytime Implementation Hand Cases` exact metadata and count. | UNMAPPED | READY |
| REQ-533 | §17 | Register `Anytime Coverage Stress` in execution group `Anytime coverage validation` with evidence class `CONFIRMATORY`, expansion `12 stress cases`, and exactly 12 registry cell(s). | Experiment | — | — | Registry expansion test proves `Anytime Coverage Stress` exact metadata and count. | UNMAPPED | READY |
| REQ-534 | §17 | Register `Population Sensitivity Utility` in execution group `Utility analysis` with evidence class `ROBUSTNESS`, expansion `6 laws x 4 partitions x 15 rho`, and exactly 360 registry cell(s). | Experiment | — | — | Registry expansion test proves `Population Sensitivity Utility` exact metadata and count. | UNMAPPED | READY |
| REQ-535 | §17 | Register `Sequential Sensitivity Utility` in execution group `Utility analysis` with evidence class `ROBUSTNESS`, expansion `6 laws x 3 rho`, and exactly 18 registry cell(s). | Experiment | — | — | Registry expansion test proves `Sequential Sensitivity Utility` exact metadata and count. | UNMAPPED | READY |
| REQ-536 | §17 | Register `Failure Boundary Atlas` in execution group `Failure-boundary analysis` with evidence class `FAILURE_BOUNDARY`, expansion `9 axes x 7 levels`, and exactly 63 registry cell(s). | Experiment | — | — | Registry expansion test proves `Failure Boundary Atlas` exact metadata and count. | UNMAPPED | READY |
| REQ-537 | §17 | Register `Real-Trajectory Validation` in execution group `Real-trajectory generalization` with evidence class `GENERALIZATION`, expansion `absent`, and exactly 0 registry cell(s). | Experiment | — | — | Registry expansion test proves `Real-Trajectory Validation` exact metadata and count. | UNMAPPED | READY |
| REQ-538 | §17 | Register `Foreign-Information Negative Control` in execution group `Foreign-information diagnostic` with evidence class `DIAGNOSTIC`, expansion `absent`, and exactly 0 registry cell(s). | Experiment | — | — | Registry expansion test proves `Foreign-Information Negative Control` exact metadata and count. | UNMAPPED | READY |
| REQ-539 | §17 | Register `Computational Scaling` in execution group `Computational scaling` with evidence class `VALIDATION`, expansion `8 K values`, and exactly 8 registry cell(s). | Experiment | — | — | Registry expansion test proves `Computational Scaling` exact metadata and count. | UNMAPPED | READY |
| REQ-540 | §17 | Register `Statistical Synthesis` in execution group `Statistical synthesis` with evidence class `VALIDATION`, expansion `deterministic synthesis`, and exactly 1 registry cell(s). | Experiment | — | — | Registry expansion test proves `Statistical Synthesis` exact metadata and count. | UNMAPPED | READY |
| REQ-541 | §17 | Require the total authoritative registry count to equal exactly 1,423 cells. | Experiment | — | — | Plan total assertion. | UNMAPPED | READY |
| REQ-542 | §18.0 | Reuse identical intermediate calculations across cells when dependency fingerprints are identical rather than recomputing them. | Reproducibility | — | — | Cross-cell artifact reuse tests. | UNMAPPED | READY |
| REQ-543 | §18.0 | Require one schema-valid primary result record per deterministic cell unless an experiment-specific contract states otherwise. | Artifact | — | — | Cell completion validation. | UNMAPPED | READY |
| REQ-544 | §18.0 | Implement the exact experiment required/reusable-input and required-output map in Section 18.0. | Experiment | — | — | Experiment contract validation. | UNMAPPED | READY |
| REQ-545 | §18.0 | Mark an experiment COMPLETED only when all executable cells complete, all experiment-level aggregates/statistics/source-data validate, invalid/nonapplicable combinations are accounted for, and no required artifact is stale/missing. | Failure Semantics | — | — | Experiment completion tests. | UNMAPPED | READY |
| REQ-546 | §18.1 | Scientific and Data Inventory must require interpretable environment, synthetic preprocessing pass, smoke pass, registry total 1423, semantic-cell uniqueness, and validate configured constants/laws/manifests/schemas/real-data status/masses/sums/component registrations/counts. | Evaluation | — | — | Inventory validation record. | UNMAPPED | READY |
| REQ-547 | §18.2 | Resolve theorem rho offsets exactly relative to tau_Pi or tau_fine as specified for each named theorem/validation experiment; never interpret refinement offsets relative to coarse tau unless explicitly stated. | Experiment | — | — | Experiment-coordinate tests. | UNMAPPED | READY |
| REQ-548 | §18.2 | For Information Profile Convexity evaluate exactly convexity_profile_grid_points equally spaced u values in [0,c], check second derivatives only in interior with symbolic/high-precision direct differentiation, and do not use finite differences. | Evaluation | — | — | Convexity experiment tests. | UNMAPPED | READY |
| REQ-549 | §18.2 | For Sharp-Set Constructive Identity use production endpoints, independent oracle endpoints, and exactly constructive_profile_grid_points diagnostic points; the grid must never define roots. | Evaluation | — | — | Constructive identity records. | UNMAPPED | READY |
| REQ-550 | §18.3 | Across Production Solver vs Independent Oracle require zero state mismatches, endpoint error <= deterministic_identity_tolerance, bracket width <= root tolerance, and root residual <= identity tolerance. | Evaluation | — | — | Solver-oracle aggregate gate. | UNMAPPED | READY |
| REQ-551 | §18.3 | Statically verify oracle independence. | Testing | — | — | Architecture test. | UNMAPPED | READY |
| REQ-552 | §18.3 | Validate rho_star in Table 6 only with beta=budgets.primary_risk and only in the interior safety-frontier regime; compare production profile value to direct-table oracle at u=beta-A. | Evaluation | — | — | rho_star oracle records. | UNMAPPED | READY |
| REQ-553 | §18.3 | When rho_star interior regime does not apply store rho_star_error=null and rho_star_status=NOT_APPLICABLE and exclude such rows from max_abs_rho_star_error. | Metric | — | — | Table 6 aggregation tests. | UNMAPPED | READY |
| REQ-554 | §18.4 | Within each 8-band comparator-reduction law cell evaluate exactly ALHO, stable-resistance, repeated-attempt pattern mixture, legacy bandwise odds-ratio sensitivity, and generic MI oracle over their specified internal grids. | Experiment | — | — | Comparator-reduction cell contract tests. | UNMAPPED | READY |
| REQ-555 | §18.4 | Do not infer Gamma<->rho or C<->rho calibration. | Claim Boundary | — | — | Comparator reporting audit. | NON_IMPLEMENTATION | READY |
| REQ-556 | §18.4 | Persist comparator observation access, assumptions, sensitivity parameter, feasible set/estimate, applicability, numeric status, and exact-equality-to-TrajCert flag where semantics match. | Artifact | — | — | Comparator result schema. | UNMAPPED | READY |
| REQ-557 | §18.4 | Treat comparator-reduction experiments as prior-method reduction/falsification diagnostics with no separate Section 21 claim state. | Claim Boundary | — | — | Claim registry audit. | NON_IMPLEMENTATION | READY |
| REQ-558 | §18.4 | Retain and report any tested comparator equality with TrajCert without making a universal equivalence claim. | Claim Boundary | — | — | Result/claim audit. | NON_IMPLEMENTATION | READY |
| REQ-559 | §18.5 | Partition Coherence must use the six configured laws, adjacent 8->4/4->2/2->Endpoint pairs, and three refinement offsets. | Experiment | — | — | Plan-coordinate test. | UNMAPPED | READY |
| REQ-560 | §18.5 | Same Endpoint, Different Timing must contain exactly 20 paired-law semantic cells with the exact comparison_pair_name, one primary partition, and one configured same-endpoint rho each; compute/report both laws inside each cell. | Ablation | — | — | Paired-cell plan/result tests. | UNMAPPED | READY |
| REQ-561 | §18.5 | Strict Timing Gain must use six configured timing cases with rho=tau_fine+d and require fine subset coarse, profile difference=Delta tau, zero-information gain within tolerance, and positive-information gain above tolerance when theorem conditions hold. | Evaluation | — | — | Timing gain validation records. | UNMAPPED | READY |
| REQ-562 | §18.6 | Compatibility Floor Behavior must use 8-band and endpoint-only and internally test rho=tau-d,tau,tau+d with d equal the first refinement offset. | Experiment | — | — | Phase-behavior records. | UNMAPPED | READY |
| REQ-563 | §18.6 | For endpoint-only Compatibility Floor Behavior require tau=0 and label below-floor case NOT_APPLICABLE_BELOW_ZERO_INFORMATION_BUDGET without adding a registry cell. | Failure Semantics | — | — | Endpoint phase test. | UNMAPPED | READY |
| REQ-564 | §18.6 | Sharpness Against Generic Oracle must use rho=tau+confirmatory_sharpness_oracle_offset_above_tau. | Experiment | — | — | Coordinate validation. | UNMAPPED | READY |
| REQ-565 | §18.6 | Safety and Intrinsic Impossibility must use the five deterministic beta regimes. | Experiment | — | — | Plan/result validation. | UNMAPPED | READY |
| REQ-566 | §18.7 | Run the ten named finite-sample hand cases independently on 2-,4-,8-band partitions for exactly 30 cells with the exact fixtures and expected states/conditions in Section 18.7. | Evaluation | — | — | Hand-case result set. | UNMAPPED | READY |
| REQ-567 | §18.7 | Distinguish count-sequence hand cases as CS inversion/running-intersection validation from singleton-envelope cases as projection/state validation. | Evaluation | — | — | Hand-case metadata checks. | UNMAPPED | READY |
| REQ-568 | §18.7 | Keep evaluation/projection_oracle.py independent of inference/projection.py. | Architecture | — | — | Import/dependency test. | UNMAPPED | READY |
| REQ-569 | §18.7 | For singleton envelopes use direct high-precision full-table population projection oracle; for non-singleton hand fixtures use the exact 1001x1001 feasible-grid + top-20 local refinement verified-feasible lower-bound procedure. | Evaluation | — | — | Projection-oracle algorithm tests. | UNMAPPED | READY |
| REQ-570 | §18.7 | Treat any production certified upper below the projection oracle's best verified feasible value by more than identity tolerance as anti-conservative implementation failure. | Failure Semantics | — | — | Anti-conservatism gate. | UNMAPPED | READY |
| REQ-571 | §18.8 | Run every configured anytime stress case with rho derived from true information or compatibility floor exactly as specified and default beta=primary risk except near-certification. | Experiment | — | — | Stress plan/result validation. | UNMAPPED | READY |
| REQ-572 | §18.8 | For near-certification derive beta=true upper+configured offset; if beta>1 mark planned case INVALID and do not clip. | Failure Semantics | — | — | Near-certification plan test. | UNMAPPED | READY |
| REQ-573 | §18.8 | Execute exactly the four configured method labels inside each stress cell, sharing U_n artifact between TrajCert and raw projection, and treat ignorable-delay reference as valid only for Independent resolution control. | Experiment | — | — | Stress-method applicability/reuse tests. | UNMAPPED | READY |
| REQ-574 | §18.8 | Use exactly 5,000 independent streams through 500 matured events per stress cell and require every primary TrajCert stress cell to pass Section 9.8. | Experiment | — | — | Coverage execution/accounting records. | UNMAPPED | READY |
| REQ-575 | §18.9 | Population Sensitivity Utility must use 6 laws x 4 partitions x 14 numeric rho values plus exact log(2)=360 cells and retain incompatible points. | Experiment | — | — | Plan count and result visibility tests. | UNMAPPED | READY |
| REQ-576 | §18.9 | Evaluate population materiality only on primary 8-band partition using absolute tightening and relative unresolved gain exact formulas/thresholds; incompatible rho values cannot qualify. | Statistical Analysis | — | — | Materiality rule tests. | UNMAPPED | READY |
| REQ-577 | §18.9 | A population law qualifies only when the configured minimum number of compatible rho values meet both thresholds, and Practical Synthetic Nonvacuity is supported only when configured minimum qualifying laws is reached. | Statistical Analysis | — | — | Claim materiality tests. | UNMAPPED | READY |
| REQ-578 | §18.9 | For Sequential Sensitivity Utility share finest-path streams between 8-band and endpoint-only, use exactly 500 streams per law/rho, and run paired inference for all three practical metrics in the 54-test family. | Experiment | — | — | Paired stream/provenance/statistics tests. | UNMAPPED | READY |
| REQ-579 | §18.9 | For claim-level sequential qualifying-law vote use only Certified update fraction and require at least one rho with mean gain threshold, bootstrap lower bound above configured value, and Holm p below alpha; other metrics remain mandatory secondary evidence only. | Statistical Analysis | — | — | Sequential materiality rule tests. | UNMAPPED | READY |
| REQ-580 | §18.10 | Failure Boundary Atlas must use the nine one-at-a-time axes around the configured base law, default K/rho/beta unless overridden, and exact axis derivations in Section 18.10. | Experiment | — | — | Boundary-plan coordinate tests. | UNMAPPED | READY |
| REQ-581 | §18.10 | Use population calculations for population-valued axes and balanced-prefix deterministic finite samples for sample-size/node-budget axes. | Experiment | — | — | Boundary execution-type tests. | UNMAPPED | READY |
| REQ-582 | §18.10 | Populate Table 11 operational_state/optimizer_gap/runtime_ms according to the exact population vs finite-sample rules. | Reporting | — | — | Failure-boundary table tests. | UNMAPPED | READY |
| REQ-583 | §18.11 | Keep Real-Trajectory Validation and Foreign-Information Negative Control at zero executable cells with no current command/mechanism. | Experiment | — | — | Registry/CLI negative tests. | UNMAPPED | READY |
| REQ-584 | §18.12 | Run Computational Scaling at every configured K, timing population solver at primary information rho and outer projection at specified n/balanced-prefix/rho/beta. | Evaluation | — | — | Benchmark plan tests. | UNMAPPED | READY |
| REQ-585 | §18.12 | Time population and projection targets separately with exactly 5 warmups and 30 measured repetitions, each fresh isolated single-thread Linux process. | Evaluation | — | — | Benchmark runner tests. | UNMAPPED | READY |
| REQ-586 | §18.12 | Measure runtime with perf_counter_ns and peak RSS with getrusage RUSAGE_SELF, converting Linux KiB to MiB by /1024. | Evaluation | — | — | Benchmark metric tests. | UNMAPPED | READY |
| REQ-587 | §18.12 | Report median/IQR/mean/sample-SD runtime and peak RSS per target, and define root iterations, Table-12 peak memory, median_root_iterations, and median_outer_nodes exactly as specified. | Metric | — | — | Benchmark aggregation tests. | UNMAPPED | READY |
| REQ-588 | §18.12 | Treat empirical scaling slopes as descriptive only. | Claim Boundary | — | — | Reporting audit. | NON_IMPLEMENTATION | READY |
| REQ-589 | §18.13 | Run Statistical Synthesis exactly once after all required upstream experiments complete. | Experiment | — | — | Dependency/entry-gate test. | UNMAPPED | READY |
| REQ-590 | §18.13 | Statistical Synthesis must perform exactly the twelve listed validation/aggregation/claim/table/figure/audit/manifest tasks and must not recompute scientific cells. | Experiment | — | — | Synthesis contract tests. | UNMAPPED | READY |
| REQ-591 | §18.13 | Allow valid scientific falsification/null to flow through synthesis as claim-state changes, but block synthesis on missing/stale/invalid/technical-failed mandatory evidence. | Failure Semantics | — | — | Synthesis gating tests. | UNMAPPED | READY |
| REQ-592 | §19 Table 1 | Generate required Table 1 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 1 source-schema and render regression test. | UNMAPPED | READY |
| REQ-593 | §19 Table 2 | Generate required Table 2 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 2 source-schema and render regression test. | UNMAPPED | READY |
| REQ-594 | §19 Table 3 | Generate required Table 3 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 3 source-schema and render regression test. | UNMAPPED | READY |
| REQ-595 | §19 Table 4 | Generate required Table 4 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 4 source-schema and render regression test. | UNMAPPED | READY |
| REQ-596 | §19 Table 5 | Generate required Table 5 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 5 source-schema and render regression test. | UNMAPPED | READY |
| REQ-597 | §19 Table 6 | Generate required Table 6 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 6 source-schema and render regression test. | UNMAPPED | READY |
| REQ-598 | §19 Table 7 | Generate required Table 7 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 7 source-schema and render regression test. | UNMAPPED | READY |
| REQ-599 | §19 Table 8 | Generate required Table 8 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 8 source-schema and render regression test. | UNMAPPED | READY |
| REQ-600 | §19 Table 9 | Generate required Table 9 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 9 source-schema and render regression test. | UNMAPPED | READY |
| REQ-601 | §19 Table 10 | Generate required Table 10 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 10 source-schema and render regression test. | UNMAPPED | READY |
| REQ-602 | §19 Table 11 | Generate required Table 11 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 11 source-schema and render regression test. | UNMAPPED | READY |
| REQ-603 | §19 Table 12 | Generate required Table 12 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 12 source-schema and render regression test. | UNMAPPED | READY |
| REQ-604 | §19 Table 13 | Generate required Table 13 from the exact authoritative Parquet source path and with the exact columns/semantics defined in Section 19. | Reporting | — | — | Table 13 source-schema and render regression test. | UNMAPPED | READY |
| REQ-605 | §19 | Render experiment-owned CSV and TeX filenames from the source basename with .csv and .tex extensions. | Reporting | — | — | Filename tests. | UNMAPPED | READY |
| REQ-606 | §19 | Use linear interpolation at (n-1)q for median/IQR quantiles and ensure display rounding never feeds scientific comparison. | Reporting | — | — | Quantile/display separation tests. | UNMAPPED | READY |
| REQ-607 | §19 | Render p-values below configured threshold as `<0.0001` at current configuration. | Reporting | — | — | Display formatting test. | UNMAPPED | READY |
| REQ-608 | §20 Figure 1 | Generate required Figure 1 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 1 source-schema/render regression test. | UNMAPPED | READY |
| REQ-609 | §20 Figure 2 | Generate required Figure 2 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 2 source-schema/render regression test. | UNMAPPED | READY |
| REQ-610 | §20 Figure 3 | Generate required Figure 3 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 3 source-schema/render regression test. | UNMAPPED | READY |
| REQ-611 | §20 Figure 4 | Generate required Figure 4 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 4 source-schema/render regression test. | UNMAPPED | READY |
| REQ-612 | §20 Figure 5 | Generate required Figure 5 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 5 source-schema/render regression test. | UNMAPPED | READY |
| REQ-613 | §20 Figure 6 | Generate required Figure 6 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 6 source-schema/render regression test. | UNMAPPED | READY |
| REQ-614 | §20 Figure 7 | Generate required Figure 7 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 7 source-schema/render regression test. | UNMAPPED | READY |
| REQ-615 | §20 Figure 8 | Generate required Figure 8 from the exact source path, coordinates/panels/annotations/reference lines, and source semantics specified in Section 20. | Reporting | — | — | Figure 8 source-schema/render regression test. | UNMAPPED | READY |
| REQ-616 | §20 | Name SVG/PNG files from source basename with .svg/.png extensions and forbid smoothing, favorable post-selection, seed filtering, or hidden removal of incompatible points. | Reporting | — | — | Renderer policy tests. | UNMAPPED | READY |
| REQ-617 | §20 Figure 7 | Do not use interpolated heatmaps for the failure-boundary atlas in a way that implies untested configurations. | Claim Boundary | — | — | Figure renderer/hostile review. | NON_IMPLEMENTATION | READY |
| REQ-618 | §20 Figure 8 | Use log2 K for computational-scaling x coordinate and use a runtime log scale only if every recorded runtime is strictly positive. | Reporting | — | — | Figure scaling tests. | UNMAPPED | READY |
| REQ-619 | §21.1 | Implement the `Partition Coherence` claim with exact roadmap wording/meaning, required evidence `all legacy partition-incoherence cells, refinement identities, and 54 Partition Coherence cells`, support rule `zero PIS nesting violations beyond tolerance and all six legacy counterexamples show non-invariance`, and failure/scope rule `NOT_SUPPORTED on any valid PIS nesting counterexample`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-620 | §21.2 | Implement the `Observable Timing Decomposition` claim with exact roadmap wording/meaning, required evidence `all decomposition identities and same-endpoint timing ablation`, support rule `residual <= deterministic_identity_tolerance`, and failure/scope rule `failure if mandatory identity criterion fails`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-621 | §21.3 | Implement the `Exact Compatibility Floor` claim with exact roadmap wording/meaning, required evidence `minimum-compatibility identities and compatibility-floor behavior`, support rule `all below/at/above regimes match`, and failure/scope rule `failure if regime mismatch`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-622 | §21.4 | Implement the `Sharp Latent-Risk Set` claim with exact roadmap wording/meaning, required evidence `constructive identity, 240 solver-vs-oracle cells, and 40 sharpness cells`, support rule `zero state mismatches and max endpoint error <= tolerance`, and failure/scope rule `no finite-sample optimality claim follows`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-623 | §21.5 | Implement the `Strict Timing Value` claim with exact roadmap wording/meaning, required evidence `strict timing identity/mechanism evidence`, support rule `zero-information gain within tolerance, positive-information gain above tolerance, profile residual within tolerance`, and failure/scope rule `no claim that more bins always strictly help`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-624 | §21.6 | Implement the `Intrinsic Certification Impossibility` claim with exact roadmap wording/meaning, required evidence `safety identities and 40 safety/impossibility cells`, support rule `all five beta regimes and applicable rho_star identities pass`, and failure/scope rule `failure if mandatory safety criterion fails`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-625 | §21.7 | Implement the `Anytime-Valid Local Certificate` claim with exact roadmap wording/meaning, required evidence `projection proof check, 30 hand cases, 12 coverage stress cells`, support rule `all hand cases and CP stress gates pass with no anti-conservative optimizer failure`, and failure/scope rule `NOT_SUPPORTED on any primary stress failure`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-626 | §21.8 | Implement the `Practical Synthetic Nonvacuity` claim with exact roadmap wording/meaning, required evidence `all 360 population utility cells`, support rule `qualifying laws >= configured minimum`, and failure/scope rule `NULL_RESULT if materiality support fails; synthetic-only scope`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-627 | §21.9 | Implement the `Trajectory Operational Gain` claim with exact roadmap wording/meaning, required evidence `18 sequential utility conditions and all 54 Holm tests`, support rule `qualifying laws >= configured minimum by certified-update-fraction vote`, and failure/scope rule `PARTIALLY_SUPPORTED for exactly 1-2 laws; NULL_RESULT for 0`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-628 | §21.10 | Implement the `Computational Tractability` claim with exact roadmap wording/meaning, required evidence `operation-count proof, oracle validation, all 8 scaling cells`, support rule `all population oracle errors <= tolerance and all K complete`, and failure/scope rule `runtime/memory descriptive`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-629 | §21.11 | Implement the `Local Validity Without Federation` claim with exact roadmap wording/meaning, required evidence `static dependency and runtime lineage audits`, support rule `both audits pass and foreign scientific parent count is zero`, and failure/scope rule `NOT_SUPPORTED on any foreign scientific input`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-630 | §21.12 | Implement the `Real-Trajectory Value` claim with exact roadmap wording/meaning, required evidence `zero-cell planned nonapplicability`, support rule `final state NOT_TESTED and only allowed manuscript statement`, and failure/scope rule `real operational validation may not be implied`. | Claim Boundary | — | — | Mechanical claim-registry evaluation and hostile-review evidence. | UNMAPPED | READY |
| REQ-631 | §21.11 | Static local-validity audit must inspect the five bound-producing inference modules and allow only target-stream/count artifacts, target epoch/partition manifests, configuration/protocol values, and local numerical dependencies; forbid different-client scientific parents. | Evaluation | — | — | Static dependency audit record. | UNMAPPED | READY |
| REQ-632 | §21.11 | Runtime local-validity audit must recursively traverse parent_artifact_keys for every local bound, require exact target client/channel/epoch on operational parents, and forbid foreign_client_ids/statistics/model_updates/cross_client_aggregate as scientific inputs. | Evaluation | — | — | Runtime lineage audit record. | UNMAPPED | READY |
| REQ-633 | §21.11 | Persist static_dependency_pass, runtime_lineage_pass, foreign_scientific_parent_count, violating_artifact_keys, and pass in the local-validity audit output. | Artifact | — | — | Audit schema validation. | UNMAPPED | READY |
| REQ-634 | §22 | Implement claim states exactly as SUPPORTED, PARTIALLY_SUPPORTED, MECHANISM_ONLY, CONDITIONAL, NULL_RESULT, NOT_SUPPORTED, NOT_TESTED with the roadmap meanings. | Claim Boundary | — | — | Claim-state enum and semantic tests. | UNMAPPED | READY |
| REQ-635 | §22 | Use PARTIALLY_SUPPORTED only where a claim explicitly defines partial support and never hide/remove claims because results are unfavorable. | Claim Boundary | — | — | Claim evaluation tests. | NON_IMPLEMENTATION | READY |
| REQ-636 | §23 | Use one scientific execution regime with no second execution phase. | CLI / Execution | — | — | Execution architecture test. | UNMAPPED | READY |
| REQ-637 | §23 | Define cell, experiment, and Statistical Synthesis completion exactly from validated evidence as specified; scientific nulls/wide intervals/incompatibility/impossibility/falsification/unfavorable materiality may still complete. | Failure Semantics | — | — | Completion/synthesis tests. | UNMAPPED | READY |
| REQ-638 | §23 | Block Statistical Synthesis on each listed missing/FAILED/INVALID/stale/corrupt/schema/dependency/provenance/multiplicity/anti-conservative/hostile-review condition. | Failure Semantics | — | — | Parameterized synthesis block tests. | UNMAPPED | READY |
| REQ-639 | §23 | On successful synthesis write outputs/experiments/statistical-synthesis/provenance/dependencies/evidence_manifest.json with exactly the listed digest/commit/plan/manifest/cell/aggregate/claim/hostile-review fields. | Artifact | — | — | Evidence-manifest schema/validation. | UNMAPPED | READY |
| REQ-640 | §23 | Treat evidence manifest as reproducibility summary, not cache key; use normal selective invalidation after material changes and regenerate synthesis/manifest after affected recomputation. | Provenance | — | — | Invalidation/re-synthesis tests. | UNMAPPED | READY |
| REQ-641 | §23 | Permit report only when Statistical Synthesis is COMPLETED and its current evidence manifest validates against active artifacts. | CLI / Execution | — | — | Report gate tests. | UNMAPPED | READY |
| REQ-642 | §24 | Require complete reproduction inputs exactly as listed: source commit, requirements.lock, image digest, roadmap, trajcert YAML, deterministic generator/seeds, component dependency map, and public CLI. | Reproducibility | — | — | Reproduction checklist/doctor validation. | UNMAPPED | READY |
| REQ-643 | §24 | Make every manuscript-bearing number trace through the full results->outputs->metric/statistics->cell->fingerprints->parents->scientific fragments->data/partition/seed/component/environment->source commit->evidence manifest chain. | Provenance | — | — | End-to-end lineage audit. | UNMAPPED | READY |
| REQ-644 | §24 | Use hashes only for integrity/lineage, semantic coordinates for scientific identity, and dependency fingerprints for reuse compatibility. | Provenance | — | — | Identity/fingerprint tests. | UNMAPPED | READY |
| REQ-645 | §24.1 | Use RFC 8785 JCS semantics as normative canonicalization reference for repeatable hashing. | Reproducibility | — | — | Canonicalization tests. | UNMAPPED | READY |
| REQ-646 | §25 | Implement the six failure-semantic classes and exact execution/evidence consequences in the Section 25 table. | Failure Semantics | — | — | Failure-class unit/integration tests. | UNMAPPED | READY |
| REQ-647 | §25 | Treat TECHNICAL_FAIL as an internal result code within FAILED, not a scientific state. | Failure Semantics | — | — | Enum/state tests. | UNMAPPED | READY |
| REQ-648 | §25 | Allow INSUFFICIENT_EVIDENCE only as a valid monitoring state from evidence-count insufficiency after data/technical validity passes. | Failure Semantics | — | — | Precedence tests. | UNMAPPED | READY |
| REQ-649 | §26 | Implement deterministic/unit test coverage for every item listed in Section 26. | Testing | — | — | Test inventory audit. | UNMAPPED | READY |
| REQ-650 | §26 | Implement deterministic Hypothesis property checks for every property listed in Section 26 and keep generated cases as test evidence only. | Testing | — | — | Property-test inventory and deterministic profile. | UNMAPPED | READY |
| REQ-651 | §26 | Implement every integration/regression behavior listed in Section 26, including idempotence, selective invalidation, interruption/checkpoints, global-plan isolation, rendering isolation, completion-last, evidence-manifest rejection, report filtering, results cleanliness, and bug regressions. | Testing | — | — | Integration/regression suite. | UNMAPPED | READY |
| REQ-652 | §27 | Statistical Synthesis must produce machine-readable hostile-review evidence for target/scope, comparators, sequential/statistical validity, identity/recovery, evidence lineage, local validity, and complete 1,423-cell accounting. | Evaluation | — | — | Hostile-review record schema/content. | UNMAPPED | READY |
| REQ-653 | §27 | Any failed mandatory hostile-review check must block Statistical Synthesis. | Failure Semantics | — | — | Hostile-review block test. | UNMAPPED | READY |
| REQ-654 | §28 | Support the normal operator workflow in exact registry-driven order: doctor, preprocess, smoke, plan, Scientific and Data Inventory, remaining nonzero experiments in dependency order, Statistical Synthesis, doctor, report. | CLI / Execution | — | — | End-to-end workflow test. | UNMAPPED | READY |
| REQ-655 | §28 | Make every executing command automatically validate/reuse/invalidate/recover/recompute/continue according to the listed lifecycle; operators must not restart the project after a later failure. | CLI / Execution | — | — | Recovery/resume e2e tests. | UNMAPPED | READY |
| REQ-656 | §28 | On reissuing a failed/downstream experiment resume from nearest valid artifact while preserving valid earlier/unrelated results unless material dependencies changed. | Reproducibility | — | — | Resume/selective-reuse tests. | UNMAPPED | READY |
| REQ-657 | §28 | Keep Real-Trajectory Validation and Foreign-Information Negative Control non-executable. | Experiment | — | — | Registry/CLI negative tests. | UNMAPPED | READY |
| REQ-658 | §28 | Never let the operator choose seed, law, partition, method, baseline, rho, beta, delta, execution group, cache mode, checkpoint mode, or scientific configuration; operator selects only experiment family. | CLI / Execution | — | — | CLI option/plan authority tests. | UNMAPPED | READY |

---

## 5. Coverage Summary

### 5.1 Requirement Counts

- Total roadmap requirements: 658
- Implementation-bearing requirements: 636
- Non-implementation requirements: 22

### 5.2 Implementation Mapping

- Mapped: 0
- Unmapped: 636
- Ambiguous: 1
- Blocked: 0

### 5.3 Coverage Metric

```text
Implementation Coverage % =
  Mapped implementation-bearing requirements
  ------------------------------------------------ × 100
  Total implementation-bearing requirements
```

**Implementation Coverage:** 0.00%

A roadmap is fully mapped only when:

```text
Implementation Coverage = 100%
Unmapped = 0
```

A roadmap is implementation-ready only when:

```text
Implementation Coverage = 100%
Unmapped = 0
Ambiguous = 0
Blocked = 0
```

`NON_IMPLEMENTATION` requirements are excluded from the implementation-coverage denominator but must still be present in the inventory for traceability.

---

## 6. Unresolved Items

Only requirements with `AMBIGUOUS` or `BLOCKED` readiness belong here.

| Requirement ID | Problem | Impact | Blocking | Resolution Issue | Resolution Evidence |
|---|---|---|---|---|---|
| REQ-438 | Section 10 requires `docs/Roadmap.md`, while the immutable authoritative roadmap in this repository is `docs/TrajCert_Roadmap.md`; implementing the exact tree would otherwise require an unprescribed rename, duplicate, or alias. | Implementation / Reproducibility / Authority | Yes | Pending dedicated `roadmap-clarification` issue | Authoritative clarification must select the roadmap path behavior without changing roadmap science or authority. |

Rules:

- Reference the requirement by ID; do not duplicate its full wording.
- Every unresolved implementation detail must have a resolution issue.
- Resolution must be reflected back into the roadmap when the roadmap itself requires clarification.
- Mark the inventory requirement `READY` only after the authoritative source and implementation mapping are consistent.

---

## 7. Audit Invariants

The inventory is valid only if all of the following hold:

- Every roadmap obligation is represented by exactly one atomic inventory requirement, unless the roadmap statement contains multiple independently verifiable obligations that must be split into separate requirements.
- Every inventory requirement points back to an authoritative roadmap reference.
- Every implementation-bearing requirement has a milestone.
- Every `MAPPED` requirement references at least one GitHub issue.
- Every implementation-bearing requirement defines concrete acceptance evidence.
- Every `AMBIGUOUS` or `BLOCKED` requirement appears in **Unresolved Items**.
- Every unresolved implementation detail has a resolution issue.
- No `NON_IMPLEMENTATION` requirement contributes to the implementation-coverage percentage.
- No GitHub issue is treated as authoritative over the roadmap.
- No roadmap requirement is silently omitted because it is descriptive, restrictive, negative, or non-code.
- No requirement is considered complete merely because an issue exists; completion must be demonstrated by its declared acceptance evidence.
- `Implementation Coverage = 100%` means every implementation-bearing roadmap requirement is mapped, not that implementation itself is complete.
- Implementation may begin only when all requirements intended for the implementation phase are `MAPPED` and `READY`.
- The final global roadmap audit must verify both directions of traceability:

```text
Roadmap → Inventory → Milestones → Issues
Issues → Inventory → Roadmap
```
