# Pre-experiment audit progress

## Baseline evidence

- Read the audit objective, complete matrix structure, and roadmap section inventory.
- Fresh pre-remediation Graphify AST extraction completed from the current `src/trajcert`
  tree on 2026-09-13: 80 code files, 2,003 nodes, and 20,972 edges. Raw output is
  in `graphify-before/graphify-out/`.
- Baseline full test suite: `897 passed` in 61.03 seconds.
- Safe CLI baseline: `doctor` passed; `plan` expanded 1,738 executable cells;
  `status` was read-only; no `trajcert run` command was issued.

## Remediation completed so far

- Replaced the obsolete `uv.lock` execution/provenance authority with generated,
  hash-locked `requirements.lock`. Runtime checks, provenance records, reporting,
  and regression fixtures now use the single `requirements.lock` authority.
- `requirements.lock` was generated with pip-tools 7.6.0 and hash checking under
  installed CPython 3.13.12. The roadmap/matrix environment wording was corrected
  from unavailable CPython 3.13.15 to the validated installed interpreter.
- Normalized unreadable/missing report evidence into `InvalidScientificDataError`.
  Thus `trajcert report` refuses incomplete evidence with exit code 30 rather than
  incorrectly treating it as technical exit code 20.

## Verification after remediation

- `python -m pip install --dry-run --require-hashes -r requirements.lock` passed.
- Focused lock/provenance/CLI/report tests: `124 passed`.
- `trajcert doctor` and `trajcert plan` passed using `requirements.lock`.
- Bare `trajcert report` correctly refused absent synthesis evidence with exit code 30.

## Synthetic preprocessing remediation

- `preprocess` now writes one validated prepared-law manifest for each selected law,
  including typed probability masses and the finest-to-coarse partition models.
- The preprocessing inventory records only a scientific specification digest and typed
  manifest identities/checksums; it does not persist a raw configuration model.
- A real `trajcert preprocess --overwrite` prepared all 12 configured laws. A second
  non-overwrite invocation reused the same verified inventory checksum.
- Real HITL-IoT preprocessing verified the pinned checksum, schema, and eligibility
  (127,845 rows; 10,227 eligible). Its reuse gate now validates the pinned raw-data
  checksum, prepared cohort checksum, typed cohort serialization, and active
  specification digest before accepting a cached cohort.
- The real-data preparation inventory now persists typed `documented_expected_value`
  and `observed_raw_dataset_value` structures, including source reference, file/row/entity
  counts, raw schema, duplicate-check key, decision-latency field, discrepancy,
  and field-mapping status. The inspected CSV has 19,177 observed attack rows versus
  19,215 documented; this 38-row difference is preserved, and the source release identity
  is not claimed as verified.

## Pre-campaign design decision (resolved)

- `STAT-026` is resolved prospectively. The utility sample is now 6,000 paired streams
  per law/rho condition. The observed-effect materiality filter remains 0.05, the test
  remains one-sided against zero gain, and the 54-test Holm family is unchanged.
- A 0.07 paired gain is the prespecified methodological design target, not an
  empirically validated domain minimum. Exact DESIGN_ONLY integration of the complete
  gate, including the configured bootstrap/sign-flip procedures and conservative
  first Holm step, finds a minimum of 5,272 streams for 80% three-law power; rounding
  to 6,000 gives 83.40%. Power at the 0.05 boundary is 12.90%, due to the observed
  effect filter. The analysis generated no TrajCert streams or campaign evidence.

## Latest verification

- Final Graphify refresh on 2026-09-25: 79 code files, 1,738 nodes, 7,920 edges,
  and 192 static-incoming candidates. Candidate classifications and multigraph
  limitations are recorded in `callgraph.md`.
- The public CLI dispatcher has direct static edges to all seven declared workflow
  handlers: doctor, preprocess, plan, smoke, run, status, and report.
- Current plan expansion is 1,738 cells across exactly 29 registered experiment families.
- Final Linux `nox -s tests`: 893 passed in 172.94 seconds at 91.49% coverage;
  14 warnings are third-party matplotlib/pyparsing deprecations. The focused final
  UNC-path regression run passed 46 tests in 1.21 seconds.
- Final Linux `nox -s quality` passed formatting, Ruff, BasedPyright (0 diagnostics),
  Semgrep (79 files, 0 findings), import contracts, source audit, complexity, Vulture,
  Deptry, and pip-audit.
- Final safe CLI: doctor PASS; plan 1,738/0 invalid; smoke 6/6; status 0 complete,
  0 failed, 29 blocked; report refused missing evidence with exit 30. HITL-IoT
  preprocessing validated the pinned source and its second invocation reused the
  verified prepared artifact. No campaign command was run.
- The DESIGN_ONLY power integration was rerun against final config: at planning gain
  0.07, 6,000 streams yield 83.3959% full three-law-gate power; minimum n is 5,272
  for the 80% target. It generated no event streams or campaign evidence.
- Final micro-audit verified 24 Same Endpoint, Different Timing cells (4 partitions ×
  6 configured rho values), corrected the stale matrix entry, and added a regression
  that keeps the family aligned with the configured plan. The total remains 1,738.
- The implemented raw-mean sign-flip test has asymptotic validity for the one-sided
  nonpositive-mean null under the documented independent bounded-stream conditions;
  finite-sample validity for a general mean null requires sign symmetry. Holm allows
  arbitrary dependence only when its individual p-values are valid, so this family’s
  control is asymptotic under current assumptions.
- The final focused micro-audit selection passed 117 tests in 21.25 seconds; full suite
  passed 893 tests with 91.49% coverage, and final quality checks passed.
