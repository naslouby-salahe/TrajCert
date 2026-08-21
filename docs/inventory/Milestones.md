# M01 — Scientific and Configuration Contract
> **Outcome:** The authoritative TrajCert identity, scientific scope, mathematical contract, execution/scientific-state vocabularies, and complete configuration contract are encoded and objectively validated without semantic drift.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `Roadmap identity + §1–§4` |
| Requirement ownership | `REQ-001–REQ-612, REQ-3408–REQ-3411` |
| Upstream milestones | `None` |
| Implementation issues | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I08` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| Roadmap identity + §1 — Authority, Identity, States, and Execution | Framework identity, authority rules, scientific/public/internal execution states, evidence classes, idempotent execution semantics, and governing claim constraints. | `REQ-001–REQ-037, REQ-3408–REQ-3411` | `I01` | Enum/state/negative-path tests, reuse/idempotency checks, and claim/scope traceability preserve the exact authoritative vocabularies and prohibitions. |
| §2 — Problem, research questions, scope, and prohibited extrapolation | Unit of validity, latent-risk problem definition, epoch semantics, research-question boundaries, assumptions, exclusions, and claim limits. | `REQ-038–REQ-096` | `I01` | Deterministic mathematical/epoch checks and claim-boundary traceability verify the declared unit, exclusions, and prohibited extrapolations. |
| §3–§3.5 — Observation, maturation, information, and compatibility floor | Formal observation/event-ledger model, fixed-horizon maturation, PIS, observable timing information, exact information profile, and minimum-information compatibility construction. | `REQ-098–REQ-186` | `I02`, `I03` | Deterministic identity/property tests cover interior/boundary fixtures, event-ledger semantics, information identities, and compatibility-floor calculations at declared tolerances. |
| §3.6–§3.10 — Certification, refinement, safety, endpoint, and solver contract | Sharp latent-risk set, refinement/timing value, safety regimes, endpoint special case, and population certified-solver contract. | `REQ-188–REQ-266` | `I04` | Sharpness/safety/endpoint and solver property tests verify feasibility, bounds, conservative behavior, and declared continuous extensions. |
| §4 — Configuration authority, artifacts, CLI, comparators, and budgets | Configuration governance plus artifact paths, budgets, CLI settings, comparator/confidence/display settings, and related fixed values. | `REQ-267–REQ-305` | `I05` | Configuration-schema and exact-value tests validate required leaves, lists, paths, and no-override behavior. |
| §4 — Failure/materiality, method, numerics, and partition configuration | Failure-boundary, legacy partition-incoherence, materiality, method, minimum-evidence, numerical, and partition settings. | `REQ-306–REQ-386` | `I05` | Exact configuration-value validation plus numerical/partition consistency checks reject missing, altered, or incompatible settings. |
| §4 — Runtime, sensitivity, sequential, smoke, and statistical configuration | Runtime benchmark/environment, sensitivity, sequential inference/stress, smoke, and statistics settings. | `REQ-387–REQ-495` | `I06` | Config snapshot validation checks exact runtime/scientific values and deterministic seed/stress settings used downstream. |
| §4 — Strict-timing and synthetic-law configuration | Strict-timing cases and the complete configured synthetic-law catalog and role lists. | `REQ-496–REQ-588` | `I07` | Exact law/case registry validation verifies every configured law parameter, partition, role list, and strict-timing control. |
| §4 + §4.1 — Root YAML and dependency-lock contract | Top-level `configs/trajcert.yaml` requirements plus dependency-lock generation and installation rules. | `REQ-589–REQ-612` | `I07` | Whole-file configuration validation and clean dependency-lock generation/install checks produce reproducible, contract-compatible snapshots. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| None — foundational milestone | No upstream implementation capability or artifact is required. | Roadmap Coverage Inventory complete and all owned requirements `READY` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| None — foundational milestone | — | No upstream implementation artifact is required; the current Roadmap Coverage Inventory must remain complete and `READY`. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I01` — Encode Scientific Identity, State Vocabularies, Scope, and Epoch Contract | Typed authoritative vocabulary and identity contracts | Roadmap identity; §1 — Authority, Identity, States, and Execution; §2 — Research Problem, Questions, Claims, and Boundaries | 98 atomic requirements | None (foundational within this milestone chain) |
| 2 | `I02` — Implement Formal Observation, Ledger Maturation, and Integrity Contract | Validated matured-event/category records | §3 — Formal Observation and Mathematical Contract; §3.1 — Event-ledger and fixed-horizon maturation | 41 atomic requirements | `I01` |
| 3 | `I03` — Implement PIS, Timing Information, Information Profile, and Compatibility Floor | Population information-profile API | §3.2 — Path-Information Sensitivity; §3.3 — Observable timing information; §3.4 — Exact information profile; §3.5 — Minimum-information completion and compatibility floor | 19 atomic requirements | `I02` |
| 4 | `I04` — Implement Sharp Risk Sets, Refinement, Safety Regimes, and Population Solver | Sharp-risk-set and solver results with final brackets/residuals/iterations | §3.6 — Sharp risk set; §3.7 — Refinement and exact timing value; §3.8 — Safety regimes; §3.9 — Endpoint special case; §3.10 — Population solver contract | 56 atomic requirements | `I03` |
| 5 | `I05` — Implement Authoritative Configuration Schema, Core Scientific Values, and Validation | Validated frozen production configuration model | §4 — Configuration YAML | 120 atomic requirements | `I01` |
| 6 | `I06` — Complete Runtime, Sensitivity, Sequential, Smoke, and Statistical Configuration | Validated runtime/sensitivity/sequential/statistics configuration | §4 — Configuration YAML | 109 atomic requirements | `I05` |
| 7 | `I07` — Complete Strict-Timing, Synthetic-Law Configuration, and Locked Dependency Contract | Complete strict-timing/synthetic-law configuration registry | §4 — Configuration YAML; §4.1 — Dependency-lock generation and installation | 112 atomic requirements | `I05`, `I06` |
| 8 | `I08` — Audit Scientific and Configuration Contract Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | Roadmap identity + §1–§4; Milestones document — M01 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Authoritative typed identity, state, evidence-class, and scope contracts | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` | Enum/value/negative-path tests and claim-boundary traceability | M02, M03, M05, M06, M07 |
| Validated formal observation and mathematical-contract implementation | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` | Deterministic identity, inequality, boundary-extension, and numerical-tolerance tests | M04, M05, M06 |
| Complete validated `configs/trajcert.yaml` contract | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` | Exact configuration-leaf/list/path validation and configuration snapshot reproducibility | M02–M09 |
| Foundation validation evidence for roadmap authority and scientific non-drift | `I01`, `I02`, `I03`, `I04`, `I05`, `I06`, `I07` | All owned mandatory requirements have objective evidence; non-implementation constraints remain traceable | Milestone audit and all downstream milestones |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- No upstream milestone is required; this is the foundational implementation boundary.
- The Roadmap Coverage Inventory is complete, every owned requirement is `READY`, and no owned requirement is `AMBIGUOUS` or `BLOCKED`.
- Roadmap authority is preserved: implementation artifacts may transcribe but may not override the scientific contract.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- All authoritative identity/state/evidence vocabularies and execution/scientific-state distinctions exactly match the inventory.
- All §2 scope, epoch, exclusion, and claim-boundary constraints are preserved and testable.
- All §3 formal mathematical contracts and declared boundary/continuous-extension rules pass deterministic validation.
- The full §4 configuration surface validates with every required exact value, list, path, and prohibition enforced.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | State-vocabulary tests; deterministic formal-mathematics/property tests; epoch/provenance checks; exact configuration validation; claim-boundary traceability. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns only the roadmap identity material and §1–§4 requirements listed above.
- It defines the authoritative implementation contract consumed downstream; it does not own synthetic data generation, scientific comparators/statistics, experiment execution, or manuscript evidence production.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M02 — Reference Architecture, Workspace, and Schemas
> **Outcome:** The repository architecture, execution-workspace layout, and canonical machine-readable schemas exist as a typed, validated substrate for every downstream artifact and computation.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§10–§11 and §13` |
| Requirement ownership | `REQ-1294–REQ-1743, REQ-1764–REQ-2106` |
| Upstream milestones | `M01` |
| Implementation issues | `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I17` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §10 — Repository, outputs, and documentation layout | Repository root plus canonical configuration, output/result, manuscript, and documentation directory/file layout. | `REQ-1294–REQ-1401` | `I09` | Architecture tests assert every required path exists at the exact roadmap-defined location and reject structural drift. |
| §10 — Source package and module architecture | Canonical `src/trajcert/` package tree and all required domain, data, method, analysis, infrastructure, reporting, and CLI modules. | `REQ-1402–REQ-1520` | `I09` | Architecture/import tests verify required source modules, package boundaries, dependency direction, and typed public interfaces. |
| §10 — Test-suite architecture | Canonical tests tree and required architecture/unit/scientific/integration/e2e/smoke test modules. | `REQ-1521–REQ-1643` | `I10` | Structural test discovery verifies the complete roadmap-defined test surface and required file placement. |
| §10 — Architecture invariants and responsibility boundaries | Production configuration authority, module responsibilities, dependency rules, and architectural invariants not expressed solely as paths. | `REQ-1644–REQ-1658` | `I10` | Architecture rule tests reject forbidden coupling, alternate authorities, redirects/shims, and responsibility leakage. |
| §11 — Execution workspace contract | Canonical `outputs/` hierarchy, experiment/artifact/result placement, project summaries, and completion-marker locations. | `REQ-1659–REQ-1721` | `I11` | Workspace integration tests construct and validate exact paths, lifecycle locations, and placement rules. |
| §11.1–§11.2 — Canonical semantic serialization and filesystem rendering | Canonical semantic serialization plus deterministic filesystem-safe rendering of semantic identities. | `REQ-1722–REQ-1743` | `I12` | Round-trip/canonicalization tests verify stable semantic serialization, filesystem rendering, collision behavior, and reproducibility. |
| §13–§13.2 — Physical types and common envelope | Schema authority, canonical physical types, and common machine-readable envelope fields. | `REQ-1764–REQ-1818` | `I13` | Schema round-trip and negative tests enforce exact physical types, required fields, shared envelope composition, and serialization. |
| §13.3 — Plan and manifest schemas | Canonical plan plus scientific/data/dependency/reproducibility manifest records and fields. | `REQ-1819–REQ-1910` | `I14` | Positive/negative schema fixtures verify required plan/manifest fields, types, identities, and compatibility. |
| §13.4 — Cell, execution, dependency, and provenance schemas | Per-cell execution/dependency/provenance record contracts. | `REQ-1911–REQ-1961` | `I15` | Schema and lineage fixtures verify field presence, physical types, state compatibility, and dependency/provenance linkage. |
| §13.5 — Scientific result schemas | Canonical scientific result records for methods, metrics, evaluations, and statistics. | `REQ-1962–REQ-2052` | `I16` | Result-schema round trips and negative fixtures validate numerical/status fields, null semantics, and shared-envelope compatibility. |
| §13.6 — Failure, claim, and completion schemas | Failure records, claim records, completion markers, and related machine-readable status contracts. | `REQ-2053–REQ-2106` | `I16` | Schema/state tests verify exact failure/claim/completion vocabularies, required fields, and invalid-combination rejection. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M01 — Scientific and Configuration Contract | Locked scientific/configuration/state contracts that determine repository interfaces, artifact paths, and serialized values. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Validated configuration contract and required artifact/path names | M01 | Exact-value validation; no unresolved configuration drift. |
| Authoritative state/evidence/scientific vocabulary | M01 | Typed values exactly match the roadmap-defined contract. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I09` — Establish Canonical Repository and Source-Package Architecture | Canonical repository/source-package architecture | §10 — Reference Implementation Architecture | 227 atomic requirements | `I08` |
| 2 | `I10` — Establish Canonical Test Architecture and Enforce Repository Architecture Invariants | Canonical test-suite architecture | §10 — Reference Implementation Architecture | 138 atomic requirements | `I08`, `I09` |
| 3 | `I11` — Implement Canonical Execution Workspace and Result Layout | Deterministic workspace/path API | §11 — Execution Workspace Contract | 63 atomic requirements | `I08`, `I09`, `I10` |
| 4 | `I12` — Implement Canonical Semantic Serialization and Filesystem-Safe Rendering | Canonical semantic serializer | §11.1 — Canonical semantic serialization; §11.2 — Filesystem-safe semantic rendering | 22 atomic requirements | `I08`, `I09`, `I10` |
| 5 | `I13` — Implement Canonical Physical Types and Common Artifact Envelope | Versioned common artifact schema/envelope | §13 — Machine-Readable Schemas; §13.1 — Canonical physical types; §13.2 — Common envelope | 55 atomic requirements | `I08`, `I09`, `I10`, `I12` |
| 6 | `I14` — Implement Plan and Manifest Schemas | Canonical plan schemas | §13.3 — Plan and manifests | 92 atomic requirements | `I08`, `I12`, `I13` |
| 7 | `I15` — Implement Cell, Execution, Dependency, and Provenance Schemas | Canonical cell/execution/dependency/provenance records | §13.4 — Cell, execution, dependency, and provenance records | 51 atomic requirements | `I08`, `I13`, `I14` |
| 8 | `I16` — Implement Scientific Result, Failure, Claim, and Completion Schemas | Canonical scientific result schemas | §13.5 — Scientific result records; §13.6 — Failure, claim, and completion records | 145 atomic requirements | `I08`, `I13`, `I15` |
| 9 | `I17` — Audit Reference Architecture, Workspace, and Schemas Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §10–§11 and §13; Milestones document — M02 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I08`, `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Roadmap-defined `trajcert/` repository architecture and tooling surface | `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` | Structural/architecture tests pass for all required files, modules, and boundaries | M03–M09 |
| Canonical execution-workspace directory contract | `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` | Workspace creation/validation tests prove exact placement and lifecycle compatibility | M03, M04, M06, M07, M08 |
| Canonical machine-readable schemas and shared envelopes | `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` | Schema round-trip, physical-type, required-field, and negative-case validation | M03–M09 |
| Architecture and schema validation evidence | `I09`, `I10`, `I11`, `I12`, `I13`, `I14`, `I15`, `I16` | All owned architecture/testing requirements pass without schema or dependency leakage | Milestone audit and downstream integration |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M01 is complete and its audit is `PASS`.
- The scientific/configuration contracts that determine paths, enums, exact values, and serialized identities are locked.
- No architecture or schema decision requires inventing a value absent from the inventory.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every required repository path/module/tooling artifact in §10 exists at the exact roadmap-defined location and passes architecture validation.
- The §11 workspace can be created and validated deterministically with all required directories and result locations.
- Every §13 schema, physical type, envelope field, and serialization contract validates on positive and negative fixtures.
- Downstream milestones can create artifacts without redefining path, schema, or structural contracts.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Repository-architecture tests; exact workspace-layout integration tests; schema round-trip/physical-type/required-field validation; negative structural tests. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §10, §11, and §13 structural and machine-readable contracts only.
- It does not own runtime fingerprint/invalidation semantics, synthetic/data generation, scientific methods, experiment results, or manuscript rendering.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M03 — Semantic Identity, Provenance, CLI, and Failure Semantics
> **Outcome:** Semantic identity, dependency reuse/invalidation/recovery, provenance/logging, the public `trajcert` CLI, and execution failure semantics operate coherently over the canonical architecture and schemas.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§14–§16 and §25` |
| Requirement ownership | `REQ-2107–REQ-2429, REQ-3285–REQ-3303` |
| Upstream milestones | `M01, M02` |
| Implementation issues | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I24` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §14–§14.2 — Semantic identity, dependency chain, and reusable layers | Scientific identity coordinates, execution dependency chain, canonical digests, and reusable artifact layers. | `REQ-2107–REQ-2163` | `I18` | Digest/fingerprint tests mutate material versus unrelated inputs and verify exact identity, reuse, lineage, and layer compatibility. |
| §14.3 — Explicit producer dependency contracts | Producer-by-producer material dependency declarations for reusable and terminal artifacts. | `REQ-2164–REQ-2264` | `I19` | Dependency-contract tests verify each producer fingerprints exactly its declared material inputs and no undeclared input changes identity. |
| §14.4–§14.6 — Selective invalidation, atomic replacement, and idempotency | Selective invalidation boundaries, stale-descendant handling, validation-before-reuse, atomic replacement, overwrite, and idempotent execution. | `REQ-2265–REQ-2308` | `I20` | Mutation/reuse integration tests prove correct stale propagation, unrelated-input stability, atomic replacement, and overwrite/idempotency behavior. |
| §14.7 — Checkpoint recovery | Nearest-valid-checkpoint discovery, compatibility, recovery, and invalid/stale checkpoint rejection. | `REQ-2309–REQ-2332` | `I20` | Checkpoint recovery tests exercise missing/stale/incompatible candidates and verify nearest valid recovery with preserved lineage. |
| §15 — Logging and provenance | Runtime/software/hardware provenance, lineage fields, structured logs, persistence, and read-only command guarantees. | `REQ-2333–REQ-2364` | `I21` | Provenance/logging tests validate required fields, environment identity, stable lineage, persistence, and read-only non-mutation. |
| §16 — Public CLI contract | Exact public `trajcert` commands, arguments, forbidden overrides, exit codes, status/report behavior, and mutating versus read-only semantics. | `REQ-2365–REQ-2400` | `I22` | CLI/e2e tests assert exact command forms, allowed/forbidden parameters, exit codes, lifecycle transitions, and produced artifacts. |
| §16 — Deterministic CLI acceptance cases | Compatible/incompatible population, endpoint-only, refinement, deterministic-CS, and low-dimensional outer-optimizer command cases. | `REQ-2401–REQ-2429` | `I22` | Deterministic CLI fixtures execute each declared case and verify states, diagnostics, outputs, and numerical acceptance relations. |
| §25 — Failure semantics | Technical failure, stale/incompatible artifact, validation failure, scientific falsification/null, precedence, and recovery consequences. | `REQ-3285–REQ-3303` | `I23` | Negative-path tests trigger each declared failure class and verify exact execution/scientific state, precedence, diagnostics, blocking, and recovery. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M01 — Scientific and Configuration Contract | Execution/scientific states, configuration, exact CLI values, identity semantics, and no-override authority rules. | `Complete + audit PASS` |
| M02 — Reference Architecture, Workspace, and Schemas | Canonical modules, workspace paths, manifest/result schemas, and shared provenance envelope. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Canonical result/manifest/provenance schemas | M02 | Schema-valid and compatible with the active M01 contract. |
| Execution workspace contract | M02 | Exact directories and lifecycle locations validate before mutating commands run. |
| Configuration/state contracts | M01 | Exact values and vocabularies validate; no unresolved drift. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I18` — Implement Semantic Scientific Identity and Reusable Artifact Layers | Scientific identity engine | §14 — Semantic Identity, Dependency Reuse, Invalidation, and Recovery; §14.1 — Execution dependency chain; §14.2 — Canonical reusable artifact layers | 57 atomic requirements | `I08`, `I17` |
| 2 | `I19` — Implement Explicit Producer Dependency and Component-Digest Contracts | Authoritative producer registry | §14.3 — Explicit producer dependency contracts | 101 atomic requirements | `I08`, `I17`, `I18` |
| 3 | `I20` — Implement Selective Invalidation, Atomic Replacement, Idempotency, and Checkpoint Recovery | Selective invalidation/reuse engine | §14.4 — Selective invalidation boundaries; §14.5 — Validation, stale-descendant handling, and atomic replacement; §14.6 — Idempotent execution and overwrite; §14.7 — Checkpoint recovery | 68 atomic requirements | `I08`, `I17`, `I19` |
| 4 | `I21` — Implement Structured Logging, Environment Capture, and Provenance | Structured provenance records | §15 — Logging and Provenance | 32 atomic requirements | `I08`, `I17`, `I18`, `I19` |
| 5 | `I22` — Implement Exact Public CLI and Deterministic Acceptance Fixtures | Public `trajcert` CLI | §16 — Public CLI; §16.1 — Exact smoke fixtures | 65 atomic requirements | `I08`, `I17`, `I20`, `I21` |
| 6 | `I23` — Implement Roadmap Failure Classification and Precedence Semantics | Failure-classification/state-precedence engine | §25 — Failure Semantics | 19 atomic requirements | `I08`, `I17`, `I20`, `I22` |
| 7 | `I24` — Audit Semantic Identity, Provenance, CLI, and Failure Semantics Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §14–§16 and §25; Milestones document — M03 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I08`, `I17`, `I18`, `I19`, `I20`, `I21`, `I22`, `I23` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Scientific identity and material-dependency fingerprint engine | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` | Digest/canonicalization and mutation tests prove identity and compatibility behavior | M04–M09 |
| Reuse, invalidation, stale-descendant, and recovery engine | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` | Integration tests prove idempotent reuse, selective invalidation, and nearest-valid recovery | M04, M06, M08, M09 |
| Complete logging and provenance envelope | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` | Required environment/code/dependency fields validate and lineage remains stable | M04, M06–M09 |
| Public `trajcert` CLI surface | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` | CLI/e2e tests pass for exact forms, exit codes, mutation/read-only behavior, reuse, and overwrite | M04, M06–M09 |
| Roadmap-defined failure-state behavior | `I18`, `I19`, `I20`, `I21`, `I22`, `I23` | Negative-path tests prove exact execution/scientific consequences and no unsupported evidence | M06, M08, M09 |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M01 and M02 are complete and both milestone audits are `PASS`.
- Canonical schemas and workspace paths exist before identity, reuse, provenance, or CLI lifecycle behavior is implemented.
- Exact state vocabularies, exit codes, and command/config values are available from M01 without local reinterpretation.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Material dependency identities and fingerprints deterministically control reuse compatibility and staleness.
- Invalidation and recovery remove/recompute only required descendants and resume from the nearest valid checkpoint where specified.
- Logging/provenance records contain every required identity and environment field and read-only commands do not mutate active scientific artifacts.
- Every public CLI command, argument rule, exit code, lifecycle transition, and overwrite/reuse semantic passes end-to-end validation.
- Every §25 failure class produces the exact roadmap-defined execution/evidence consequence and never masks a valid scientific null or falsification as a technical failure.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Digest/fingerprint mutation tests; reuse/invalidation/recovery integration tests; provenance envelope checks; CLI e2e tests; failure-state negative-path tests. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §14–§16 and §25 runtime identity, provenance, CLI, and failure-semantics requirements.
- It does not own scientific experiment outcomes or global test-suite closure; later milestones consume this runtime contract.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M04 — Synthetic Trajectories and Dataset Authority
> **Outcome:** Deterministic synthetic trajectory laws and the dataset/real-trajectory authority pipeline produce validated, provenance-compatible scientific inputs without exceeding the roadmap’s real-data claim boundary.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§5–§6` |
| Requirement ownership | `REQ-613–REQ-759` |
| Upstream milestones | `M01, M02, M03` |
| Implementation issues | `I25`, `I26`, `I27`, `I28` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I29` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §5.1–§5.4 — Synthetic generator and law catalog | Synthetic trajectory probability generator, primary/derived law roles, minimum-information constructions, and K-scaling laws. | `REQ-613–REQ-660` | `I25` | Formula/property tests verify exact law parameters, probability validity, role membership, derived constructions, and K-scaling invariants. |
| §5.5–§5.8 — Stream generation, ledger, preprocessing, and count apportionment | Stochastic stream generation, synthetic ledger, deterministic preprocessing, and exact count apportionment. | `REQ-661–REQ-704` | `I26` | Deterministic seeded fixtures validate stream/ledger fields, preprocessing invariants, split semantics, and exact apportionment totals. |
| §5 — Balanced-prefix construction | Balanced-prefix/refinement sequence construction used by synthetic validation and downstream hand cases. | `REQ-705–REQ-717` | `I27` | Construction tests verify deterministic prefixes, exact counts, refinement compatibility, and repeatability. |
| §6 — Dataset authority and real-trajectory decision | External-data inventory authority, expected-versus-observed validation, checksums/schema observations, eligibility/nonapplicability, and real-trajectory claim boundary. | `REQ-718–REQ-759` | `I28` | Inventory/provenance checks validate observed data facts and applicability; traceability rejects unsupported real-operational claims. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M01 — Scientific and Configuration Contract | Synthetic-law mathematics, fixed scientific parameters, dataset scope, and prohibited extrapolation rules. | `Complete + audit PASS` |
| M02 — Reference Architecture, Workspace, and Schemas | Prepared-data/artifact locations and canonical machine-readable schema contracts. | `Complete + audit PASS` |
| M03 — Semantic Identity, Provenance, CLI, and Failure Semantics | Provenance/fingerprint lifecycle and preprocessing execution semantics. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Synthetic-law/configuration contract | M01 | Exact formulas/values and deterministic seed rules validate. |
| Prepared-data and inventory schemas/workspace | M02 | Schema-valid paths and canonical types. |
| Provenance/fingerprint and `trajcert preprocess` lifecycle | M03 | Dependency-compatible, idempotent, and recoverable execution. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I25` — Implement Deterministic Synthetic Trajectory Laws and Derived Law Catalog | Validated synthetic law catalog/full-law tables | §5.1 — Synthetic trajectory generator; §5.2 — Primary law roles; §5.3 — Derived minimum-information laws; §5.4 — K-scaling laws | 36 atomic requirements | `I08`, `I17`, `I24` |
| 2 | `I26` — Implement Synthetic Streams, Ledger, Preprocessing, and Hamilton Apportionment | Validated synthetic event streams/ledgers | §5.5 — Stochastic stream generation; §5.6 — Synthetic ledger; §5.7 — Preprocessing; §5.8 — Deterministic count apportionment | 37 atomic requirements | `I08`, `I17`, `I24`, `I25` |
| 3 | `I27` — Implement Deterministic Balanced-Prefix Construction | Balanced-prefix sequence implementation | §5.8 — Deterministic count apportionment; Balanced-prefix construction | 10 atomic requirements | `I08`, `I17`, `I24`, `I26` |
| 4 | `I28` — Implement Dataset Inventory Authority, Eligibility, and Real-Trajectory Boundary | External dataset inventory records | §6 — Dataset Authority and Real-Trajectory Decision | 42 atomic requirements | `I08`, `I17`, `I24` |
| 5 | `I29` — Audit Synthetic Trajectories and Dataset Authority Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §5–§6; Milestones document — M04 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I08`, `I17`, `I24`, `I25`, `I26`, `I27`, `I28` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Deterministic synthetic trajectory generator and locked law catalog | `I25`, `I26`, `I27`, `I28` | Probability/formula/property tests and repeatability checks pass | M05, M06 |
| Balanced-prefix/refinement and prepared synthetic-law artifacts | `I25`, `I26`, `I27`, `I28` | Construction invariants and deterministic serialization validate | M05, M06 |
| External-dataset inventory and validation records | `I25`, `I26`, `I27`, `I28` | Expected/observed provenance, checksums, schemas/counts, and applicability rules validate | M06, M07 |
| Real-trajectory decision evidence and explicit claim boundary | `I25`, `I26`, `I27`, `I28` | Traceability confirms no unsupported real-operational validation is implied | M07, M08 |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M01, M02, and M03 are complete and their audits are `PASS`.
- Synthetic-law mathematics and fixed parameters are locked before generator implementation.
- Workspace, schemas, provenance, and preprocessing lifecycle are available before producing prepared data.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every synthetic law and construction is deterministic under the roadmap seed/configuration contract and passes formula/probability/invariant validation.
- Prepared synthetic artifacts are schema-valid, provenance-complete, and reusable under dependency fingerprints.
- Every required external-dataset inventory field, checksum/observed-value rule, and applicability decision is recorded and validated.
- The real-trajectory decision is represented exactly as required and no dataset result broadens the permitted claim scope.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Deterministic generator/property tests; balanced-prefix/refinement invariants; prepared-artifact schema/provenance validation; dataset inventory/checksum/applicability evidence. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §5–§6 data-generation and dataset-authority requirements.
- It does not own baseline estimators, certification statistics, experiment execution, or manuscript claims beyond preserving the roadmap’s explicit real-trajectory boundary.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M05 — Comparators, Metrics, and Statistical Certification Engine
> **Outcome:** All roadmap-defined baselines, sensitivity comparators, metrics, aggregation rules, confidence procedures, and statistical synthesis primitives are numerically validated and ready for authoritative experiments.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§7–§9` |
| Requirement ownership | `REQ-760–REQ-1293` |
| Upstream milestones | `M01, M02, M03, M04` |
| Implementation issues | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I37` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §7.1–§7.4.1 — Foundational and legacy comparators | Complete-case, unresolved-as-harm, endpoint-only, legacy bandwise odds-ratio sensitivity, and deterministic partition-incoherence construction. | `REQ-760–REQ-820` | `I30` | Comparator/reduction tests verify assumptions, exact outputs, applicability, boundary behavior, and deterministic partition-incoherence cases. |
| §7.5–§7.8 — Sensitivity callbacks and full-law oracle | ALHO common-slope, stable-resistance, repeated-attempt mixture, and generic full-law information-oracle implementations. | `REQ-821–REQ-901` | `I31` | Deterministic comparator/oracle fixtures verify optimization contracts, feasible laws, information calculations, and required status/applicability outputs. |
| §7.9–§7.12 — Anytime references, controls, and ablations | Time-uniform observable-law projection, repeated-static-monitoring negative control, ignorable-delay anytime reference, and declared ablations. | `REQ-902–REQ-942` | `I35` | Control/ablation tests verify exact reduction relations, anytime semantics, negative-control behavior, and declared ablation settings. |
| §8–§8.1 — Metrics, aggregation, and undefined behavior | Scientific/computational/coverage/utility/state metrics, aggregation rules, directions, denominators, and undefined-result semantics. | `REQ-943–REQ-1008` | `I32` | Exact-formula and edge-case tests verify metric values, aggregation units, null/undefined behavior, and serialization-ready status fields. |
| §9.1–§9.3 — Independent units, confidence sequence, inversion, and summary envelope | Independent-unit contract, categorical confidence sequence, endpoint inversion, and conservative summary-envelope construction. | `REQ-1009–REQ-1074` | `I33` | Deterministic/statistical fixtures verify coverage components, inversion/bracketing, running intersections, and conservative envelope properties. |
| §9.4–§9.7 — Certified optimization, compatibility, impossibility, and evidence/state gates | Certified outer optimization, finite-sample compatibility, intrinsic impossibility, and failure/scientific-state precedence gates. | `REQ-1075–REQ-1199` | `I34` | Certified-optimization and negative-path tests verify conservative upper bounds, compatibility/impossibility logic, gate precedence, and numerical statuses. |
| §9.8–§9.9 — Validation and paired practical inference | Clopper-Pearson validation, paired percentile bootstrap, sign-flip testing, effect-size edge cases, and Holm multiplicity adjustment. | `REQ-1200–REQ-1264` | `I36` | Fixed-seed statistical fixtures reproduce intervals/tests/effect sizes/multiplicity decisions with the declared unit of analysis and thresholds. |
| §9.10–§9.11 — Failed stochastic executions and randomness | Treatment of failed stochastic executions plus semantic seed derivation, reproducibility, and deterministic rerun/reuse rules. | `REQ-1265–REQ-1293` | `I36` | Failure-accounting and clean-rerun tests verify seed derivation, deterministic outputs, material-dependency invalidation, and reproducible statistical units. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M01 — Scientific and Configuration Contract | Formal observation model, exact mathematical definitions, numerical tolerances, and scientific-state semantics. | `Complete + audit PASS` |
| M02 — Reference Architecture, Workspace, and Schemas | Typed result interfaces and canonical numeric/artifact schemas. | `Complete + audit PASS` |
| M03 — Semantic Identity, Provenance, CLI, and Failure Semantics | Dependency identity/provenance and exact numeric failure handling. | `Complete + audit PASS` |
| M04 — Synthetic Trajectories and Dataset Authority | Deterministic synthetic laws and validated prepared inputs used for comparator/statistical validation. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Formal mathematical/configuration contract | M01 | Exact identities, tolerances, constants, and boundary rules validate. |
| Canonical result schemas | M02 | Numeric/status/result records serialize and validate exactly. |
| Prepared synthetic laws and constructions | M04 | Deterministic, schema-valid, and provenance-compatible. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I30` — Implement Foundational and Legacy Comparator Contracts | Foundational comparator results | §7.1 — Complete-case arrival-only; §7.2 — Unresolved-as-harm worst case; §7.3 — Endpoint-only path information; §7.4 — Legacy bandwise odds-ratio sensitivity; §7.4.1 — Deterministic legacy partition-incoherence construction | 39 atomic requirements | `I08`, `I17`, `I24`, `I29` |
| 2 | `I31` — Implement Sensitivity Callbacks, Pattern Mixture, and Independent Full-Law Oracle | Callback comparator results | §7.5 — ALHO common-slope callback; §7.6 — Stable-resistance callback; §7.7 — Binary repeated-attempt pattern mixture; §7.8 — Generic full-law information oracle | 61 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I30` |
| 3 | `I32` — Implement Canonical Metrics, Aggregation, and Undefined-Value Semantics | Canonical metric/aggregation library | §8 — Metrics and Aggregation; §8.1 — Undefined behavior | 64 atomic requirements | `I08`, `I17`, `I24`, `I29` |
| 4 | `I33` — Implement Categorical Confidence Sequence, Outward Endpoint Inversion, and Summary Envelope | Categorical CS trajectories with outward endpoint brackets | §9.1 — Independent units; §9.2 — Categorical confidence sequence; Endpoint inversion; §9.3 — Conservative summary envelope | 43 atomic requirements | `I08`, `I17`, `I24`, `I29` |
| 5 | `I34` — Implement Certified Outer Projection, Compatibility, Intrinsic Impossibility, and State Gates | Certified projection results/diagnostics | §9.4 — Certified outer optimization; §9.5 — Finite-sample compatibility; §9.6 — Finite-sample intrinsic impossibility; §9.7 — Evidence gate, failure precedence, and scientific-state precedence | 101 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I33` |
| 6 | `I35` — Implement Sequential References, Negative Control, Ignorable-Delay Reference, and Ablations | Sequential reference trajectories | §7.9 — Time-uniform observable-law projection; §7.10 — Repeated-static-monitoring negative control; §7.11 — Ignorable-delay anytime reference; §7.12 — Ablations | 34 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I33`, `I34` |
| 7 | `I36` — Implement Statistical Validation, Paired Inference, Failed-Seed Accounting, and Semantic Randomness | Statistical interval/test/effect/multiplicity records | §9.8 — Clopper-Pearson validation; §9.9 — Paired practical inference; Paired percentile bootstrap; Sign-flip test; Effect-size edge cases; Holm adjustment; §9.10 — Failed stochastic executions; §9.11 — Randomness and seed derivation | 79 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I32` |
| 8 | `I37` — Audit Comparators, Metrics, and Statistical Certification Engine Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §7–§9; Milestones document — M05 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I08`, `I17`, `I24`, `I29`, `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Complete baseline and sensitivity-comparator library | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` | Deterministic comparator, applicability, reduction, and boundary tests pass | M06, M07 |
| Canonical metrics and aggregation library | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` | Exact-formula and edge-case unit tests pass | M06, M07 |
| Confidence-sequence, inversion, and certification machinery | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` | Coverage/inversion/bracketing and numerical-status tests pass | M06 |
| Paired statistical testing and multiplicity-adjustment utilities | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` | Bootstrap, sign-flip, effect-size, and Holm test fixtures pass | M06, M07 |
| Numerical/oracle validation evidence | `I30`, `I31`, `I32`, `I33`, `I34`, `I35`, `I36` | Roadmap-defined tolerances and deterministic identities hold across required fixtures | M06 and milestone audit |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M01–M04 are complete and their milestone audits are `PASS`.
- Validated synthetic laws/prepared inputs exist for deterministic comparator and statistical test fixtures.
- Canonical result/status schemas and numerical failure semantics are available.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every §7 comparator implements its exact assumptions, applicability conditions, formulas, boundary behavior, and result/status contract.
- Every §8 metric and aggregation definition produces exact roadmap-defined values on deterministic fixtures, including denominator/edge cases.
- All §9 confidence, inversion, gate, bootstrap, sign-flip, effect-size, and Holm procedures pass their deterministic/statistical validation contracts.
- The scientific engine exposes stable typed outputs that the authoritative experiment registry can invoke without redefining methodology.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Comparator/reduction fixtures; exact metric tests; confidence-sequence and endpoint-inversion validation; paired-bootstrap/sign-flip/effect-size/Holm tests; numerical oracle checks. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §7–§9 scientific computation and statistical-method requirements.
- It does not own experiment-family enumeration, experiment execution, or manuscript-facing claims; those consume the validated engine.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M06 — Authoritative Experiment Registry and Execution
> **Outcome:** The exact authoritative experiment registry expands into the complete dependency-ordered execution plan and produces all roadmap-required scientific outputs, aggregates, diagnostics, and statistical-synthesis evidence.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§17–§18` |
| Requirement ownership | `REQ-2430–REQ-2874, REQ-3412` |
| Upstream milestones | `M02, M03, M04, M05` |
| Implementation issues | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I46` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §17 — Authoritative experiment registry | Exact experiment names, execution groups, evidence classes, expansions, fixed row order, semantic coordinates, and the complete 1,423-cell authoritative plan. | `REQ-2430–REQ-2530, REQ-3412` | `I38` | Plan expansion tests verify exactly 1,423 cells in declared order with exact semantic coordinates/classes and no missing or extra experiment. |
| §18.0 — Experiment dependency and required-output map | Per-experiment upstream dependencies, required reusable artifacts, result outputs, completion conditions, and execution relationships. | `REQ-2531–REQ-2592` | `I39` | Dependency/output-map validation proves every experiment consumes and produces exactly the roadmap-declared artifacts and completion records. |
| §18.1–§18.2 — Inventory validation and rho-offset resolution | Scientific/data inventory validation plus deterministic resolution of configured rho offsets and invalid conditions. | `REQ-2593–REQ-2609` | `I40` | Evaluation fixtures validate inventory states, exact rho derivations, invalid/nonapplicable handling, and machine-readable outputs. |
| §18.3–§18.6 — Solver, comparator, partition/timing, compatibility, sharpness, and safety validation | Production-vs-independent-oracle, comparator reduction, partition/timing mechanism, and compatibility/sharpness/safety experiments. | `REQ-2610–REQ-2675` | `I41` | Experiment e2e tests execute declared paired/control cells and verify oracle relations, reductions, metrics, states, and numerical tolerances. |
| §18.7 — Anytime implementation hand cases and independent projection oracle | Anytime implementation hand cases, including the internally numbered §1–§10 fixtures, applicability rules, conservative fallback case, and independent high-precision projection oracle. | `REQ-2676–REQ-2760` | `I42` | Every hand case executes with its exact fixture settings/expected state; applicability checks pass; the independent oracle rejects anti-conservative production bounds beyond tolerance. |
| §18.8–§18.9 — Anytime coverage stress and utility analysis | Configured anytime stress cases, derived rho/beta conditions, coverage validation, population materiality, and sequential utility. | `REQ-2761–REQ-2810` | `I43` | Stress/utility runs validate planned-validity rules, coverage/materiality metrics, paired outputs, and all declared numerical/state acceptance conditions. |
| §18.10–§18.12 — Failure boundaries, planned nonapplicabilities, and computational scaling | Failure-boundary atlas, predeclared nonapplicable cells, and computational scaling experiments. | `REQ-2811–REQ-2858` | `I44` | Execution/analysis tests verify boundary classifications, nonapplicability records, scaling coordinates/metrics, and required outputs without post-hoc condition changes. |
| §18.13 — Statistical synthesis | Project-level statistical synthesis over completed authoritative experiments and required evidence. | `REQ-2859–REQ-2874` | `I45` | Synthesis tests verify exact included evidence, statistical outputs, completeness rules, blocking semantics, and machine-readable project evidence records. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M02 — Reference Architecture, Workspace, and Schemas | Canonical plan, manifest, result, failure, provenance, and completion schemas plus experiment workspace paths. | `Complete + audit PASS` |
| M03 — Semantic Identity, Provenance, CLI, and Failure Semantics | Executable lifecycle, dependency fingerprints, reuse/invalidation/recovery, provenance, and failure-state behavior. | `Complete + audit PASS` |
| M04 — Synthetic Trajectories and Dataset Authority | Validated prepared laws/data inventories and applicable dataset decisions. | `Complete + audit PASS` |
| M05 — Comparators, Metrics, and Statistical Certification Engine | All scientific algorithms, comparators, metrics, confidence/statistical procedures, and numerical validation interfaces. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Canonical plan/result/failure/completion schemas and experiment workspace | M02 | Schema, physical-type, required-field, and path validation pass. |
| Execution/provenance/runtime substrate | M03 | CLI lifecycle, identity, reuse, recovery, and failure semantics validate. |
| Prepared laws/data inventories | M04 | Schema-valid, provenance-complete, and dependency-compatible. |
| Scientific computation/statistical engine | M05 | All method-level acceptance tests pass before registry execution consumes the interfaces. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I38` — Implement Exact 1,423-Cell Authoritative Experiment Registry and Plan Expansion | `outputs/artifacts/derived/plans/experiment_plan.json` | §17 — Authoritative Experiment Registry | 102 atomic requirements | `I17`, `I24`, `I29`, `I37` |
| 2 | `I39` — Implement Experiment Dependency, Output, and Completion Map | Machine-readable experiment dependency/output map | §18.0 — Experiment dependency and required-output map | 62 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I38` |
| 3 | `I40` — Implement Scientific/Data Inventory Experiment and Deterministic Rho-Offset Resolution | Scientific/data inventory experiment records | §18.1 — Inventory validation — Scientific and Data Inventory; §18.2 — Formal mathematics validation; Rho-offset resolution | 14 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I39` |
| 4 | `I41` — Execute Population Solver, Comparator, Partition/Timing, Compatibility, Sharpness, and Safety Validation | Authoritative population/oracle validation evidence | §18.3 — Solver validation — Production Solver vs Independent Oracle; §18.4 — Comparator reduction; §18.5 — Partition and timing mechanism; §18.6 — Compatibility, sharpness, and safety | 59 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I40` |
| 5 | `I42` — Execute Anytime Hand Cases and Independent Certified-Projection Oracle | Ten hand-case result/evidence sets | §18.7 — Finite-sample implementation validation — Anytime Implementation Hand Cases; Hand-case applicability; Independent projection oracle | 78 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I40` |
| 6 | `I43` — Execute Anytime Coverage Stress, Population Materiality, and Sequential Utility Analysis | Anytime coverage-stress evidence | §18.8 — Anytime coverage validation — Anytime Coverage Stress; §18.9 — Utility analysis; Population materiality; Sequential utility | 39 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I42` |
| 7 | `I44` — Execute Failure-Boundary Atlas, Planned Nonapplicabilities, and Computational Scaling | Failure-boundary atlas source data | §18.10 — Failure-boundary analysis — Failure Boundary Atlas; §18.11 — Planned nonapplicabilities; §18.12 — Computational scaling | 48 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I40` |
| 8 | `I45` — Implement Authoritative Statistical Synthesis | Project-level statistical synthesis records | §18.13 — Statistical synthesis | 16 atomic requirements | `I17`, `I24`, `I29`, `I37`, `I41`, `I42`, `I43`, `I44` |
| 9 | `I46` — Audit Authoritative Experiment Registry and Execution Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §17–§18; Milestones document — M06 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I17`, `I24`, `I29`, `I37`, `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Authoritative machine-readable 1,423-cell experiment registry/plan | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` | Exact cell-count, row-order, semantic-coordinate, evidence-class, and dependency validation | Experiment execution, M07, M08 |
| Anytime implementation hand-case suite and independent projection-oracle evidence | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` | Every declared hand case uses exact fixture settings/expected state; applicability passes; production certified uppers are not anti-conservative relative to the independent oracle beyond tolerance | Experiment validation, M07, M09 |
| Per-cell authoritative results and completion evidence for every required executable experiment | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` | Schema, dependency, numerical, completion-marker, and provenance validation | M07, M08 |
| Experiment-level aggregates, diagnostics, and reusable intermediate artifacts | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` | Required-output map and dependency-fingerprint validation | M07, M08 |
| Statistical Synthesis outputs and project evidence map | `I38`, `I39`, `I40`, `I41`, `I42`, `I43`, `I44`, `I45` | All mandatory upstream evidence present/valid; roadmap-defined synthesis and hostile-review precursor checks pass | M07, M08, M09 |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M02, M03, M04, and M05 are complete and their milestone audits are `PASS`.
- The canonical experiment schemas/workspace are validated before plan materialization or result persistence.
- The runtime can plan/run/reuse/recover artifacts with exact provenance and dependency identity.
- All scientific methods and prepared inputs required by the registry and implementation hand cases are validated before confirmatory execution begins.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- The authoritative registry contains exactly 1,423 planned cells in the required experiment order and semantic coordinate system.
- Every §18.7 implementation hand case, including the internally numbered §1–§10 fixtures, passes with its exact declared settings and expected scientific/execution state.
- The independent projection oracle is implemented independently of the production projection path and no production certified upper is anti-conservative relative to a verified feasible oracle value beyond the declared tolerance.
- Every roadmap-required executable cell has its required schema-valid result, dependencies, completion marker, and provenance; deliberately non-executed/nonapplicable states follow the roadmap contract.
- All required experiment-level aggregates, diagnostics, source data, and statistical outputs exist and validate.
- Missing, stale, invalid, or technically failed mandatory evidence blocks synthesis exactly as specified; valid nulls/falsifications remain completed scientific evidence rather than technical failures.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Exact registry/plan expansion; all §18.7 hand cases and independent projection oracle; experiment e2e runs; per-cell schema/completion/provenance validation; numerical gates; aggregate/statistical outputs; synthesis completeness checks. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §17–§18 registry, dependency, execution, output, and statistical-synthesis contracts.
- It does not own manuscript table/figure rendering or final claim-state presentation, though it produces the authoritative evidence they consume.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M07 — Manuscript Evidence and Claim Evaluation
> **Outcome:** Authoritative scientific evidence is deterministically rendered into the required manuscript tables and figures, evaluated against every roadmap claim-support rule, and recorded with explicit non-suppressible claim states.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§12 and §19–§22` |
| Requirement ownership | `REQ-1744–REQ-1763, REQ-2875–REQ-3215, REQ-3413` |
| Upstream milestones | `M02, M06` |
| Implementation issues | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I53` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §12 — Manuscript evidence contract | Machine-readable/manuscript evidence authority, evidence-role separation, source-data obligations, and manuscript-facing evidence constraints. | `REQ-1744–REQ-1763` | `I47` | Evidence-lineage tests prove manuscript outputs are derived only from authoritative validated source data and preserve evidence-role constraints. |
| §19 + Tables 1–4 — Scientific constants, laws, assumptions, and experiment matrix | General table contract plus Tables 1–4 schemas, source paths, ordering, and scientific formatting. | `REQ-2875–REQ-2927` | `I47` | `trajcert report` integration tests render required CSV/TeX outputs solely from verified source data with exact columns, paths, ordering, and formatting. |
| Tables 5–9 — Validation, partition/timing, safety, and anytime tables | Theorem, production/oracle, partition/timing, compatibility/sharpness/safety, and anytime-validity table contracts. | `REQ-2928–REQ-2991` | `I47` | Deterministic render/source-data tests verify exact table schemas, authoritative inputs, null/status rules, and scientific values. |
| Tables 10–13 — Sensitivity/utility, failure, scaling, and claim registry tables | Sensitivity/utility, failure-boundary, computational-scaling, and claim-registry table contracts. | `REQ-2992–REQ-3051` | `I52` | Report tests verify exact source paths, columns, ordering, claim-state fields, and no unsupported/hand-edited manuscript values. |
| §20 + Figures 1–4 — Core scientific figures | General figure contract plus partition coherence, exact timing value, information/safety corridor, and representative anytime certificate figures. | `REQ-3052–REQ-3096` | `I48` | Figure source-data and render tests verify exact settings/axes/content and deterministic SVG/PNG outputs without smoothing or cherry-picking. |
| Figures 5–8 — Stress, sensitivity, failure-boundary, and scaling figures | Anytime stress validity, full-rho sensitivity, failure-boundary atlas, and computational-scaling figures. | `REQ-3097–REQ-3114` | `I48` | Figure tests verify declared source data, axes/settings, deterministic rendering, and required failure/scaling annotations. |
| §21.1–§21.6 — Coherence, timing, compatibility, sharpness, safety, and impossibility analyses | Primary claim-support analyses for partition coherence, timing decomposition, compatibility floor, sharp risk sets, strict timing value, and intrinsic impossibility. | `REQ-3115–REQ-3147` | `I49` | Analysis tests recompute required quantities from authoritative evidence and enforce declared claim boundaries, including the prohibition on claiming bins always strictly help. |
| §21.7–§21.11 — Anytime validity, nonvacuity, operational gain, tractability, and local validity | Claim-support analyses for anytime-valid local certification, synthetic nonvacuity, trajectory operational gain, computational tractability, and non-federated local validity. | `REQ-3148–REQ-3178` | `I50` | Analysis/evidence tests verify the declared support relations, materiality conditions, and applicable scientific states. |
| §21 — Static dependency and runtime lineage audits | Static dependency audit and runtime input-lineage audit supporting scientific evidence integrity. | `REQ-3179–REQ-3204` | `I50` | Static/runtime lineage checks prove each reported number traces to the declared producers, material inputs, and authoritative experiment evidence. |
| §21.12 — Real-trajectory value | Real-trajectory evidence interpretation and explicit non-extrapolation boundary. | `REQ-3205–REQ-3207` | `I51` | Traceability and claim checks validate the allowed real-trajectory interpretation and reject any implication of real operational validation. |
| §22 — Claim-state semantics | Exact claim-state vocabulary, definitions, transitions/usage, and preservation of null, conditional, mechanism-only, unsupported, and not-tested outcomes. | `REQ-3208–REQ-3215, REQ-3413` | `I51` | Claim-registry tests enforce the exact vocabulary and reject hidden unfavorable/null outcomes or unsupported strengthening. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M02 — Reference Architecture, Workspace, and Schemas | Canonical evidence/result schemas and manuscript/source-data artifact locations. | `Complete + audit PASS` |
| M06 — Authoritative Experiment Registry and Execution | Complete authoritative experiment outputs, aggregates, statistical synthesis, and evidence map. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Authoritative result/aggregate Parquet and source data | M06 | Schema-valid, complete, provenance-compatible, and non-stale. |
| Statistical Synthesis/project evidence map | M06 | All mandatory synthesis inputs valid; no blocked mandatory evidence. |
| Canonical manuscript/evidence schemas and workspace paths | M02 | Exact schema/path validation. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I47` — Implement Manuscript Evidence Contract and Generate Tables 1–9 | Tables 1–9 verified source data and manuscript renderings | §12 — Manuscript Evidence Contract; §19 — Required Tables; Table 1 — Scientific constants and numerical protocol; Table 2 — Synthetic laws; Table 3 — Baseline assumptions; Table 4 — Experiment matrix; Table 5 — Theorem validation; Table 6 — Production/oracle validation; Table 7 — Partition coherence and timing; Table 8 — Compatibility, sharpness, safety; Table 9 — Anytime validity | 134 atomic requirements | `I17`, `I46` |
| 2 | `I48` — Generate Required Scientific Figures 1–8 | Figures 1–8 verified source-data artifacts and deterministic SVG/PNG renderings | §20 — Required Figures; Figure 1 — Partition coherence at fixed sensitivity; Figure 2 — Exact timing value; Figure 3 — Information profile and safety corridor; Figure 4 — Representative anytime certificates; Figure 5 — Anytime stress validity; Figure 6 — Full rho sensitivity; Figure 7 — Failure-boundary atlas; Figure 8 — Computational scaling | 62 atomic requirements | `I17`, `I46` |
| 3 | `I49` — Evaluate Claims 21.1–21.6: Coherence, Timing, Compatibility, Sharpness, Safety, and Impossibility | Machine-readable claim records for §21.1–§21.6 | §21.1 — Partition Coherence; §21.2 — Observable Timing Decomposition; §21.3 — Exact Compatibility Floor; §21.4 — Sharp Latent-Risk Set; §21.5 — Strict Timing Value; §21.6 — Intrinsic Certification Impossibility | 31 atomic requirements | `I17`, `I46` |
| 4 | `I50` — Evaluate Claims 21.7–21.11 and Perform Local-Validity Dependency/Lineage Audits | Claim records for §21.7–§21.11 | §21.7 — Anytime-Valid Local Certificate; §21.8 — Practical Synthetic Nonvacuity; §21.9 — Trajectory Operational Gain; §21.10 — Computational Tractability; §21.11 — Local Validity Without Federation; Static dependency audit; Runtime input-lineage audit | 57 atomic requirements | `I17`, `I46` |
| 5 | `I51` — Evaluate Real-Trajectory Claim and Enforce Exact Claim-State Semantics | Real-trajectory `NOT_TESTED` claim record | §21.12 — Real-Trajectory Value; §22 — Claim-State Semantics | 12 atomic requirements | `I17`, `I46`, `I49`, `I50` |
| 6 | `I52` — Generate Sensitivity, Utility, Failure, Scaling, and Claim Tables 10–13 | Tables 10–13 stable source data | Table 10 — Sensitivity and utility; Table 11 — Failure boundaries; Table 12 — Computational scaling; Table 13 — Claim registry | 60 atomic requirements | `I17`, `I46`, `I49`, `I50`, `I51` |
| 7 | `I53` — Audit Manuscript Evidence and Claim Evaluation Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §12 and §19–§22; Milestones document — M07 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I17`, `I46`, `I47`, `I48`, `I49`, `I50`, `I51`, `I52` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Implemented manuscript-evidence contract | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` | Evidence-source linkage and manuscript-scope validation passes | M08, manuscript export |
| All required manuscript tables with authoritative machine-readable sources | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` | Deterministic Parquet/CSV/TeX schema/content validation | M08, manuscript |
| All required figures with authoritative source data | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` | Exact SVG/PNG/source-data/settings validation with no hidden filtering or post-selection | M08, manuscript |
| All §21 scientific claim-support evaluations | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` | Every roadmap-defined support condition/gate is evaluated against authoritative evidence | Claim registry, M08 |
| Complete claim registry with exact §22 states | `I47`, `I48`, `I49`, `I50`, `I51`, `I52` | Exact vocabulary/state-assignment tests; unfavorable/null/not-supported results retained | M08, manuscript |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M02 and M06 are complete and their milestone audits are `PASS`.
- All mandatory authoritative experimental outputs and Statistical Synthesis evidence needed by reporting are present, valid, and non-stale.
- Canonical manuscript/source-data schemas and output paths are available before rendering.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every roadmap-required table is a deterministic render of authoritative machine-readable source data with exact schema/content and required CSV/TeX outputs.
- Every roadmap-required figure is rendered from exact authoritative source data/settings and obeys all anti-selection/smoothing/filtering restrictions.
- Every §21 support rule is evaluated objectively against the required evidence, including negative and failure-boundary evidence.
- Every claim receives exactly one valid §22 claim state and no unfavorable result is hidden, dropped, or rhetorically promoted beyond its evidence.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Deterministic table/figure render tests; source-data schema/provenance checks; exact claim-gate evaluations; claim-state vocabulary/assignment tests; anti-selection checks. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §12 and §19–§22 evidence rendering, scientific support evaluation, and claim-state requirements.
- It may summarize authoritative outputs but may not recompute or redefine upstream scientific methods, experiment cells, thresholds, or acceptance gates.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M08 — Evidence Closure, Reproducibility, and Manuscript Export
> **Outcome:** All scientific evidence reaches roadmap-defined completion, reproducibility inputs and lineage are closed, and manuscript exports are traceable from every reported number back to authoritative artifacts and material dependencies.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§23–§24` |
| Requirement ownership | `REQ-3216–REQ-3284` |
| Upstream milestones | `M03, M06, M07` |
| Implementation issues | `I54`, `I55` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I56` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §23 — Evidence completion and reproducibility closure | Single execution regime, cell/experiment completion semantics, valid null/boundary/falsification treatment, evidence completeness, and stale/invalid blocking. | `REQ-3216–REQ-3258` | `I54` | Completion/evidence-closure tests verify every required cell/experiment state, blocking rule, provenance requirement, and non-stale evidence condition. |
| §24–§24.1 — Reproducibility and manuscript export | Complete reproduction-input set, manuscript-number lineage, evidence manifests, source/dependency/container identity, canonicalization, and normative serialization reference. | `REQ-3259–REQ-3284` | `I55` | Clean reproduction/export checks rebuild authoritative outputs from locked inputs and verify canonical identities, manifests, lineage, and deterministic manuscript export. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M03 — Semantic Identity, Provenance, CLI, and Failure Semantics | Stable provenance, dependency fingerprints, canonical identity, and stale/recovery semantics. | `Complete + audit PASS` |
| M06 — Authoritative Experiment Registry and Execution | Complete executable experiment evidence, completion markers, aggregates, and statistical synthesis. | `Complete + audit PASS` |
| M07 — Manuscript Evidence and Claim Evaluation | Validated manuscript source data, tables/figures, support evaluations, and claim registry. | `Complete + audit PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Experiment completion markers, results, aggregates, and evidence map | M06 | Complete, schema-valid, provenance-compatible, and non-stale. |
| Tables/figures/source data and claim registry | M07 | Deterministic, authoritative-source-linked, and claim-state valid. |
| Dependency fingerprints and provenance envelope | M03 | Canonical identity/integrity validation passes. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I54` — Implement Evidence Completion, Atomic Closure, and Reproducibility Gates | Canonical cell/experiment/project completion verifier | §23 — Evidence Completion and Reproducibility Closure | 43 atomic requirements | `I24`, `I46`, `I53` |
| 2 | `I55` — Implement Reproducibility Bundle and Verified Manuscript Export | Complete project reproducibility bundle | §24 — Reproducibility and Manuscript Export; §24.1 — Normative canonicalization reference | 26 atomic requirements | `I24`, `I46`, `I53`, `I54` |
| 3 | `I56` — Audit Evidence Closure, Reproducibility, and Manuscript Export Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §23–§24; Milestones document — M08 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I24`, `I46`, `I53`, `I54`, `I55` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Project evidence-completion record | `I54`, `I55` | Every required cell/experiment/evidence state is accounted for under §23 completion semantics | M09 and final project closure |
| Complete reproducibility input manifest | `I54`, `I55` | Source commit, lockfile, container, roadmap, config, generators/seeds, producer dependency map, and all required identities validate | Independent reproduction |
| Manuscript evidence export with number-to-source lineage | `I54`, `I55` | Every exported number traces through source data, result/aggregate artifacts, experiment identity, config, dependencies, and project evidence manifest | Manuscript and M09 |
| Canonical integrity/dependency manifests | `I54`, `I55` | Canonicalization, hash, semantic-coordinate, and dependency-fingerprint checks pass | M09 and independent audit |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M03, M06, and M07 are complete and their milestone audits are `PASS`.
- All required experiment and manuscript evidence exists before project-level closure is evaluated.
- No mandatory evidence is stale, dependency-incompatible, invalid, or technically failed unless the roadmap explicitly permits that scientific state.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every required registry cell and experiment is accounted for under the exact §23 completion rules, including valid scientific nulls, boundaries, incompatibilities, and falsifications.
- All mandatory evidence is present, valid, non-stale, and lineage-compatible; missing/stale/invalid mandatory evidence prevents closure.
- The full §24 reproduction-input set is captured and sufficient to reconstruct the authoritative execution context.
- Every manuscript number/exported result has complete, machine-checkable lineage to authoritative source data, experiment identity, configuration, dependencies, and the project evidence manifest.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Project completion-accounting checks; stale/missing/invalid evidence gates; reproduction-input manifest validation; canonical digest checks; manuscript number-to-source lineage reconstruction. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §23–§24 evidence completion, reproducibility closure, and manuscript-export lineage requirements.
- It does not reinterpret scientific results or claim states; it proves that completed evidence and manuscript exports are complete, compatible, and reproducible.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.

---

# M09 — Roadmap-Wide Verification and Operator Readiness
> **Outcome:** The complete TrajCert implementation passes the roadmap-wide deterministic, integration, hostile-review, and normal-operator workflow contracts end to end with no unresolved blocking verification finding.
## At a Glance
| Field | Value |
|---|---|
| Roadmap scope | `§26–§28` |
| Requirement ownership | `REQ-3304–REQ-3407` |
| Upstream milestones | `M01–M08` |
| Implementation issues | `I57`, `I58`, `I59` |
| Coverage authority | `Roadmap Coverage Inventory` |
| Audit issue | `I60` |
| Audit status | `PENDING` |

## Coverage

The Roadmap Coverage Inventory is the traceability authority for this milestone. Every roadmap requirement owned by this milestone is allocated to exactly one primary milestone here; implementation-issue references remain unassigned until real issues are created.

| Roadmap Section | Scope / Work Package | Requirement IDs | Implementation Issue(s) | Verification / Evidence |
|---|---|---|---|---|
| §26 — Test contract | Roadmap-wide deterministic/unit, property, integration, schema, numerical, provenance, CLI, experiment, negative-path, and end-to-end coverage. | `REQ-3304–REQ-3365` | `I57` | Required test suite executes every declared edge/failure case and passes all roadmap-defined deterministic, integration, numerical, provenance, CLI, and e2e gates. |
| §27 — Hostile reviewer verification | Independent verification of evidence lineage, scientific/numerical claims, completeness, hidden-failure absence, and machine-readable evidence pointers. | `REQ-3366–REQ-3373` | `I58` | Hostile-review verification independently traces claims to evidence and blocks on missing, stale, incompatible, hidden, or unsupported results. |
| §28 — Normal operator workflow | Exact dependency-ordered `trajcert` workflow, reuse/invalidation/recovery behavior, and operator-facing prohibitions. | `REQ-3374–REQ-3407` | `I59` | Full operator e2e run validates command order, read/write semantics, expected artifacts, reuse/invalidation/recovery, and final report readiness. |

### Coverage Rules

- Every mandatory requirement owned by this milestone must be present in the Roadmap Coverage Inventory.
- Every mandatory implementation requirement must map to at least one implementation issue before implementation begins.
- Every conditional requirement must remain traceable and must be implemented when its roadmap-defined condition applies.
- Requirements marked `NON_IMPLEMENTATION` inside the owned ranges remain traceable methodological, terminology, exclusion, invariant, or claim constraints and must not be converted into fictitious implementation work.
- Every mapped requirement must have objective verification or evidence.
- Every implementation issue must reference the exact requirement IDs it satisfies.
- A requirement is not considered covered merely because it falls inside a requirement range or roadmap section assigned to the milestone.
- Requirement ranges may span intentional identifier gaps; only actual inventory requirements are covered, and no existing requirement assigned to another milestone is captured by a range.
- No blocking requirement may remain `UNMAPPED` or `AMBIGUOUS` when implementation begins.
- No issue may redefine, weaken, silently reinterpret, duplicate, or extend the authoritative roadmap requirement it implements.

## Dependencies

### Milestone Dependencies

| Milestone | Required Input / Contract | Entry Gate |
|---|---|---|
| M01–M08 — all prior implementation milestones | Complete scientific/configuration contracts, architecture/runtime, data, methods, experiments, manuscript evidence, and reproducibility-closure artifacts required for integrated verification. | `All complete + all audits PASS` |

### Artifact / Interface Dependencies

| Dependency | Produced By | Required Validation |
|---|---|---|
| Complete integrated `trajcert` implementation and all milestone artifacts | M01–M08 | Every upstream deliverable validates under its declared contract and is non-stale. |
| Project evidence and reproducibility manifests | M08 | Evidence closure and manuscript lineage pass before final hostile-review/operator validation. |

Dependency completion alone is not sufficient. Every consumed dependency must be present, valid, provenance-compatible where applicable, and compatible with the active roadmap contract.

## Implementation Issues

Implementation issues for this milestone are listed below; each issue's detailed task checklist, acceptance criteria, and required tests are defined in `Issues.md`.

| Order | Issue | Work Package | Roadmap Scope | Requirement Coverage | Depends On |
|---:|---|---|---|---|---|
| 1 | `I57` — Implement Roadmap-Wide Deterministic, Property, Integration, and Regression Test Contract | Complete automated roadmap test suite | §26 — Test Contract | 60 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I37`, `I46`, `I53`, `I56` |
| 2 | `I58` — Implement Hostile Reviewer Verification and Evidence-Pointer Gate | Hostile-review machine-readable evidence pointers | §27 — Hostile Reviewer Verification | 8 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I37`, `I46`, `I53`, `I56`, `I57` |
| 3 | `I59` — Implement and Verify Normal Registry-Driven Operator Workflow | Verified normal operator workflow | §28 — Normal Operator Workflow | 34 atomic requirements | `I08`, `I17`, `I24`, `I29`, `I37`, `I46`, `I53`, `I56`, `I57`, `I58` |
| 4 | `I60` — Audit Roadmap-Wide Verification and Operator Readiness Milestone Completion | Independent milestone audit result with complete requirement, test, deliverable, provenance, and downstream-readiness evidence | §26–§28; Milestones document — M09 coverage, dependencies, deliverables, exit criteria, acceptance evidence, and Milestone Audit contract | Audit / milestone-completion gate — no new primary requirements | `I08`, `I17`, `I24`, `I29`, `I37`, `I46`, `I53`, `I56`, `I57`, `I58`, `I59` |

### Issue Contract

Every milestone issue must:

- reference its exact roadmap section(s);
- list every covered requirement ID;
- contain a detailed implementation checklist;
- define objective acceptance criteria;
- identify required tests;
- identify required artifacts, outputs, or interfaces;
- identify required provenance or manifest updates where applicable;
- identify explicit dependencies on upstream milestones, issues, artifacts, or interfaces;
- preserve roadmap terminology and semantics;
- close only when every mapped requirement and acceptance criterion is satisfied.

## Deliverables

| Deliverable | Source Issue(s) | Required Validation | Downstream Consumer |
|---|---|---|---|
| Complete roadmap-wide automated test suite and results | `I57`, `I58`, `I59` | All mandatory §26 deterministic/unit/property/integration/e2e/negative/reproducibility tests pass | Final milestone audit |
| Machine-readable hostile-review verification record | `I57`, `I58`, `I59` | Every §27 mandatory check has a valid evidence pointer and passes; no blocking finding remains | Final milestone audit |
| Validated normal operator workflow | `I57`, `I58`, `I59` | Fresh execution and reuse/invalidation/recovery workflow follow exact §28 command/order/override rules | Operators and final project completion |
| Final integrated verification evidence | `I57`, `I58`, `I59` | No unresolved blocking test, lineage, workflow, or hostile-review finding remains | Project completion |

All roadmap-required deliverables for this milestone must appear in this table or be explicitly referenced through the Roadmap Coverage Inventory.

## Entry Criteria

Implementation may begin only when all of the following are true:

- M01–M08 are complete and every upstream milestone audit is `PASS`.
- The complete implementation, experiment evidence, manuscript outputs, claim registry, and reproducibility manifests are available as one compatible dependency graph.
- No final verification step requires an operator to choose a scientific configuration value forbidden by §28.
- all roadmap requirements owned by this milestone are present in the Roadmap Coverage Inventory;
- every mandatory implementation requirement is mapped to at least one real milestone issue before implementation begins;
- every mapped requirement has an explicit verification or evidence target;
- no blocking requirement is `UNMAPPED` at implementation start;
- no blocking requirement is `AMBIGUOUS`;
- no unresolved roadmap ambiguity would force the implementer to invent a scientific, mathematical, methodological, numerical, architectural, configuration, artifact, or execution decision.

## Exit Criteria

The milestone is complete only when all of the following are true:

- Every mandatory test category and edge/failure case in §26 passes against the integrated system.
- Every §27 hostile-review check has machine-readable supporting evidence and no mandatory check fails.
- The complete §28 normal operator workflow succeeds in the exact roadmap-defined order, including reuse, invalidation, recovery, and selective recomputation behavior.
- Operators can select only permitted experiment-level actions; scientific configuration, dependency, cache, checkpoint, and execution-group choices remain registry/configuration controlled.
- No unresolved blocking verification finding remains and the milestone audit is `PASS`.
- every mandatory requirement owned by this milestone is satisfied;
- every applicable conditional requirement is satisfied;
- every mapped implementation issue is closed;
- the Roadmap Coverage Inventory contains no unresolved `UNMAPPED` or blocking `AMBIGUOUS` requirement owned by this milestone at completion;
- all required unit, integration, end-to-end, numerical, schema, provenance, and other milestone-applicable tests pass;
- all required deliverables are generated and validate against their roadmap-defined contracts;
- required provenance is complete and valid, and no required evidence is stale or incompatible with its material dependencies;
- the milestone audit is `PASS` with no unresolved blocking finding.

## Acceptance Evidence

| Evidence Area | Required Evidence | Pass Condition |
|---|---|---|
| Requirement coverage | Roadmap Coverage Inventory plus this milestone coverage table | Every owned mandatory/applicable requirement is accounted for exactly once at milestone level with no conflicting primary owner |
| Implementation | Closed real milestone issues linked to exact requirements | Every implementation-bearing requirement has completed issue-level implementation evidence before milestone completion |
| Unit / component validation | Required milestone-specific unit/property/schema/structural test results | All required component-level checks pass |
| Integration / execution validation | Required milestone-specific integration/e2e results | All owned integration paths and lifecycle semantics pass |
| Scientific / functional validation | Complete test-suite results; hostile-review machine-readable evidence pointers; fresh/reuse/recovery operator-workflow e2e runs; forbidden-override and dependency-driven recomputation checks. | All roadmap-defined conditions applicable to this milestone pass without weakening or reinterpretation |
| Deliverables | Required outputs and artifacts listed above | Complete, readable, schema/contract-valid, and consistent with the active roadmap requirements |
| Provenance | Required manifests, dependency identities, source-data links, and compatibility evidence | Complete and sufficient to verify origin, compatibility, integrity, reuse, and staleness where applicable |
| Audit | Milestone audit issue | Final result is `PASS` with no unresolved blocking findings |

## Milestone Audit

**Audit issue:** `—`

**Audit status:** `PENDING`

The milestone audit is the final completion gate. It must independently verify:

- complete roadmap coverage for all requirements owned by the milestone;
- exact requirement-to-issue traceability;
- closure of every mandatory implementation issue;
- completion and passing status of all required tests;
- completion and passing status of all required validations;
- existence and validity of all required deliverables;
- completeness and validity of required provenance and manifests;
- absence of stale or incompatible evidence;
- absence of unresolved blocking findings;
- readiness of milestone outputs for all declared downstream consumers.

The audit must end in exactly one result:

- `PASS` — every completion condition is satisfied.
- `FAIL` — one or more blocking conditions remain.

A milestone is not complete until the audit result is `PASS`.

## Scope Boundary

- This milestone owns §26–§28 integrated verification and operator-readiness requirements only.
- It verifies but does not redefine the scientific, architectural, experimental, reporting, or reproducibility contracts owned by M01–M08.
- The authoritative roadmap remains the source of scientific, mathematical, methodological, architectural, numerical, configuration, artifact, and execution requirements.
- This milestone may organize implementation work but may not redefine, weaken, extend, or silently reinterpret the roadmap.
- Detailed implementation checklists belong in implementation issues.
- Detailed verification checklists belong in the milestone audit issue.
- Work outside this milestone's mapped roadmap scope must not be added unless the roadmap or coverage inventory is explicitly updated first.
