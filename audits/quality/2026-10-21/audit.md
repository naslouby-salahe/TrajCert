# Source, configuration and repair audit - 21 October 2026

The Sonar repairs and configuration wiring corrections pass verification. The separate review of the earlier numerical changes found no additional enclosure-direction defect in the reviewed paths. Dependency security remains an open finding: pip-audit reports 25 advisories across five locked packages. This is a technical audit of the current working tree, separate from the manuscript's scientific audit.

## Repairs

The original 11 Sonar findings are resolved. Exact binary64 sentinel and endpoint checks now use integer ratios; no tolerance was substituted. Confidence inversion retains fail-closed handling of uncertain Arb comparisons. Repeated figure strings are centralized. Tests use monkeypatch for temporary precision changes and isolate the potentially raising call. A subsequent scan found a composite assertion and legacy generic typing; both were corrected.

The first post-push automatic analysis also scanned the audit helper scripts, which the earlier manual scan excluded, and reported eight findings. The helpers now resolve repository paths from their own location, use a securely created temporary trace directory, omit unused pytest hook parameters, share the column-mapping label, and use a deterministic arithmetic sequence for exact-sum diagnostics. Both audit scripts were rerun successfully, and the trace plugin passed 35 enclosure regression tests. The production source and tests were unchanged in this follow-up.

The configuration audit found two operational gaps. Confidence inversion now reads numerics.arbitrary_precision_bits instead of hard-coding 128 bits; the production default remains 128. Both strict-timing experiment dispatch routes now check their declared ZERO/POSITIVE expectation. Duplicate law/partition coordinates are rejected so lookup is unambiguous. These changes affect those validation routes and nondefault precision runs. No laws, budgets, seeds, scientific configurations or saved experimental records were changed.

## Configuration coverage

configuration-usage.json accounts for all 280 declared model fields and 478 canonical field instances. The full test run recorded 248 model-qualified fields read from source outside config.py. The remaining consumers were reviewed statically, including override resolution, per-scenario checkpoints, scaling workers, hand-case optimizer controls and real-data column mappings. Shared model-field evidence does not mean every campaign value or cell was executed.

Some values deliberately describe or validate the configuration. confidence.level and alpha validate their complementary relationship; anytime_delta controls the confidence sequence. grids.beta is a validated provenance reference grid, not an execution grid. schema_version constrains the supported schema. information_roundoff_ulps still has an information-kernel consumer; it was not restored as an arbitrary certification slack. No field is left without an identified role or consumer.

## Separate numerical review

This phase reread the arithmetic, confidence, envelope, projection, certification and oracle paths after the repairs. It checked the following invariants against the source-level argument already recorded in the Supplement:

- Fraction sums and directed conversions enclose exact represented values, including subnormal sums and complements.
- Entropy envelopes use monotonic mass entropy and outward Arb endpoints. The confidence rectangle is intersected with the simplex using directed sums.
- Confidence inversion moves a bracket only after a certified sign. An uncertain interior sign returns an outer fallback; precision contexts are restored.
- The singleton shortcut requires exact rational normalization and aggregate agreement. Its upper endpoint solves the relaxed profile with the entropy upper envelope, retains an outer right bracket, and rounds the objective upward. A verified incumbent checks the actual table and information upper bound.
- General projection prunes only with outward geometry or certified information lower bounds. Node, resolution, stall and arithmetic exits retain surviving bounds, including an active parent when needed.
- Witnesses use exact rational normalization, band membership, entropy containment and an Arb information upper bound. Minimum searches return certified box lower bounds; approximate points affect stopping, not the returned proof direction. Empty minimum queues fall back to zero.
- Certification checks matching sensitivity budgets, upward-rounded strict guards and projection_upper <= risk_budget. The all-unresolved oracle boundary is handled before minimum-singleton logic.

independent_audit.py ran in a separate process with its own 110-decimal-digit entropy and endpoint calculations. All 110 singleton cases enclosed both the original and relaxed reference endpoints. All 1,504 exact-sum checks and 63 outer confidence-root sign checks passed, including 80-, 128- and 160-bit runs. Existing focused tests also cover uncertain signs, normalization fallback, thresholds, pruning, exhaustion and stalls.

This is a source review with independent finite diagnostics, not machine-checked verification. Its enclosure conclusion retains the documented exact-rational, IEEE binary64, Arb enclosure and serial/process-isolation assumptions. It does not attest that the repaired source executed historical experiments. The ordinary population solver remains an approximate scientific calculation; its midpoint outputs are not used as proven certificate bounds without separate verification.

## Executed checks

| Check | Result |
|---|---|
| Full suite with branch-aware coverage | 1,005 passed; 196 warnings; 91.98% coverage, above 90% |
| After final typing/assertion repair | 152 passed, including architecture, telemetry and confidence tests |
| Ruff format/check, basedpyright, source audit | Pass |
| Import contracts, complexity, vulture, deptry | Pass |
| Semgrep | 10 rules, 80 files, zero findings |
| Lock consistency | Pass |
| pip-audit | FAIL: 25 advisories in certifi, mcp, pillow, pyjwt and uv |
| Final Sonar working-tree scan | Zero open issues and review-pending hotspots; quality gate OK; new coverage 92.0% |

Sonar analysis d6aa9af8-4e6d-44e2-b785-623abba6bd9d analyzed the uncommitted working tree, anchored to the existing main revision 1150bed3469761571855b61209c3e1cdd77d8661. It is not a claim that these fixes are committed or present on remote main. Automatic Analysis was temporarily disabled for the manual scan, and restored to its original enabled state. Automatic analysis may therefore display the committed remote source's older findings until these fixes are published. The exact scan snapshot is preserved here.

The additional dependency check prevents an all-green quality claim. These packages are present in the lockfiles, not merely unrelated global tooling. No dependency upgrade was applied in this repair, and no finding was suppressed. See security-dependencies.txt for affected versions and available fixes, including one advisory without a listed fix. Dependency remediation remains separate work; it requires dependency and compatibility review.

## Preservation

All 6,025 protected files match their baseline hashes, including private docs, configurations, manuscript artifacts and lockfiles. No comments or docstrings were added to the changed Python files. Branch paper and HEAD 024b4b5e7e94216b485809cd0a3ffd6e89fbb5f7 are unchanged; nothing is staged, committed or pushed. No full experimental campaign or stream study was run. Test-generated execution logs and plan files were moved outside the repository to /tmp/trajcert-fix-audit/test-generated-outputs. Root outputs and results are absent.
