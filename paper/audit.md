# TrajCert: Independent Scientific and Journal-Readiness Audit

Audited article: *TrajCert: Sharp risk identification and anytime-valid certification with informative outcome-resolution paths*. Assessment date: 20 October 2026. Repository: `/home/naslouby/Projects/TrajCert`, branch `paper`, HEAD `e628f0a`; the article identifies inspected scientific-code commit `6a37400fc10e977d4c568d7e94d88f3f49dd67aa`.

The authorities are `paper/main.tex`, its eight section inputs, `paper/preamble.tex`, `paper/references.bib`, `paper/supplementary/supplement.tex`, the four generated table inputs, three figure PDFs, `paper/main.pdf` (17 pages), and `paper/supplementary/supplement.pdf` (6 pages). Both published-location PDFs are byte-identical to their corresponding build PDFs. Historical campaign documents and earlier audits are leads, not independent evidence. This document assesses the current sources and records; it does not implement revisions.

## 1. Executive assessment

**Scientific assessment.** The central identification results survive independent reconstruction. The scalar completion, mutual-information profile, compatibility floor, constructive sharpness, refinement increment, strict-improvement condition and risk-budget frontier are sound, with one local qualification needed for the fully resolved boundary. The categorical mixture argument and projection theorem are valid under their stated conservative-computation hypothesis. The contribution is a useful exact specialization and integration of established principles, rather than a new information identity or a new general confidence-sequence construction. No verified result warrants discarding these contributions.

**Readiness.** A defensible journal submission is achievable through a finite revision. The current article is not ready for submission: its implementation-level numerical-enclosure claim needs correction or narrower scope, the interpretation of finite-sample resolution cost omits important optimizer non-resolution, and author information and declarations are unfinished. No Critical defect was established. There are **17 retained findings: 3 Major, 10 Moderate and 4 Minor**. Four are Required, eleven Strongly recommended and two Optional. Severity and priority are distinct.

**Verified strengths.** Independent 70-digit calculations reproduce the displayed population bounds and frontiers. All 160 checkpoint certification counts in 32 power cells were reconstructed from 320 original batches; the exact binomial calculations and the publication CSV/Parquet relationships pass read-only validation. All 116 rendered-artifact source/destination pairs match their hashes. The evidence archive's 523 payload files match both its manifest and the current repository. The 136 math/inference unit tests pass in an isolated workspace. Every page of both manuscript PDFs was visually inspected, with no substantive clipping, overlap, missing equation or unreadable main table found.

**Highest-return corrections.**

1. Resolve the distinction between an analytically conservative projection and every floating-point execution. A deterministic singleton example returns an upper endpoint about `6.03e-14` below the high-precision solution; ordinary objective sums can also round down. This does not demonstrate a false risk certificate in the published experiment.
2. Explain which failed certifications are refuted by a feasible incumbent and which remain numerically unresolved. At 50,000 events in the matched two-band control, 67 of 96 decision-targeted streams stalled, one was refuted, 27 certified and one had stopped after an empty region. The current causal attribution to statistical dimension and relaxation alone is incomplete.
3. Preserve the strong headline while reporting its supporting decomposition: at 5,000 events, two bands certify 100/100; the endpoint search reports refutation in 89/96 decision-targeted streams and unresolved search in seven. The early advantage is not explained solely by optimizer stalls.
4. Strengthen the interpretation and elicitation of the total-information budget and contrast the closest missing-data, multinomial-CS and sequential partial-identification literature. The paper already explains equal absolute versus equal excess budgets; that is a strength, not an unaddressed mathematical defect.
5. Complete declarations and improve the archived design/runtime record without presenting acknowledged provenance limitations as verified reproducibility.

Journal fit and anticipated reviewer reactions below are reasoned judgments, not empirical acceptance probabilities. The literature search found no verified equivalent of the entire profile/frontier/finite-sample projection construction, but cannot establish exhaustive priority. Two cited works remain incompletely accessible for fresh full-text verification.

## 2. Prioritized action plan

| ID | Severity | Priority | Location | Finding | Required action |
|---|---|---|---|---|---|
| TC-ROUNDING-SCOPE | Major | Required | sequential.tex:53-55; supplement.tex:96-100; projection.py:85,214 | End-to-end upper enclosure is stronger than what all numerical paths establish | Narrow the implementation claim or supply a complete outward-rounding justification; exclude approximate singleton results from verified-certificate claims |
| TC-NUMERICAL-NONRESOLUTION | Major | Required | results.tex:22,39; discussion.tex:6 | Resolution-cost interpretation omits stalled numerical searches | Add state/termination decomposition from existing records and revise attribution |
| TC-DECLARATIONS | Major | Required | main.tex:16-17; declarations.tex:5-11 | Author identity and declarations are unfinished | Authors complete and approve all factual statements and disclosure |
| TC-THEOREM-STATEMENTS | Minor | Required | identification.tex:19 | Fully resolved sentence needs the compatibility qualification | State singleton only when rho is at least the floor |
| TC-ORACLE-DEGENERACY | Moderate | Strongly recommended | math/oracle.py:300-345 | Independent oracle collapses the flat zero-resolved profile to a singleton | Correct the diagnostic boundary and add a focused oracle test in a later authorized task |
| TC-PRIOR-ART | Moderate | Strongly recommended | introduction.tex:14,22; sequential.tex:10-24,55 | Closest fixed-time sensitivity and sequential predecessors could be compared more precisely | Add a small targeted set with explicit contrasts and point-of-use attribution |
| TC-BUDGET-DIRECTION | Moderate | Strongly recommended | identification.tex:61-63; main.tex:19 | Correct budget-accounting identity could be given a clearer substantive interpretation | Explain what total-budget narrowing does and does not establish |
| TC-RHO-CALIBRATION | Moderate | Strongly recommended | model.tex:24; results.tex:15,20 | Nats are difficult to elicit operationally | Report upper-end unresolved harm and implied odds ratios as conditional sensitivity summaries |
| TC-RUNTIME-REPORTING | Moderate | Strongly recommended | results.tex:54; supplement.tex:104-117 | Published benchmark omits decision-boundary runtime scale | Add saved power-checkpoint runtime summary and its denominator |
| TC-INCOMPATIBILITY-DETECTION | Moderate | Strongly recommended | results.tex:51; sequential.tex:73 | False-budget example lacks the observed zero incompatibility-detection count | Report zero detection without implying the safeguard validates rho |
| TC-PILOT-DISCLOSURE | Moderate | Strongly recommended | experiments.tex:26; supplement.tex:136 | Pilot influence on horizons and comparator selection is not described | Summarize the documented exploratory design decisions and long-horizon pilot |
| TC-ARCHIVE-EQUIVALENCE | Moderate | Strongly recommended | declarations.tex:3; supplement.tex:124,128,136 | Frozen-design and source-equivalence evidence is not fully portable | Archive design/pilot/equivalence artifacts with accurately bounded provenance |
| TC-FULL-LAW-STABILITY | Minor | Strongly recommended | sequential.tex:3-8,60 | Fixed latent target is implicit in the reference to the true full law | Make the shared target/full-law interpretation explicit |
| TC-LONG-HORIZON-VALIDITY | Moderate | Strongly recommended | results.tex:44,51 | Existing longer-horizon CS diagnostics can strengthen empirical context | Add deduplicated descriptive exclusions, with dependence and stopping caveats |
| TC-WRITING-REGISTER | Minor | Strongly recommended | experiments.tex:40; results.tex:3,5,44,61 | Some process-log language obscures scientific interpretation | Apply the specific meaning-preserving edits in section 10 |
| TC-REAL-DATA | Moderate | Optional | discussion.tex:8; experiments.tex:3 | An application could improve uptake, but is unnecessary for current claims | Consider a separate illustrative workflow only if a suitable dataset exists |
| TC-REJECTION-COROLLARY | Minor | Optional | sequential.tex:73 | Conservative rejection states admit a useful explicit probabilistic interpretation | Add a short conditional corollary if useful to the chosen readership |

Locations are repository-relative in this report. `supplement.tex` means `paper/supplementary/supplement.tex`; manuscript section filenames mean `paper/sections/`; implementation paths are given in full below. No recommendation authorizes changes during this audit.

## 3. Required pre-submission fixes

### TC-ROUNDING-SCOPE

**Finding ID:** TC-ROUNDING-SCOPE  
**Severity:** Major  
**Priority:** Required  
**Location:** `paper/sections/sequential.tex:53-55`; `paper/supplementary/supplement.tex:96-100`; `src/trajcert/inference/projection.py:85-86,214-245,773-816,1164-1165`; `src/trajcert/inference/envelope.py:135-174`; `src/trajcert/inference/confidence.py:100-101,171-211`; `src/trajcert/math/solver.py:221-230`; `src/trajcert/inference/certification.py:67`.

**Current content:** The article states that the method reports `Uhat_n >= V_n`, and describes outward Arb conversion and allowances for aggregate arithmetic. The supplement states that singleton envelopes use the population solver with its declared root precision. `_singleton_projection` passes the population midpoint endpoint through as `proven_upper`, records `final_gap=0`, and calls the termination `EXACT_SINGLETON`. `_Box.objective_upper` is `min(1.0, harmful_upper + hidden_upper)` with ordinary binary64 addition.

**Issue:** Root-location accuracy is not an upper enclosure. In addition, outward entropy conversion does not automatically enclose mass aggregation, geometry tests, objective sums or likelihood-ratio evaluations made before Arb is called. The theorem explicitly conditions on conservative computation and remains valid. The assertion that the current wrapper fulfills that condition on every path is not established, and the singleton path has a deterministic counterexample. This is a numerical contract issue, not a refutation of the population identification theorem.

**Evidence:** A read-only diagnostic used an exactly representable one-band law `A=0.125`, `G=0.625`, `c=0.25`, binary64 `rho=0.002`, production tolerances `root_atol=1e-12`, `identity_atol=1e-10`, and a singleton summary envelope. `project_upper_risk` returns `0.18098316846643075`. Independent 80-digit evaluation of `h(A+u)-(A+G)h(A/(A+G))-c h(u/c)=rho`, treating the input float rho exactly, gives upper risk `0.18098316846649106928032017689993736`. The reported value is lower by approximately `6.03143e-14`. Separately, exact rational comparison of binary64 operands `0.01` and `0.1` shows their rounded sum `0.11` is below their exact sum by `5.20417e-18`. These are component/path checks, not new scientific experiments. Production categorical inversions retain outer *computed* brackets, but their `betaln`/log signs are not interval-verified. The information allowance `32(K+1) ulp(1)` addresses specified information arithmetic, not a proved bound on every mass and root operation.

**Impact:** A computational-statistics reviewer can correctly challenge an unconditional implementation-level verified-bound claim. The smallest saved certified power margin is `1.3318858682609402e-8`; that is useful context but cannot, by itself, prove that no pruning/inversion error affected any result. No below-truth published certificate was established. Ordinary finite-sample power envelopes are non-singleton, so the explicit singleton counterexample is not evidence that their reported outcomes change.

**Recommended action:** Preserve Theorem 4 as conditional. Before submission, either (i) independently verify the complete arithmetic path, with directed mass/objective bounds, certified inversion signs or a proved error allowance, and an outer singleton root; or (ii) narrow the implementation description to an enclosure algorithm in exact arithmetic with partially verified numerical components, explicitly distinguishing approximate singleton diagnostics and the unproved wrapper contract. The second route requires honest scope edits, not a change to scientific results. Do not claim that a small global information slack repairs unrelated operations. Any code repair or new boundary tests require a later authorized task; none were made here.

**Proposed wording:** Replace the unconditional implementation sentence at `sequential.tex:53` with: “The numerical search is designed to return an upper enclosure of this relaxation. The statistical guarantee below requires that enclosure property; Arb verifies entropy evaluations, while the complete floating-point wrapper is not formally verified.” Add at Supplement section 4: “Singleton diagnostics use approximate population roots and must not be interpreted as verified upper enclosures. The current mass aggregation, geometric comparisons, objective addition and mixture inversion also involve ordinary floating-point operations. The saved numerical checks support the implementation but do not establish end-to-end outward enclosure for every input.” If later verification resolves these limitations, replace this disclosure with the proved bounds and precise verified scope.

**Verification criterion:** No approximate midpoint is described as a certified upper enclosure; all implementation-level claims either have a complete rounding argument or are explicitly conditional. A later numerical repair must cover the exact law above, zero-cell boundaries, mass/simplex arithmetic and threshold-adjacent inversion, with outputs checked against exact/interval references rather than `pytest.approx` alone.

**Confidence:** Verified for the singleton under-enclosure and downward objective rounding; strongly supported for the broader verification gap. The effect on ordinary reported certificates remains unproved, not presumed adverse.

### TC-NUMERICAL-NONRESOLUTION

**Finding ID:** TC-NUMERICAL-NONRESOLUTION  
**Severity:** Major  
**Priority:** Required  
**Location:** `paper/sections/results.tex:22,39`; `paper/sections/discussion.tex:6`; `paper/supplementary/supplement.tex:104-117`; `src/trajcert/experiments/power.py:295-334`.

**Current content:** “The larger categorical region and aggregate relaxation therefore impose a measurable cost when no compensating information increment is present.” The headline comparison also says intermediate resolution certifies earlier despite a smaller eight-band population bound.

**Issue:** The observed noncertification frequency combines statistical uncertainty, the envelope relaxation and numerical stopping. Saved reasons show stalled searches at several decisive checkpoints. A stalled retained upper bound above beta, with no incumbent above beta, does not determine whether exact confidence projection permits certification. Thus the current explanation assigns a specific cause beyond what the counts alone establish. The main success counts are correct and should remain.

**Evidence:** All 320 batches were independently read. Four fixed streams per cell use full searches (`full_precision=true`); the other 96 use decision-targeted searches. Their different termination semantics must not be pooled as if `STALLED` always meant uncertified. In the matched two-band control at `n=50000`, the 96 targeted streams contain 27 current certificates, one `DECISION_REFUTED`, 67 `STALLED`, and one stopped path. In the matched eight-band control, 94 targeted streams with updates are refuted and two are stopped; four additional full-search streams are not part of that 94. In strong timing at `K=1,n=5000`, targeted counts are 0 certified, 89 refuted and seven stalled; `K=2` certifies all 100 streams overall. Section 7 gives a complete-denominator table. Refutation relies on the feasible-incumbent verification contract; TC-ROUNDING-SCOPE prevents elevating code labels alone into a formal end-to-end proof.

**Impact:** The difference matters to the interpretation of resolution cost and first-certification times. It strengthens the early timing comparison while revealing that some later delays reflect the optimizer. It does not change the statistical theorem or invalidate a conservatively withheld certificate.

**Recommended action:** Add an existing-data Supplement table with current scientific states, numerical termination reasons, stopped paths, search mode and runtime by checkpoint. Keep “ever certified” separate from “currently certified.” Define numerical non-resolution without claiming exact projection would have certified. Revise the attribution sentences; do not rerun or replace the official outputs.

**Proposed wording:** Replace the sentence at `results.tex:39` with: “Finer resolution reduces certification frequency in this control through a combination of sampling uncertainty, envelope relaxation and incomplete numerical search. At 50,000 events, the two-band decision-targeted searches include 67 stalled noncertifications and one refutation among 96 streams, alongside 27 current certificates and one stopped path; the corresponding eight-band searches refute 94 streams and have two stopped paths (Supplement).” After the headline comparison at line 22 add: “At 5,000 events, endpoint searches refuted certification in 89 of the 96 decision-targeted streams and were numerically unresolved in seven, whereas the two-band procedure certified all 100 streams. At later checkpoints, numerical non-resolution also contributes to endpoint delay.” In discussion line 6, include “incomplete numerical search” among the potential finite-sample costs.

**Verification criterion:** A reader can distinguish current states, ever-certified outcomes, solver refutations, stalled searches and stopped paths, with every displayed decomposition summing to its stated denominator. The four full-search streams are identified and no stopped/full-search stream is silently called statistically refuted.

**Confidence:** Verified for code behavior, saved counts and omitted interpretation; exact real-arithmetic refutation remains conditional on numerical feasibility verification.

### TC-DECLARATIONS

**Finding ID:** TC-DECLARATIONS  
**Severity:** Major  
**Priority:** Required  
**Location:** `paper/main.tex:16-17`; PDF p.1 and metadata; `paper/sections/declarations.tex:5-11`; Supplement title page.

**Current content:** `[AUTHOR NAMES REQUIRED]`, `[AFFILIATIONS AND CORRESPONDING AUTHOR REQUIRED]`, pending conflicts/funding/CRediT statements, and an explicit unfinished human-review action in the AI declaration.

**Issue:** These author-specific facts and approvals are not supplied. The AI disclosure already names Codex and the substantive assistance accurately; it must be preserved and approved, not replaced by a guessed assertion that human review has occurred.

**Evidence:** Source and rendered title/declaration pages. The official [Elsevier generative-AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals) is the appropriate policy to check at submission; exact venue-specific forms remain unverified here.

**Impact:** Administrative return without review is a realistic risk. Scientific correctness cannot fill missing authorship, funding or accountability statements.

**Recommended action:** Human authors supply identities, affiliations, correspondence details, interests, funding, contributions and final responsibility/AI-disclosure approval. Synchronize the main article, Supplement, PDF metadata and portal. Retain factual AI assistance including auditing and mathematical checking; do not infer no funding or no conflicts.

**Proposed wording:** Author-completed disclosure skeleton only: “During preparation of this work, the authors used [tool and version if required] for [actual tasks]. The authors subsequently reviewed and edited the content and take responsibility for the publication.” Use that final sentence only after the authors have actually completed the review. Existing specific task descriptions may be retained verbatim.

**Verification criterion:** No unresolved author placeholder remains in the final sources/PDFs/metadata; each declaration is factually approved by the authors and satisfies the chosen journal's current forms.

**Confidence:** Verified.

### TC-THEOREM-STATEMENTS

**Finding ID:** TC-THEOREM-STATEMENTS  
**Severity:** Minor  
**Priority:** Required  
**Location:** `paper/sections/identification.tex:19`; Theorem 1, PDF p.4; compare `paper/supplementary/supplement.tex:40`.

**Current content:** “If c=0, the compatible set is {A}.”

**Issue:** Read as an unconditional boundary statement, this conflicts with the immediately preceding empty-below-floor assertion. Fully observed timing can still require positive information. This is a local qualification, not a failure of the proof or algorithm.

**Evidence:** Set `K=2`, `a=(1/2,0)`, `b=(0,1/2)`, `c=0`. Then `A=G=1/2`, `T=0`, and `tau=log(2)`. At `rho=0`, the only completion fails the information restriction, so the set is empty. The Supplement already gives its information as tau; the implementation assesses compatibility before the zero-unresolved branch.

**Impact:** Avoids a contradictory theorem boundary clause that is easy for a referee to identify.

**Recommended action:** Add the compatibility qualification. The other boundary cases and constructive sharpness proof need no weakening.

**Proposed wording:** “If c=0, the identified set is {A} for rho at least tau_Pi, and is empty otherwise.” Optionally make “positive-mass fine bands” explicit at line 46; the model already says empty-band proportions need not be defined.

**Verification criterion:** Theorem 1 and Supplement section 1 give the same set for the explicit two-band fully resolved example, and no conditional harmful proportion is assigned to a zero-mass band.

**Confidence:** Verified.

## 4. Strongly recommended improvements

### TC-ORACLE-DEGENERACY

**Finding ID:** TC-ORACLE-DEGENERACY  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `src/trajcert/math/oracle.py:300-345` (`_solve_information_oracle_data`), `oracle.py:773-802` (`_golden_minimum`); supporting scope at `paper/sections/results.tex:3`.

**Current content:** When rho is within the configured equality tolerance of the minimized information, the oracle returns `MINIMUM_INFORMATION_SINGLETON` at the numerical minimizer. It does so without first excluding the flat-profile case r=0.

**Issue:** For A=G=0 and c=1, the profile is identically zero. At rho=0 the whole interval [0,1] is identified, not a singleton. The production solver handles this correctly; the independent validation oracle does not. The manuscript's statement that all 280 tested state comparisons agree is not contradicted: those tests use configured generating laws with resolved mass, not every possible observable law.

**Evidence:** A deterministic read-only diagnostic used a one-band summary with harmful=(0), beneficial=(0), c=1 and `solve_information_oracle(summary,0,100,1e-14,1e-12)`. The oracle returned a singleton near `4.827994059928292e-99` with regime `MINIMUM_INFORMATION_SINGLETON`; `sharp_risk_set(summary,0,1e-12,1e-10)` returned [0,1] with `NO_RESOLVED_MASS`. Analytically J is constant, so I(L;J)=0 for every harmful proportion. Existing unit tests pass despite this missing oracle boundary assertion.

**Impact:** Limits the validator's domain and the interpretation of oracle agreement as universal boundary verification. It does not show a production-certificate defect or require replacing the stored 280 comparisons.

**Recommended action:** In a separately authorized numerical-maintenance task, handle zero resolved mass before the oracle's equality-to-minimum singleton branch and add a focused test of the returned full interval at rho=0 (and positive rho). Until then, avoid claiming oracle verification of every degenerate observable law. No code or result was changed during this audit.

**Proposed wording:** No main-paper result replacement is needed. If oracle boundary coverage is described, use: “The independent oracle comparisons cover the configured generating laws; fully unresolved boundary cases are established analytically and checked in the production solver, rather than validated by that oracle.”

**Verification criterion:** The oracle returns [0,1] at A=G=0,c=1 for every nonnegative rho, with a non-singleton/no-resolved regime; production behavior is preserved, and the validator's stated test domain is accurate.

**Confidence:** Verified deterministic counterexample; no effect on current published comparison rows was established.

### TC-PRIOR-ART

**Finding ID:** TC-PRIOR-ART  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/introduction.tex:14,22`; `paper/sections/sequential.tex:10-24,55`; `paper/references.bib`.

**Current content:** Related work cites Imbens-Manski for the parameter/set distinction and general confidence-sequence references, and correctly says martingale inversion is established. It does not mention Vansteelandt et al.'s strong uncertainty regions, Dalal et al.'s sequential partial identification, Lindon-Malek's joint multinomial region, or the Arb reference.

**Issue:** These are unusually close precedents for specific parts of the framework. Adding their contrasts materially improves positioning. A bibliography of 17 entries is not itself a defect; no reference quota is appropriate.

**Evidence:** Vansteelandt et al. (2006), Definition 3, covers the whole ignorance region at fixed time (no DOI located; full text verified). Dalal et al. (2024), section 4 and Assumptions 4.1-4.3, constructs asymptotic inference for sensitivity bounds on causal effects ([preprint DOI](https://doi.org/10.48550/arXiv.2408.09598); full methods verified). Lindon-Malek (2022), Theorems 2.2 and 2.4, gives joint multinomial time-uniform regions ([proceedings DOI](https://doi.org/10.52202/068431-0204); full methods verified). Johansson (2017) is the numerical-library foundation ([DOI](https://doi.org/10.1109/TC.2017.2690633); author full text verified). Sections 8-9 identify the exact files and placement.

**Impact:** Reviewers can assess what is specialized, what is integrated and what is inherited. A joint multinomial CS is an existing alternative to the coordinate union bound, not an unsolved construction or a demonstrated universally more powerful replacement.

**Recommended action:** Add these targeted comparisons, cite the existing Howard/Ramdas references next to mixture inversion and the maximal inequality, and retain the present modest contribution language. Treat Podkopaev-Ramdas and the recent categorical work as useful additions if space permits. No competitor experiment is indispensable for the current claims.

**Proposed wording:** After the Imbens-Manski sentence: “Fixed-time uncertainty regions in missing-data sensitivity analysis also distinguish coverage of a parameter from coverage of an entire ignorance region [Vansteelandt et al., 2006]. Sequential partial-identification inference has been developed asymptotically for causal sensitivity bounds [Dalal et al., 2024]; our result instead uses a finite-sample categorical region for the present information-budget model.” At sequential line 24: “Joint multinomial confidence sequences are another available input [Lindon and Malek, 2022]; the coordinate construction is used here for its simple aggregate envelopes.” Cite Johansson with the Arb description.

**Verification criterion:** Each added reference has a precise comparison, correct publication/preprint status and verified DOI or explicit no-DOI exception; no broad “first sequential partial identification” or “new chain rule” claim appears.

**Confidence:** Strongly supported; this is a positioning improvement, not a verified priority infringement.

### TC-BUDGET-DIRECTION

**Finding ID:** TC-BUDGET-DIRECTION  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/identification.tex:56-63`; `paper/sections/discussion.tex:2`; final abstract sentence, `paper/main.tex:19`.

**Current content:** “At equal excess budgets rho-tau_Pi, common endpoint masses yield identical risk intervals; the information advantage is the one implied by a common absolute finest-path budget.”

**Issue:** This already resolves the mathematical convention. The remaining practical question is why the application should constrain total path dependence rather than terminal-selection dependence. Stronger observed resolved-timing dependence consumes the common allowance and hence narrows terminal completions; this is a consequence of the assumption, not evidence that unresolved outcomes resemble resolved outcomes. The text is accurate but could answer that practical objection more directly.

**Evidence:** Independent subtraction gives `S_Pi(u)=tau_Pi+I(L;R)`. At strong timing, `tau_8=0.0505564` consumes about 63% of `rho=0.08`. No callback/extrapolation model implies a universal opposite direction; different substantive restrictions answer different questions. The manuscript already disclaims empirical validation of rho at `model.tex:24`.

**Impact:** A short explanation makes the contribution more defensible without recasting a disclosed convention as a flaw.

**Recommended action:** Add one interpretive paragraph after equation (13). Keep the equal-excess-budget statement. A short budget qualifier in the abstract is helpful, but multiple repeated disclaimers are unnecessary.

**Proposed wording:** “Under a declared total-information budget, visible dependence in resolved timing leaves less allowance for dependence through nonresolution. The resulting tightening is conditional on that total-budget assumption; it does not show that terminal selection is weak. An application that instead fixes an allowance specifically for terminal selection answers a different sensitivity question: at equal rho-tau_Pi and common endpoint margins, the population intervals coincide.” Optional abstract ending: “Under a fixed total-information budget, retaining verification paths can change population decisions and shorten certification horizons in the designed synthetic examples.”

**Verification criterion:** An analyst can identify the quantity they must elicit and explain why timing tightens the bound under that choice. No claim says observed timing identifies the true terminal mechanism.

**Confidence:** Verified identity; reviewer need is judgment.

### TC-RHO-CALIBRATION

**Finding ID:** TC-RHO-CALIBRATION  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/model.tex:24`; `paper/sections/results.tex:15,20`; Table 2.

**Current content:** “Reported budgets are sensitivity choices, not empirically validated operating values.”

**Issue:** Correctly disclosed nonidentifiability does not make nats easy to interpret. An observable-law-conditional translation into allowed unresolved harm would help readers judge these particular budgets without pretending to estimate rho.

**Evidence:** Independent population calculations give, at the ordinary law's rho=0.05, resolved harm `A/r=0.0373333`, worst-case unresolved harm `(theta_U-A)/c=0.4933621` at K=1 and `0.3238503` at K=8. Corresponding unresolved/resolved harmful odds ratios are 25.1100 and 12.3504. At strong timing/rho=0.08, unresolved harm is 0.3248351 versus 0.1643364 (odds ratios 26.9427 versus 11.0126). These are endpoint properties of assumed sets, not estimated selection parameters.

**Impact:** Shows concretely how permissive the chosen budgets are on these laws. It supports interpretation but does not establish scientific plausibility or transportability of the assumed budget.

**Recommended action:** Add a compact calibration paragraph or Supplement table based on existing endpoints. Explain external-adjudication or domain elicitation as a possible source of a budget range, with uncertainty. Do not propose estimating the unobserved information from the incomplete stream.

**Proposed wording:** “For interpretation, the upper endpoint implies an allowed unresolved harmful proportion `(theta_U-A)/c` when c>0. In Table 2 this is 0.493 at the endpoint and 0.324 with eight bands, compared with resolved harm 0.0373. These correspond to odds ratios of about 25 and 12. They describe completions admitted by the chosen budget, rather than estimates of the missing-outcome mechanism.”

**Verification criterion:** Reported translations reproduce from the stated A,c and endpoints; no worst-case completion is presented as the truth or a universal conversion from rho to an odds ratio.

**Confidence:** Verified.

### TC-RUNTIME-REPORTING

**Finding ID:** TC-RUNTIME-REPORTING  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/results.tex:54`; Figure 3; `src/trajcert/experiments/power.py:501-527`.

**Current content:** “The broader 500-event outer-projection target takes median 1.027-7.546 seconds…”

**Issue:** That benchmark and its units are accurate and properly scoped. It does not communicate the cost at the power study's operational decision boundaries, where projection is often stalled.

**Evidence:** Across 160 checkpoint-level saved medians, their median is 921.902 ms and their maximum is 31,003.659 ms; 27 exceed 3 seconds and eleven exceed 10 seconds. The 31-second value is the endpoint-uncertifiable two-band cell at n=20,000. Matched two-band n=50,000 is 28.587 seconds. `_summarize_checkpoint` excludes the four full-search representatives from runtime medians. These values time summary-envelope/projection/state computation, not the complete cost of processing a stream or an average over individual checkpoints pooled together.

**Impact:** A runtime statement from the actual power study would help readers evaluate repeated monitoring and the meaning of “earlier.” Hardware remains insufficiently recorded for portable performance claims.

**Recommended action:** Add a saved-runtime column to the decomposition table and one main-text sentence. Keep Figure 3's separate benchmark; do not combine its timed region with the power timings.

**Proposed wording:** “Among the 160 power-study checkpoint medians, the median was 0.922 s and the maximum 31.004 s; eleven checkpoint medians exceeded 10 s. These timings exclude the four full-search representative streams and measure projection-related checkpoint computation, rather than complete stream processing. Hardware was not recorded sufficiently for a portable speed claim.”

**Verification criterion:** The aggregation and excluded search modes are stated; units match saved `median_runtime_ms`; no median-of-medians is called an overall per-call median.

**Confidence:** Verified.

### TC-INCOMPATIBILITY-DETECTION

**Finding ID:** TC-INCOMPATIBILITY-DETECTION  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/results.tex:51`; `paper/sections/sequential.tex:73`; Supplement section 5.

**Current content:** “A finite-sample compatible envelope cannot authenticate the budget.” The article already reports 16/100 certificates in the incompatible four-band scenario and correctly distinguishes them from false risk certification.

**Issue:** The observed detection performance is useful additional context: the incompatibility state was never issued in the confirmatory power study. This is an unreported empirical fact, not a missing warning that invalidates the theorem.

**Evidence:** Every saved checkpoint state's `model_incompatible` count is zero, including the two incompatible scenarios where rho=0.02 while tau_4=0.0237104 and tau_8=0.0251064. The broad entropy envelope weakens the lower bound used for rejection. These records do not isolate the causal contribution of each source of looseness, nor do they establish that no sample size could detect incompatibility. Pilot README summaries are not confirmatory outcomes.

**Impact:** Prevents readers from treating the finite-sample compatibility check as an effective empirical validation of rho in the demonstrated regimes.

**Recommended action:** Add the zero detection count beside the existing 16/100 statement and include the incompatibility column in the Supplement decomposition.

**Proposed wording:** “No model-incompatible state was issued at any reported checkpoint in either incompatible-budget cell, or elsewhere in the power study. Thus the rejection safeguard did not detect these false budgets at the tested horizons.”

**Verification criterion:** The count matches every checkpoint record and is not described as a failure of coverage under a true structural assumption.

**Confidence:** Verified.

### TC-PILOT-DISCLOSURE

**Finding ID:** TC-PILOT-DISCLOSURE  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/experiments.tex:26`; `paper/sections/results.tex:17`; `paper/supplementary/supplement.tex:136`.

**Current content:** “The strong-timing law was selected by a population-feasibility search…” and “Exploratory indices were below 1,000,000…”

**Issue:** The design account is candid but incomplete about the exploratory stream pilots that also influenced horizons, grids and comparator inclusion. The source README explicitly records those choices. Reporting that process strengthens the confirmatory/designed-example distinction; it does not establish misconduct or invalidate the independent confirmatory streams.

**Evidence:** `docs/audit/exploratory_pilots/README.md` records ten-stream pilots (twenty for the optional-stopping grid), disjoint seed indices, the 50,000-event cap for strong timing, dropping matched-control comparators for cost and choosing the endpoint-uncertifiable checkpoints. `pilot_p2.txt` records no TrajCert certification through 200,000 events in ten exploratory streams for the ordinary population-decision example. The confirmatory paper correctly reports 0/100 through 20,000 for that example. The pilot is a different sample, not an extension of those 100 streams.

**Impact:** Makes the favorable scenario's origin and the limits of the population example easier to assess.

**Recommended action:** Add a concise pilot-design paragraph and archive the referenced pilot summary. Do not merge pilot and confirmatory counts or demand reruns. The 200,000-event observation should be identified as exploratory and algorithm-dependent, not proof of a practically impossible horizon.

**Proposed wording:** “Disjoint exploratory stream pilots were also used to choose horizons and checkpoint grids and to omit matched-control comparators for computational cost. These choices were fixed before the confirmatory streams. In a separate ten-stream pilot of the ordinary population-decision example, TrajCert did not certify by 200,000 events; that exploratory observation is not part of the 100-stream confirmatory estimates.”

**Verification criterion:** The design account names the actual tuning decisions and separate denominators; the pilot summary and raw record are available through the stated archive or an explicit access limitation.

**Confidence:** Verified for existing files and design statements; temporal freezing is locally documented rather than externally attested.

### TC-ARCHIVE-EQUIVALENCE

**Finding ID:** TC-ARCHIVE-EQUIVALENCE  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/declarations.tex:3`; `paper/supplementary/supplement.tex:124,128,136,138`; `paper/supplementary/evidence.zip`.

**Current content:** “No permanent archive DOI or release tag is asserted.” The Supplement explicitly discloses missing per-run source digests and campaign-reported equivalence on eleven selected cases.

**Issue:** These limitations are correctly acknowledged. The remaining improvement is to make the exact evidence portable: the existing archive does not contain the frozen configuration/pilot materials, and the public scientific commit does not track those local documentation files. A current source commit cannot retroactively attest the bytes used by every power run. An archive helps preservation but cannot manufacture historical attestation.

**Evidence:** Config and local frozen copy are byte-identical, with SHA-256 `865eeb27e1bdbead6198ecfc1f45349a483fe44e4ea6a06e71012ca0e35058b7`; `git ls-files docs/audit/exploratory_pilots` is empty. Evidence archive contains 523 payloads plus `MANIFEST.json`. The public API resolves commit `6a37400...`. `docs/audit/campaign_run/verification/equivalence.json` supplies 44 targeted/full cases with four budgets each, all agreeing (176 comparisons); it is not the separate eleven-case source-speed equivalence record. The latter remains a campaign assertion, not independently reconstructed per-cell evidence here.

**Impact:** Separates verified artifact integrity, repeatable recorded calculations and incompletely attested scientific reruns. The paper does not currently falsely assert complete source equivalence.

**Recommended action:** Authors should deposit a versioned source/evidence/design archive containing the cited commit, locks, frozen config and pilot summary, with checksums and a real persistent identifier if available. Preserve the scope limitation. If broader output equivalence is essential to a later claim, obtain the exact pre-optimization sources/manifest or conduct a separately authorized targeted rerun; do not prescribe an arbitrary expensive campaign merely for appearance.

**Proposed wording:** “The archived frozen-design copy and exploratory-selection record are provided with their checksums. Their agreement with the reported configuration is verified; their creation time and the exact source bytes used by every historical run are not independently attested.” Add a release/DOI citation only after it exists. Retain the distinction between the eleven-case speed assertion and the 176 targeted/full comparisons.

**Verification criterion:** An external reader can retrieve the named design, code and evidence files, verify checksums and identify what is and is not historically attested. No unresolved placeholder DOI is introduced.

**Confidence:** Verified for current local/public availability and hash relationships; Requires further verification for historical pre-run source identity.

### TC-FULL-LAW-STABILITY

**Finding ID:** TC-FULL-LAW-STABILITY  
**Severity:** Minor  
**Priority:** Strongly recommended  
**Location:** `paper/sections/sequential.tex:3-8,60`; `paper/sections/model.tex:8,14`.

**Current content:** The stream assumption fixes categorical conditional probabilities p_j; Theorem 4 additionally refers to “the true full law” and the model defines a single theta.

**Issue:** A fixed latent target is already implicit in those full-law definitions. It would be clearer to state it at the point where stable observable data are introduced. Observable stability alone does not identify a unique unresolved harmful share under unrestricted latent drift. This is a scope clarification, not a demonstrated missing hypothesis that invalidates the theorem as written.

**Evidence:** Changing only the harmful split of the unresolved category leaves all observable p_j unchanged. The projection proof contains every budget-compatible completion, but the fixed theta being certified must still be specified. Shared marginal full law plus the stated conditional observable stability is sufficient; one need not impose an unnecessary conditional independence assumption on every latent label.

**Impact:** Prevents operational extrapolation to a changing underlying risk solely because the observable frequencies look stable.

**Recommended action:** Make the fixed-law target explicit without claiming unrestricted drift coverage or strengthening the assumptions beyond the proof's needs.

**Proposed wording:** “The target theta and terminal harmful mass u refer to one fixed full law of matured events. Equation (16) is the additional conditional stability condition on its observed categories used by the confidence-sequence proof.”

**Verification criterion:** The operational scope distinguishes a fixed latent risk, observable conditional stability and unmodeled policy/label drift; the theorem remains valid under its actual assumptions.

**Confidence:** Strongly supported as clarification.

### TC-LONG-HORIZON-VALIDITY

**Finding ID:** TC-LONG-HORIZON-VALIDITY  
**Severity:** Moderate  
**Priority:** Strongly recommended  
**Location:** `paper/sections/results.tex:44,51`; Table 4; `paper/sections/experiments.tex:33`.

**Current content:** “Confidence-sequence exclusions of the true law range from one to six of 100 by cell, illustrating why validity is probabilistic.”

**Issue:** This statement is correct. Longer-horizon records allow a more useful synthesis than the short 500-event diagnostic alone. The repeated-static reference also has zero recorded violations in the short study, so that study does not empirically discriminate safe continuous monitoring from the approximate repeated-static construction.

**Evidence:** Deduplicating shared law/partition streams, retaining the longest available horizon for each, gives 21 sets and 58 exclusions among 2,100 indexed stream outcomes (2.76%). Maximum count is 6/100. Horizons are 20,000-50,000; the shorter optional-stopping duplicate is not counted again. Parts of different sets share event streams; this is not a binomial experiment with 2,100 independent trials. Empty paths stop, so the records describe exclusions observed by stopping/horizon rather than unobserved post-stop behavior.

**Impact:** Adds evidence on the categorical input at relevant horizons while preserving the distinction between construction coverage, risk-bound containment and false certification. It neither proves the theorem nor validates numerical enclosure.

**Recommended action:** Report the deduplicated descriptive summary with its dependence/stopping limits; retain the seven individual Table 4 intervals. Do not add a pooled exact binomial confidence interval or a campaign-wide 95% claim.

**Proposed wording:** “Using the longest recorded horizon for each of 21 distinct law-partition stream sets, categorical exclusion was recorded in 58 of 2,100 indexed outcomes (2.8%; at most six of 100 per set). This is a descriptive summary: partitions share streams and empty paths stop. The 500-event study is a shorter implementation diagnostic; its repeated-static reference also recorded no violation.”

**Verification criterion:** Sets are deduplicated by law and partition with the longest horizon, stopped paths remain accounted for, and no independence or multiplicity guarantee is attached to the pooled rate.

**Confidence:** Verified.

### TC-WRITING-REGISTER

**Finding ID:** TC-WRITING-REGISTER  
**Severity:** Minor  
**Priority:** Strongly recommended  
**Location:** `paper/sections/results.tex:3,5,44,61`; `paper/sections/experiments.tex:40`; section 10 below.

**Current content:** “The current population-solver table…”; “Stored tests…”; “Inspection of the batch counts shows…”; “A stored expected-count diagnostic…”

**Issue:** These phrases describe the preparation workflow more than the scientific result. This is a local readability concern. Formal grammar, necessary caveats and standard terminology are not evidence of AI authorship or plagiarism. Blanket deletion of “stored,” “current,” “not,” or all technical provenance would remove useful meaning.

**Evidence:** The specific source passages and replacement table in section 10. In particular, “Stored tests” refers to mathematical identity evaluations as well as unit tests; relabeling all of them “unit tests” would change the evidence type.

**Impact:** Clearer prose makes the claims easier to follow while retaining auditability and uncertainty.

**Recommended action:** Apply only the localized edits listed in section 10; keep full provenance in the Supplement and necessary scope statements at their point of use.

**Proposed wording:** “The population-solver validation comprises 280 cases…” and “Recorded checks of the profile decomposition, curvature, compatibility floor and constructive completions support consistency of the implementation with the analytical identities.” Other exact replacements appear in section 10.

**Verification criterion:** Replacements preserve every number, evidence type, limitation and disclosure; no unsupported “verified” or completed-human-review claim is introduced.

**Confidence:** Verified locations; style assessment is judgment.


## 5. Optional refinements

### TC-REAL-DATA

**Finding ID:** TC-REAL-DATA  
**Severity:** Moderate  
**Priority:** Optional  
**Location:** `paper/sections/experiments.tex:3`; `paper/sections/discussion.tex:8`; `docs/audit/HITL-IoT Provenance Audit.md`.

**Current content:** “All primary evidence is synthetic…”; “The experiments demonstrate the mechanism on designed synthetic laws.”

**Issue:** This is an acknowledged scope boundary, not an unresolved validity defect. An application could make budget elicitation and maturation more tangible for an applied readership.

**Evidence:** Current claims concern mathematical properties and performance on specified laws. The existing HITL-IoT audit records uncertain annotation provenance and selected reviewed cases; the manuscript appropriately excludes it as primary evidence. This audit did not independently re-audit the external raw dataset and does not assert that its labels are valid.

**Impact:** Potential reader uptake and venue fit only. A real-world study becomes necessary only if the authors add deployment/generalization claims that require it.

**Recommended action:** Consider a future illustrative workflow with a documented outcome-adjudication protocol, target population, fixed terminal horizon and explicit budget range. Keep it optional for this theory-led submission. Do not reclassify the existing diagnostic replay as external validation.

**Proposed wording:** If no application is added, retain the current scope statement. An optional closing sentence is: “A practical application additionally requires a justified information-budget range and a stable, documented adjudication process.”

**Verification criterion:** Any application has traceable labels and a supported target; otherwise the abstract/conclusion retain the present designed-law scope.

**Confidence:** Strongly supported reviewer judgment.

### TC-REJECTION-COROLLARY

**Finding ID:** TC-REJECTION-COROLLARY  
**Severity:** Minor  
**Priority:** Optional  
**Location:** `paper/sections/sequential.tex:73`, decision states; Theorem 4 and Supplement section 4.

**Current content:** “Numerical comparison guards make the first two rejections conservative.”

**Issue:** The same containment event gives a useful probabilistic interpretation, assuming the claimed lower bounds are actually conservative. The text already describes the states correctly; a separate theorem is not necessary for validity.

**Evidence:** On the simultaneous categorical-containment event, the true summary is plausible. Under the information restriction it is compatible; therefore a lower bound on all plausible floors cannot exceed the true floor. Similarly, with r>0, a conservative minimum-risk lower bound cannot exceed the true A/r. If zero resolved mass is plausible, the implementation withholds the intrinsic state. Numerical scope is governed by TC-ROUNDING-SCOPE.

**Impact:** Makes operational interpretation easier without adding a new inference construction.

**Recommended action:** If desired, add a one-sentence corollary with explicit fixed-law, sensitivity and conservative-computation hypotheses. Do not imply that an intrinsic state proves the actual latent theta exceeds beta.

**Proposed wording:** “On the same simultaneous-containment event, conservative state bounds cannot reject the true sensitivity model, and cannot declare intrinsic uncertifiability when its minimum-information risk A/r is at most beta (r>0).” Proof: the true compatible summary is among the summaries over which the lower bounds are taken.

**Verification criterion:** The statement preserves the distinction between A/r and theta, specifies r>0, and inherits the theorem's numerical and sensitivity conditions.

**Confidence:** Verified conditional argument.

## 6. Mathematical and implementation verification

### 6.1 Independent reconstruction of all main results

| Result and location | Reconstruction / boundary challenge | Assessment |
|---|---|---|
| Observation table, model equations (1)-(4) | The resolved 2K masses and one unresolved mass leave exactly the split u in [0,c]; rows sum to A+u and 1-A-u | Correct for the stated observation model and correct resolved labels |
| Profile, Theorem 1 / equation (5) | Subtract column-conditional binary entropies from h(A+u); every completion is a joint table | Correct; constructive sharpness is partition-relative as disclosed |
| Minimum and compatibility floor, equation (6) | S'(u)=log[u(G+c-u)/((A+u)(c-u))]; its zero solves u=Ac/(A+G); substitution gives q(A,G)-T | Correct for r>0; no resolved-risk ratio is used at r=0 |
| Curvature, equations (8)-(9) | S''=1/u+1/(c-u)-1/(A+u)-1/(G+c-u)=A/[u(A+u)]+G/[(c-u)(G+c-u)] | Strictly positive on 0<u<c when r>0; endpoint minima handle A=0 or G=0 |
| Sublevel interval and attainment | Continuous strictly convex profile has compact interval sublevels; each u supplies its attaining table | Correct, subject to TC-THEOREM-STATEMENTS at c=0 |
| Chain-rule decomposition, equation (10) | R is a function of J; the unresolved R=0 branch has constant J; I(L;R) is minimized at zero by equal resolved/unresolved harm proportions | Correct established information identities specialized to this model |
| Refinement, Theorem 2 / equations (11)-(13) | A,G,c unchanged; only T changes. Strict concavity gives T_c-T_f>=0 with equality for homogeneous positive-mass fine proportions inside each coarse band | Correct; unresolved category must remain unsplit, as assumed |
| Strict upper-risk improvement | Fine compatibility plus Delta>0 implies rho>tau_c. The nonsaturated coarse upper endpoint is right of the common minimizer and has fine profile rho+Delta; compact nesting excludes it strictly | Correct sufficient condition; no general strictness claim when both upper endpoints saturate |
| Frontier, Proposition 3 / equations (14)-(15) | Every compatible set contains A/r. In A/r<=beta<A+c, beta-A is on the right branch; certification iff tau<=rho<=S(beta-A) | Correct, including equality beta=A/r and the frontier endpoint |
| Population computation paragraph | One O(K) entropy/mass reduction, then scalar evaluations and bisection | Correct for locating roots; approximation is not an outward bound |
| Maturation / equation (16) | Events enter once at common terminal age; stable conditional category probabilities imply Bernoulli conditional means for each coordinate | Correct. Informative selection/reordering or policy drift outside that assumption is not covered |
| Mixture and categorical CS, equations (17)-(19) | Integrating a Bernoulli likelihood ratio against Beta(1/2,1/2) preserves a nonnegative martingale by conditional Tonelli. Ville plus d-way allocation gives one event over all n | Correct in exact arithmetic; category independence is unnecessary |
| Probability-zero/one categories | At a true zero category the observed count is identically zero and the limiting mixture decreases from one; analogous at one | Correct supermartingale boundary argument |
| Running intersection and simplex | Both retain the true p on the same single containment event | Correct; no extra spending over monitoring times |
| Aggregate envelope, equations (21)-(22) | Simplex complements bound sums; partial q/partial a=log[(a+b)/a]>=0 and the analogous b derivative justify corner entropy bounds by continuity | Correct mathematical enclosure; unattainable upper corners make it loose, not invalid |
| Relaxation, equation (23) | The constraint decreases with T, so setting T=T_U enlarges the feasible set. Possibly unattainable A,G,T combinations are deliberately retained | Correct outer relaxation, not the exact categorical projection |
| Box lower bound, Supplement (S11)-(S13) | Bound h on the risk interval and terminal q on its rectangle, then subtract T_U. Truncating the result at zero cannot exclude an original feasible table for rho>=0 | Correct with enclosing inputs/arithmetic; not a proof for every wrapper operation |
| Theorem 4 / equation (24) | On the categorical event, true observable summary and budget-compatible u are feasible; data processing supplies the coarse budget; projection dominates theta | Correct under conservative computation and the fixed target model |
| Decision states | Evidence gate, guarded floor/intrinsic lower comparisons, then upper<=beta; zero-resolved plausibility withholds intrinsic rejection | Matches described ordering; numeric contracts remain conditional |

Additional challenges covered A=0, G=0, r=0, c=0, empty bands, rho=0, rho=tau, rho>=log(2), beta<A/r, beta=A/r, beta>=A+c, incompatible sets, empty running intervals and saturated/nonsaturated refinement endpoints. No further counterexample to the main mathematical results was established. The separate validation-oracle boundary defect is TC-ORACLE-DEGENERACY. Every main theorem/proposition and its Supplement proof was examined. The fully resolved example is a wording correction; the singleton numerical example is a separate implementation issue.

The sharpness lift to an unobserved finer representation may assign equal outcome proportions within each coarse band, preserving information. It need not respect already-known fine margins; the manuscript explicitly distinguishes those experiments. A common absolute rho on the finest prespecified path implies all coarse constraints; partition-specific rho choices change the assumptions. Finite-sample monotonicity across d=3,5,9,17 is not promised.

### 6.2 Implementation and numerical invariant

| Mathematical object | Source functions inspected | Verified behavior / limit |
|---|---|---|
| Entropy, profile, floor | `src/trajcert/math/entropy.py`; `information.py:resolved_timing_entropy,minimum_information_point,information_profile,timing_gain` | Formulas agree; tiny negative information is clipped under a configured roundoff rule |
| Compatibility/roots | `math/compatibility.py:assess_compatibility`; `math/solver.py:solve_hidden_mass_interval,_bisect`; `math/bounds.py:sharp_risk_set` | Compatibility precedes fully resolved handling; scalar branches and zero-resolved case present; midpoint roots are approximations |
| Independent oracle | `math/oracle.py:solve_information_oracle`, table-information helpers | Direct arbitrary-precision table information and separate search, rather than the production profile root solver; numerical agreement is not proof of sharpness |
| Event order/labels | `data/maturity.py:mature_event,mature_ledger`; `inference/categorical.py:append_matured_event` | Common H maturity, deterministic maturity/event-ID order, one category per event, identity/horizon checks |
| Seed pairing | `determinism.py:event_stream_namespace,derive_seed`; `data/synthetic.py:generate_stochastic_ledger`; `experiments/power.py:resolve_power_case` | Finest law/index seed PCG64; partition/rho/beta excluded from namespace; nested analyses share finest streams |
| Categorical region | `inference/confidence.py:raw_confidence_region,confidence_sequence_update,_lower_root,_upper_root` | log(d/delta), outer computed brackets, prefix intersections and simplex validation; signs use floating betaln/log |
| Aggregate envelope | `inference/envelope.py:summary_envelope_from_confidence,_subset_interval,_resolved_entropy_envelope` | Matches algebra; sums/entropy envelope use floats |
| Upper search | `inference/projection.py:_projection_step,_settled_search,_final_projection,_queue_upper` | Retains active/queued objective values at convergence, stall, box resolution, cap and arithmetic fallback; no substitution of a smaller incumbent |
| Incumbent | `projection.py:_summary_at_aggregates,_allocate_total,_verified_information_feasible` | Allocates category masses and checks an Arb information upper bound; other table operations still use floats |
| Rejections | `projection.py:_compatibility_search,_intrinsic_search,_zero_resolved_plausible`; `inference/certification.py:classify_certification` | Lower-search direction and zero-resolved safeguards explicit; state precedence matches text |
| Comparators | `comparators/repeated_static.py,ignorable_delay.py`; `experiments/power.py:_static_state,_ignorable_certified` | Wilson uses coordinate Bonferroni without time spending; resolved-label mixture assumes ignorability; assumptions disclosed |

Max-heap ordering, active-box retention, overlapping split faces and stopping branches support the intended real-arithmetic search invariant. The historical gap-pruning defect is repaired in the current source and is not an open finding. The invariant presupposes safe geometric exclusion and enclosing arithmetic. Arb at 128 bits and outward endpoint conversion are meaningful components, not a proof for floating operations outside Arb.

Existing tests cover caps, active-box fallback, nonconvergence, incumbent units, decision targets and feasible-oracle direction. Some directional assertions permit 1e-12 slack, and the singleton test checks type/range/status rather than exact upward inclusion. All tests can therefore pass while the 6e-14 singleton shortfall remains. Targeted boundary tests verifying the actual enclosure contract are justified; broad duplicate tests are unnecessary.

**Tests actually executed:** 136 math/inference unit tests passed in 5.56 s with bytecode, pytest cache, coverage and random-order plugin disabled. Configuration copies and pytest temporary files were outside the repository. An initial isolated invocation failed at setup because relative configuration files were absent; copying unchanged configs into scratch resolved that invocation issue. Those setup errors are not scientific failures. The 961-test historical log was treated as historical evidence only. No scientific stream, experiment, expensive campaign or manuscript build was rerun.

### 6.3 Independent population calculations

These values use a separate 70-digit reconstruction of the exponential-band law and scalar bisection, not the production endpoint solver. All displayed manuscript digits agree.

| Law and rho | K | tau | Sharp upper risk | Frontier at beta=.06 |
|---|---:|---:|---:|---:|
| Ordinary harmful-late, .05 | 1 | 0 | .065835130129 | .035490507897 |
| Same | 2 | .018323082312 | .058345717466 | .053813590209 |
| Same | 4 | .023710384982 | .055898912435 | .059200892879 |
| Same | 8 | .025106390433 | .055240646545 | .060596898330 |
| Strong timing, .08 | 1 | 0 | .079616689663 | — |
| Same | 2 | .033215669492 | .059128978701 | — |
| Same | 4 | .046983680407 | .049755149970 | — |
| Same | 8 | .050556375854 | .047195954366 | — |

Ordinary-law A=.035, G=.9025, c=.0625, A/r=.0373333333, A+c=.0975; frontier window approximately (.0354905,.0605969]. Low-prevalence upper risks at rho=.02 and K=1,2,4,8 are .017294121148, .015829851882, .015373961770 and .015252681530. TC-RHO-CALIBRATION uses the same calculations.

**Unresolved limits:** No formal proof assistant, complete floating-point verification, full scientific rerun, historical per-run source attestation, portable-hardware replication or external-dataset revalidation was performed. None is silently treated as passed.

## 7. Experimental evidence audit

### 7.1 Authority and claim-to-artifact trace

Production evidence is the completed current experiment records, checkpoints/completion markers, exported tables and report manifest. `docs/audit/archive/2026-10-19_pre_campaign` is historical; retired validity scenarios and old runtime-unit outputs were not substituted for final studies. Pilots are exploratory. The optional real-trajectory replay is diagnostic, with no current deployment claim.

| Manuscript claim / display | Definition and implementation | Configuration and stored source | Independent check |
|---|---|---|---|
| Profile, floor and refinement identities, results:3-5 | Theorems 1-2; `math/information.py,solver.py`; identity experiments | Current identity/coherence records in `outputs/experiments/`; config laws/partitions | Proofs reconstructed; supporting records/tests inspected; stored checks are not proofs |
| 280 oracle cases, upper error about 4.615e-13 | Production solve vs direct table oracle | `results/experiments/production-solver-vs-independent-oracle/tables/main/solver_oracle_validation.csv` and current records | 20 aggregate rows x14 cases; zero state mismatches; stored maximum 4.614086890342151e-13 |
| 360 profiles / 2,160 rows / 34 changed decisions; Table 2 | Law/rho/K/beta; `experiments/decision_value.py,math/safety.py` | `results/experiments/trajectory-decision-value/tables/main/trajectory_decision_value.csv`; 6 laws x15 rho x4 K x6 beta | Counts, 13/11/10 law split and max oracle error 4.0015907254442595e-13 checked; Table 2 independently recomputed |
| Figure 1(a) | S(u) grid | `outputs/experiments/safety-and-intrinsic-impossibility/evaluations/aggregates/figure_information_profile.parquet` | 1,001 points, law, shading and minimum consistent with formulas; panel (b) uses decision CSV |
| Strong timing/stricter beta/low prevalence/matched control; Figure 2, Table 3, abstract | `experiments/power.py`; ever certificate at scheduled looks | `configs/trajcert.yaml:sequential.certification_power`; `outputs/experiments/anytime-certification-power/evaluations/records/**/scientific_result.json` and matching `checkpoints/execution/**/batch_*_result.json` | 32 cells, 320 batches, original 100 indices and 160 checkpoint counts reconstructed; main and all 32 Supplement final rows agree |
| Figure 2 intervals | Two-sided Clopper-Pearson | `results/experiments/anytime-certification-power/tables/main/certification_power.csv,certification_power_summary.csv` | Every saved interval recomputed; CSV/Parquet numeric agreement checked |
| Table 4 | Ever empty-region/below-risk diagnostic; separate exclusions | `results/experiments/anytime-coverage-stress/tables/main/anytime_coverage.csv`, seven records/batches | Seven completion markers, 500 streams/case, counts 1,1,0,0,0,0,0 and one-sided limits checked; nonzero events are empty regions |
| Figure 3 | Population and broad 500-event outer targets | `results/experiments/computational-scaling/tables/main/computational_scaling.csv`; eight K records | Conversion checked; medians .4187135-.4656885 ms and 1.026963706-7.545919009 s; process RSS 210.824-214.648 MiB; 36 total root iterations |
| Independent feasible-risk check | Feasible oracle lower vs saved upper | `docs/audit/campaign_run/verification/soundness_new.json` | 40 records; 33 comparable, seven no feasible point; stored zero directional failures is finite evidence only |
| 176 targeted/full decisions | Paired solver decisions | `docs/audit/campaign_run/verification/equivalence.json` | 44 cases x4 budgets; all agree; separate from eleven-case speed-equivalence assertion |
| Expected-count .0540/.0404 at 5k/10k | Deterministic diagnostic | `results/experiments/failure-boundary-atlas/tables/main/failure_boundaries.csv`, certification-sample-size axis | Separately labeled expected-count evidence; not used as stochastic power |

The manuscript-side validator was read, copied to scratch, and its sole JSON output redirected there. Its hash/record/interval/CSV-Parquet checks passed. Separate independent archive hashes, stream/termination reconstruction and high-precision population reconstruction also passed. No publication output was regenerated.

### 7.2 Bookkeeping, statistics and comparators

- Each power cell retains original indices 1000000..1000099, ten batches and completion markers. No replaced seed, dropped noncertifying stream or current completed-cell technical failure was found. Empty paths stop updates but remain in the denominator; an earlier certificate remains ever-certified if the path later stops.
- All percentages/intervals match outcomes. For 100/100 the two-sided lower limit is .963783; for 96/100 the interval is about [.900742,.988996]. For 88/100 the lower limit is .799764, below the .8 target despite rounding to .800 at three decimals. The manuscript uses four decimals where needed.
- For 0/100 false certificates the one-sided upper limit is .029513; validity 1/500 gives .0094523 and 0/500 gives .0059736. These describe simulation frequencies, not theta intervals. The .06 acceptance threshold is explicitly distinguished from theoretical delta=.05, not offered as a new theorem level.
- Streams are independent within a fixed cell, shared across partitions and some scenarios. Marginal intervals are conditionwise. Neither 32 cell conjunctions nor 160 checkpoint rows are independent replications. Four fixed full-search representatives and 96 targeted streams should be documented; interpreting their decisions as one procedure relies on decision-preserving stopping. The 176 paired comparisons support, but do not prove all arithmetic executions of, that invariant.
- Endpoint TrajCert shares rho, beta, finest stream, maturity and CS construction: a fair information ablation under the common total budget. Dimension changes with K by design. The ignorable-delay reference uses stronger assumptions; assumption-violated certificates are not valid-comparator failures. Repeated-static Wilson intervals are approximate at fixed time and not time-uniform, as the paper says.
- One hundred streams give limited rare-error/near-boundary precision but adequately demonstrate the large designed-law contrast. At n=5000 the strong K=2/K=1 paired outcomes are 100 versus zero; a further significance test is unnecessary to demonstrate that observed difference. Equal-checkpoint paired summaries are preferable to implying independent marginal comparisons.
- All TrajCert cells record zero false-risk and zero compatible-population premature-certification counts under the stored definitions. The 16/100 incompatible-budget certificates are retained; true risk is below beta. They are certificates under a false assumption, not false-risk events by that counter. Zero false-risk counts do not validate rho.
- The ordinary population example's confirmatory 0/100 through 20,000 and distinct exploratory 0/10 through 200,000 are both meaningful. Neither disproves the frontier nor establishes an unreachable future horizon. No sample-complexity theorem follows from the strong-timing example.

### 7.3 Retained checkpoint decomposition

Each row below uses **96 decision-targeted streams**, excluding four fixed full-search representatives. C=current certificate, R=stored `DECISION_REFUTED`, U=stalled unresolved noncertification, S=stopped/no update. These selected rows have no other categories and sum to 96. R is conditional on the numerical feasibility contract, not proof actual theta exceeds beta. U does not prove further search would certify.

| Scenario | K | n | C | R | U | S |
|---|---:|---:|---:|---:|---:|---:|
| Strong timing, beta=.09 | 1 | 5,000 | 0 | 89 | 7 | 0 |
| Same | 1 | 10,000 | 2 | 67 | 27 | 0 |
| Same | 1 | 20,000 | 14 | 12 | 70 | 0 |
| Same | 1 | 50,000 | 92 | 0 | 4 | 0 |
| Same | 2 | 2,000 | 0 | 0 | 96 | 0 |
| Same | 2 | 5,000 | 96 | 0 | 0 | 0 |
| Same | 4 | 5,000 | 84 | 0 | 12 | 0 |
| Same | 8 | 5,000 | 0 | 0 | 95 | 1 |
| Same | 8 | 10,000 | 94 | 0 | 1 | 1 |
| Endpoint-uncertifiable, beta=.07 | 2 | 10,000 | 0 | 0 | 96 | 0 |
| Same | 2 | 20,000 | 8 | 0 | 88 | 0 |
| Matched no timing, beta=.09 | 1 | 50,000 | 91 | 0 | 3 | 2 |
| Same | 2 | 50,000 | 27 | 1 | 67 | 1 |
| Same | 4 | 50,000 | 0 | 65 | 28 | 3 |
| Same | 8 | 50,000 | 0 | 94 | 0 | 2 |

Main-paper counts remain **ever certified over all 100**. The matched 28/100 must not be replaced by 27/96. A full-search representative can be certified after `STALLED`, having continued search after the bound first crossed beta. Therefore counting every `STALLED` label as a failed certificate would be wrong.

### 7.4 Provenance and selection

Config/frozen-copy equality and seed separation are verified local facts. Pre-confirmatory creation is documented locally, not proved by filenames, current modification times or an independent preregistration. No contradictory evidence was found. Missing source-digest coverage and partial equivalence are already acknowledged; they are not retained as undisclosed correctness defects. Portable archiving and pilot description remain useful actions.

Config SHA-256: `865eeb27e1bdbead6198ecfc1f45349a483fe44e4ea6a06e71012ca0e35058b7`. `requirements.lock`: `2f94341d20401569cbbd305333d78becd88a046ca1b272c30b49997836fcf9db`. `uv.lock`: `b2228b28b9fa7e350f3bed22f06d128d41b884f76004153f610f441d4b6efd48`. Report commit `36e76519...`, inspected code `6a37400...` and current paper `e628f0a` serve distinct roles. Current hash equality does not attest historical execution bytes.

## 8. Literature and reference audit

### 8.1 Verification scope and access accounting

All **17 current entries** were checked against fresh Crossref registrations except the arXiv-only Lindon-Kallus entry, checked against DataCite and arXiv v2. Author order, title identity, issue year, outlet, volume/issue/pages where applicable and DOI agree with the bibliography. Early-online dates differ from issue years for Miao, Waudby-Smith and Cro; the issue-year citations are appropriate. All 17 keys are used; no uncited padding was found.

Eleven relevant additions are assessed below: **28 distinct works** total. Twenty-seven have verified DOI identities; Vansteelandt et al. has verified institutional/publisher identity but no DOI was located. Preprint and publisher DOIs are distinguished. This is a bounded inventory, not a claim that every search hit was read.

**L/** means `paper/literature/references_pdf/`; **R/** means `paper/references_pdf/`. Existing PDFs were preserved. There are **26 valid PDFs for 25 distinct works**: thirteen in each directory. Three were newly acquired: Johansson's author paper, Jung-Kang arXiv v2 and the distinct final PMLR version. Each opens in Poppler and matches title/authors/version. Existing files also open and their identities were inspected. Little's garbled extraction was supplemented by visual reading of article p.125, including section 1.2's factorization.

Fourteen cited works have local PDFs; Carpenter-Smuk has full official XML freshly retrieved from Europe PMC. **Two cited works lack fresh substantive full-text verification:** Manski (publisher abstract only) and Shardell-El-Kamary (PubMed abstract verified; fresh PMC/Europe PMC methods/PDF access failed or returned a challenge). Earlier audits' full-HTML reading is not adopted as this audit's own. Carpenter/Shardell PDF attempts returned 403 or HTML and were not saved as PDFs. No access control was bypassed. Three cited works therefore lack a local PDF, but only two lack substantive full text in another format.

### 8.2 Every existing bibliography entry

| Reference | DOI | PDF status | Citation accuracy | Recommendation |
|---|---|---|---|---|
| Manski, 2005, *Partial identification with missing data: concepts and findings*, IJAR 39(2-3):151-165 | [10.1016/j.ijar.2004.10.006](https://doi.org/10.1016/j.ijar.2004.10.006) | No PDF; publisher abstract | Intro:14's generic observed-plus-admissible-missing-laws statement is supported by abstract; no full theorem/priority exclusion verified | Keep narrow attribution; seek legitimate full-text access before expanding |
| Little, 1993, *Pattern-Mixture Models for Multivariate Incomplete Data*, JASA 88(421):125-134 | [10.1080/01621459.1993.10594302](https://doi.org/10.1080/01621459.1993.10594302) | `R/little1993_escholarship_scan.pdf` | Visual p.125 section 1.2 equation (2) supports pattern factorization; extraction damaged | Keep; repository cover's 2011 deposit date is not journal year |
| Shardell and El-Kamary, 2009, *Sensitivity Analysis of Informatively Coarsened Data Using Pattern Mixture Models*, JBS 19(6):1018-1038 | [10.1080/10543400903242779](https://doi.org/10.1080/10543400903242779) | No PDF; [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/20183462/); methods inaccessible | Intro:14's coarsening/interval-censoring precedent supported by abstract; no complete-equivalence exclusion verified | Keep narrow wording; full-method comparison remains incomplete |
| Kline and Santos, 2013, *Sensitivity to missing data assumptions: Theory and an evaluation of the U.S. wage structure*, QE 4(2):231-267 | [10.3982/QE176](https://doi.org/10.3982/QE176) | `L/kline2013.pdf`, published article/EconStor cover | Section 2.1's maximal conditional KS discrepancy supports intro:19; different target/scale | Keep |
| Miao, Li, Zhang and Sun, 2025, *A stableness of resistance model for nonresponse adjustment with callback data*, JRSS B 87(2):433-456 | [10.1093/jrsssb/qkae097](https://doi.org/10.1093/jrsssb/qkae097) | `L/miao2025.pdf`, arXiv:2112.02822v5, 2025 | Assumption 1 and identification results support intro:16's stable response-odds/positivity contrast; no universal direction relative to MI | Keep; distinguish final metadata/author methods |
| Jiang and Ding, 2018, *Using missing types to improve partial identification with application to a study of HIV prevalence in Malawi*, AoAS 12(3):1831-1852 | [10.1214/17-AOAS1133](https://doi.org/10.1214/17-AOAS1133) | `L/jiang2018.pdf`, arXiv v6 | Assumption 1's partial-MAR missingness type supports intro:16 | Keep |
| Imbens and Manski, 2004, *Confidence Intervals for Partially Identified Parameters*, Econometrica 72(6):1845-1857 | [10.1111/j.1468-0262.2004.00555.x](https://doi.org/10.1111/j.1468-0262.2004.00555.x) | `L/imbens2004.pdf`, 2003 working paper | Introduction's parameter/whole-region coverage distinction supports intro:22; final DOI correct | Keep; precise final-theorem attribution would need final text |
| Howard, Ramdas, McAuliffe and Sekhon, 2021, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, AoS 49(2):1055-1080 | [10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991) | `L/howard2021.pdf`, author version | Mixtures/time-uniform bounds/beta-binomial construction support sequential background | Keep; cite beside sequential (17)-(19) |
| Waudby-Smith and Ramdas, 2024, *Estimating means of bounded random variables by betting*, JRSS B 86(1):1-27 | [10.1093/jrsssb/qkad009](https://doi.org/10.1093/jrsssb/qkad009) | `L/waudby2024.pdf`, discussion version | Bounded-mean betting methods support intro:22; no claim of using their most efficient CS | Keep |
| Ramdas, Grünwald, Vovk and Shafer, 2023, *Game-Theoretic Statistics and Safe Anytime-Valid Inference*, Statistical Science 38(4):576-601 | [10.1214/23-STS894](https://doi.org/10.1214/23-STS894) | `L/ramdas2023.pdf`, author version | Mixtures/maximal inequalities/anytime inference support stated background | Keep; point-of-use citation useful |
| Johari, Koomen, Pekelis and Walsh, 2022, *Always Valid Inference: Continuous Monitoring of A/B Tests*, OR 70(3):1806-1821 | [10.1287/opre.2021.2135](https://doi.org/10.1287/opre.2021.2135) | `L/johari2022.pdf`, 2019 three-author antecedent | General monitoring role supported by antecedent; current final four-author bibliography is correct | Keep general attribution; do not equate antecedent/final versions |
| Clopper and Pearson, 1934, *The use of confidence or fiducial limits illustrated in the case of the binomial*, Biometrika 26(4):404-413 | [10.1093/biomet/26.4.404](https://doi.org/10.1093/biomet/26.4.404) | `L/clopper1934.pdf`, scan | Original binomial-tail construction plus independent quantile calculation supports design:30/Supplement | Keep |
| Cro, Carpenter and Kenward, 2019, *Information-Anchored Sensitivity Analysis: Theory and Application*, JRSS A 182(2):623-645 | [10.1111/rssa.12423](https://doi.org/10.1111/rssa.12423) | `L/cro2019.pdf`, author version | Imputation's inferential-information preservation differs from Shannon dependence, accurately stated at intro:19 | Keep if useful; no equivalence claim |
| Carpenter and Smuk, 2021, *Missing data: A statistical framework for practice*, Biometrical Journal 63(5):915-947 | [10.1002/bimj.202000196](https://doi.org/10.1002/bimj.202000196) | PDF unavailable; official XML for PMC7615108 verified | Sections 6/8.2 support explicit MNAR sensitivity assumptions and contextual elicitation | Keep; report XML access accurately |
| Christensen and Connault, 2023, *Counterfactual Sensitivity and Robustness*, Econometrica 91(1):263-298 | [10.3982/ECTA17232](https://doi.org/10.3982/ECTA17232) | `L/christensen2023.pdf`, arXiv v4 | Latent-law divergence neighborhoods and moment restrictions support intro:19 | Keep |
| Jin, Ren and Zhou, 2026, *Sensitivity Analysis Under the f-Sensitivity Model: A Distributional Robustness Perspective*, OR 74(2):860-878 | [10.1287/opre.2023.0001](https://doi.org/10.1287/opre.2023.0001) | `L/jin2026.pdf`, arXiv:2203.04373v2, 2022, plural “models” title | Average selection-bias/DRO claim supported by antecedent setup; no final-theorem-change claim verified | Keep final metadata; distinguish antecedent |
| Lindon and Kallus, 2026, *Design-Based Anytime-Valid Inference for Randomized Experiments with Delayed Outcomes and Staggered Entry*, arXiv:2603.25971v2 | [10.48550/arXiv.2603.25971](https://doi.org/10.48550/arXiv.2603.25971), preprint DOI | `L/lindon2026.pdf`, v2, 29 May 2026 | Counterfactual calendar-time reward and event-time filtration support intro:22 | Precise v2 citation valid. Author lists an ICML 2026 item under earlier title; final proceedings identity was not independently resolved and needs confirmation |

No verified author/title/DOI error was found. Verification is limited by versions/access above; it is not correct to say all final published full texts were read.

### 8.3 Candidate additions and retained PDFs

| Reference | DOI | PDF status | Citation accuracy / relationship | Recommendation |
|---|---|---|---|---|
| Vansteelandt, Goetghebeur, Kenward and Molenberghs, 2006, *Ignorance and uncertainty regions as inferential tools in a sensitivity analysis*, Statistica Sinica 16(3):953-979 | No DOI located in publisher/institutional records and Crossref search; [identity](https://biblio.ugent.be/publication/357052) | `R/vansteelandt2006_StatSinica16-953.pdf` | Definition 3: whole ignorance-region coverage at fixed time | Strongly recommended, intro:22 |
| Dalal, Blöbaum, Kasiviswanathan and Ramdas, 2024, *Anytime-Valid Inference for Double/Debiased Machine Learning of Causal Parameters* | [10.48550/arXiv.2408.09598](https://doi.org/10.48550/arXiv.2408.09598), preprint DOI | `R/dalal2024_arXiv2408.09598v2.pdf` | Section 4 causal sensitivity bounds and nuisance-rate conditions contrast with finite-sample categorical model; no newer journal version verified | Strongly recommended, intro:22 |
| Lindon and Malek, 2022, *Anytime-Valid Inference for Multinomial Count Data*, NeurIPS 35:2817-2831 | [10.52202/068431-0204](https://doi.org/10.52202/068431-0204), proceedings DOI | `R/lindon2022_multinomial_arXiv2011.03567v2.pdf` | Joint Dirichlet-mixture CS; does not solve terminal identification | Strongly recommended, sequential:24/discussion:8 |
| Podkopaev and Ramdas, 2022, *Tracking the risk of a deployed model and detecting harmful distribution shifts*, ICLR | [10.48550/arXiv.2110.06177](https://doi.org/10.48550/arXiv.2110.06177), preprint DOI; publisher DOI not verified | `R/podkopaev2022_arXiv2110.06177v3.pdf` | Observed loss tracking, possibly delayed; no guarantee for unknown outcome-dependent permanent missingness | Useful, intro:22; not mandatory power baseline |
| Daly-Grafstein and Gustafson, 2026, *Partial identification with categorical data and nonignorable missing outcomes*, Canadian Journal of Statistics 54(3):e70037 | [10.1002/cjs.70037](https://doi.org/10.1002/cjs.70037) | `R/dalygrafstein2026_arXiv2308.07319v2.pdf`, 2023 antecedent titled *Partial identification for discrete data with nonignorable missing outcomes* | Bayesian restrictions/instruments/bias direction; final metadata checked, methods comparison uses antecedent | Useful recent contrast, intro:14; label version accurately |
| Johansson, 2017, *Arb: Efficient Arbitrary-Precision Midpoint-Radius Interval Arithmetic*, IEEE TC 66(8):1281-1292 | [10.1109/TC.2017.2690633](https://doi.org/10.1109/TC.2017.2690633) | **New:** `R/johansson2017_Arb_arXiv1611.02831.pdf` | Library foundation, not proof for TrajCert's surrounding floating operations | Strongly recommended, sequential:55 |
| Jung and Kang, 2026, *Information-Theoretic Causal Bounds under Unmeasured Confounding*, CLeaR, PMLR 323:1656-1692 | [10.48550/arXiv.2601.17160](https://doi.org/10.48550/arXiv.2601.17160), preprint DOI; no publisher DOI given | **New:** `R/jung2026_CLeaR_PMLR323-1656-1692.pdf`; distinct **new** antecedent `R/jung2026_information_bounds_arXiv2601.17160v2.pdf` | Final Assumption 4/Theorems 5,11 inspected; causal divergence balls/duality, not resolution-path MI | Optional, intro:19; cite [final PMLR record](https://proceedings.mlr.press/v323/jung26a.html) |
| Xu, Karampatziakis and Mineiro, 2024, *Active, anytime-valid risk controlling prediction sets*, NeurIPS 37:60110-60132 | [10.52202/079017-1920](https://doi.org/10.52202/079017-1920), verified proceedings DOI | `R/xu2024_arXiv2406.10490v2.pdf` | Known predictable query probabilities, inverse weighting/e-processes; different unknown nonresolution model | Optional for reliable ML/active-label framing |
| Waudby-Smith, Arbour, Sinha, Kennedy and Ramdas, 2024, *Time-uniform central limit theory and asymptotic confidence sequences*, AoS 52(6):2613-2640 | [10.1214/24-AOS2408](https://doi.org/10.1214/24-AOS2408) | `R/waudbysmith2024clt_arXiv2103.06476v9.pdf` | Asymptotic CS foundation, different from two-author bounded-betting citation | Optional; Dalal suffices for concise contrast |
| Bates, Angelopoulos, Lei, Malik and Jordan, 2021, *Distribution-free, Risk-controlling Prediction Sets*, JACM 68(6) | [10.1145/3478535](https://doi.org/10.1145/3478535) | `R/bates2021_arXiv2101.02703v3.pdf` | Labeled holdout calibration; not terminal missing-outcome identification | Optional ML context, otherwise unnecessary |
| Kaido, Molinari and Stoye, 2019, *Confidence Intervals for Projections of Partially Identified Parameters*, Econometrica 87(4):1397-1432 | [10.3982/ECTA14075](https://doi.org/10.3982/ECTA14075) | `R/kaido2019_ECTA14075_author.pdf`, published article | Calibrated fixed-time projection inference, not numerical conservativeness | Optional; do not add just for “projection” |

Xu's proceedings DOI was independently verified. No inaccessible/abstract-only paper is designated indispensable for a detailed method comparison. Historical candidate lists are not mandatory additions.

## 9. Missing or recent literature

Searches covered missing outcomes/MNAR, coarsening/verification trajectories, MI/divergence restrictions, categorical identification, sequential partial identification, multinomial CS, delayed-outcome risk and verified arithmetic. Fresh 2024-2026 screening followed relevant references, author publication lists and publisher records. This was a targeted primary-source review, not a database census. Abstracts/search hits do not establish equivalence.

| Closest challenge | Model, assumptions and guarantee | Distinction / placement |
|---|---|---|
| Fixed-time sensitivity regions: Vansteelandt et al. | Incomplete-data sensitivity models; whole ignorance-set uncertainty regions | Add coverage-target connection at intro:22; region coverage is established prior art |
| Sequential partial identification: Dalal et al., 2024 | Observed treatment/covariates/outcomes; confounding-sensitivity bounds, orthogonal scores and asymptotic CS under consistency/rate conditions | TrajCert instead uses finite-sample categorical inference, conditional on numerical enclosure. One contrast at intro:22 |
| Joint multinomial CS: Lindon-Malek | Fixed multinomial law; Dirichlet-mixture vector region | Alternative CS input, not a profile/frontier result or a proved universally better-power replacement. Cite after sequential:24 |
| Callback identification: existing Miao et al. | Multiple attempts; stable outcome-response odds effects and positivity | Already correctly contrasted at intro:16; arbitrary trajectory data are not newly introduced by TrajCert |
| Categorical MNAR: Daly-Grafstein-Gustafson, 2026 | Discrete outcome/treatment/instrument/missingness; restrictions on nonidentified parameters and Bayesian inference | Useful recent contrast at intro:14; not a time-uniform MI certificate |
| Risk tracking/active labels: Podkopaev-Ramdas; Xu et al., 2024 | Observed loss streams; known-probability label queries and weighted e-processes | Useful at intro:22 for an ML readership; unknown terminal completions require different assumptions |
| Information-theoretic causal bounds: Jung-Kang, 2026 | Final Assumption 4: positivity/absolute continuity/generator regularity. Theorem 5 bounds observational/interventional f-divergence by propensity; Theorem 11 supplies duality | Optional intro:19 comparison; not a calibration or observed estimate of I(L;J*) |

A surgical revision needs approximately four high-priority additions (Vansteelandt, Dalal, Lindon-Malek, Johansson), not every optional source. The defensible originality is the exact binary completion/profile and decision geometry plus integrated conservative sequential computation. The refinement identity derives from the chain rule; its completion-independent observable increment and exact frontier consequence are the useful specialization. Conservative search is a computational integration conditional on arithmetic, not a new general verified-optimization paradigm. No reviewed competitor was verified to subsume the entire combination. Access-limited cited works prevent an exhaustive full-text novelty exclusion.

## 10. Plagiarism and writing audit

### 10.1 Attribution and textual comparison

No plagiarism or inappropriate close paraphrase was established in the passages examined. That is a bounded assessment, not a similarity certificate. No trustworthy exhaustive similarity service was available, no percentage is reported, and prose style does not establish AI authorship. The existing AI-assistance declaration must remain factual and receive author approval.

| Manuscript passage | Primary source comparison | Assessment |
|---|---|---|
| Intro:14, pattern-mixture factorization | Little p.125 section 1.2, joint outcome/pattern factorization | Correct generic attribution, with standard terminology rather than a copied explanatory passage |
| Intro:16, missing types and callback contrast | Jiang Assumption 1; Miao Assumption 1/identification results | Assumptions differentiated accurately; no borrowed novelty claim established |
| Intro:19, KS sensitivity and divergence models | Kline section 2.1; Christensen model-neighborhood setup; Jin antecedent model | Accurate brief paraphrases with citations; version limits in section 8 still apply |
| Intro:19, information anchoring contrast | Cro author full text and Carpenter section 6.2 | Different inferential and Shannon meanings distinguished; no equivalence or unattributed reuse established |
| Intro:22 / sequential proof | Howard/Ramdas mixtures, maximal inequality; Lindon-Kallus v2 model/filtration | Established machinery acknowledged; nearby citations would aid attribution, not repair demonstrated plagiarism |

No exact replacement is needed for a verified plagiarism concern because none was retained. Point-of-use attribution in TC-PRIOR-ART is best scholarly practice, not an accusation that a proof of a standard chain-rule identity is plagiarism. Manski/Shardell methods remain access-limited; no full-text overlap conclusion is made for those sources.

### 10.2 Meaning-preserving local prose edits

These proposals implement TC-WRITING-REGISTER and related interpretive findings. They are not edits to the manuscript. Necessary caveats about rho, multiplicity, provenance and synthetic scope should stay close to the claims they limit.

| Exact location | Original sentence/phrase | Reason | Proposed replacement |
|---|---|---|---|
| results.tex:3 | “The current population-solver table aggregates 280 cases across four partitions and five information-offset levels, with 14 laws per combination.” | “Current table” reads as preparation history | “The population-solver validation comprises 280 cases: 14 laws at each combination of four partitions and five information-offset levels.” |
| results.tex:5 | “Stored tests of profile decomposition, curvature, minimum compatibility and constructive completions support the implementation of the analytical identities.” | “Stored tests” does not identify evidence type | “Recorded checks of the profile decomposition, curvature, compatibility floor and constructive completions support consistency of the implementation with the analytical identities.” |
| results.tex:5 | “Decision-targeted and full searches agree in 176 stored budget decisions.” | Remove process vocabulary, retain finite scope | “Decision-targeted and full searches agree on all 176 recorded budget comparisons.” |
| experiments.tex:40 | “We checked the report's 116 rendered-artifact hashes against their sources and destinations and reconstructed all power-checkpoint certification counts from the saved stream records.” | Long audit-log detail interrupts design narrative | “Publication tables and figures were checked against checksummed source records, and checkpoint certification counts were reconstructed from individual stream outcomes (Supplement).” Preserve the 116-pair detail in the Supplement |
| results.tex:44 | “Inspection of the batch counts shows that the nonzero diagnostics arise from empty running regions.” | State result directly | “Both nonzero diagnostics arise from empty running regions.” Keep the preceding description of the composite diagnostic |
| results.tex:61 | “A stored expected-count diagnostic for the low-prevalence law…” | “Stored” adds no scientific meaning here | “An expected-count diagnostic for the low-prevalence law…” Retain the following statement that it is deterministic, not Monte Carlo power |
| identification.tex:84 | “from the stored 1,001-point grid”; “at the stored sensitivity budgets” | Process qualifiers unnecessary in caption | “on a 1,001-point grid”; “at the evaluated sensitivity budgets.” Do not claim all 15 budgets are plotted when the panel shows only its displayed range |
| discussion.tex:11 | “The verified experiments show both consequences of retaining timing…” | “Verified experiments” can imply stronger numerical validation than demonstrated | “The synthetic experiments show both consequences of retaining timing…” |

The title accurately identifies sharp risk bounds and anytime certification under a sensitivity model. The abstract states model, theory and designed-law results and distinguishes the stronger-timing finite-sample example from the population example; TC-BUDGET-DIRECTION offers a clearer final qualifier. The section order is coherent and does not need wholesale restructuring. The main text should retain the central assumptions and negative controls. Detailed numerical stopping decomposition and pilot records fit the Supplement, with the main interpretation corrected at its point of use. No sound theorem, successful result or unfavorable outcome should be removed for cosmetic reasons.

### 10.3 Figures, tables and visual QA

All 17 article pages and six Supplement pages were rendered to temporary PNGs and visually inspected. Main equations, four tables, three figures, captions, declarations, references and complete Supplement Table S1 were checked. No content clipping, overlapping legend, missing symbol, blank page or substantive float failure was found. The build PDFs and canonical PDFs match byte for byte; existing build logs show no undefined references/citations, overfull boxes or missing-character warnings. These are read-only checks, not a fresh compilation. The validation oracle also has the independent zero-resolved defect in TC-ORACLE-DEGENERACY; neither rendered figures nor passing tests certify its entire domain.

Figure 1's nats/risk axes, beta threshold, compatibility omissions and line-guide caveat are appropriate. Figure 2 uses **numeric logarithmic sample-size coordinates**, confirmed in `paper/tools/render_evidence.py:40` and the rendering; its axis is not ordinal. Its checkpoint values, marginal bands, legend, line styles and markers match the records. Figure 3 likewise uses log-spaced numerical K values, with distinct population-ms and outer-seconds panels. Different line/marker styles aid monochrome interpretation, although this audit did not perform a separate publisher print-proof test. Population/Table 2 quantities are in nats and risk probability, stream counts have explicit denominators, and Clopper-Pearson precision at 88/100 preserves the target comparison. No graphical defect is retained merely because two close population curves overlap.

## 11. Adversarial reviewer assessment

These are three conceptual referee perspectives applied by one auditor, not three independent human reviews or external endorsements.

### Reviewer A: theoretical statistics and information theory

| Strong realistic objection | Assessment | Defensible response / minimal action |
|---|---|---|
| “The profile and refinement difference are elementary entropy manipulations; what is new?” | Legitimate positioning question; the manuscript already avoids claiming a new chain rule | Emphasize exact scalar completion, observable compatibility floor, sharp decision/frontier consequences and sequential integration. Add close region-inference precedent (TC-PRIOR-ART), not a broader novelty slogan |
| “Why does stronger outcome-timing association leave less concern about unresolved harm?” | Evidence sufficient, interpretation can improve | The total MI budget accounts for both mechanisms; equal excess budgets give equal endpoint intervals. TC-BUDGET-DIRECTION and TC-RHO-CALIBRATION answer this without inventing a terminal-selection estimate |
| “Does coarse sharpness still hold after fine margins are retained?” | Already resolved | Model:16 and Supplement:42 explicitly distinguish partition-relative sharpness and fine-data relaxation; no correction needed |
| “Fully observed outcomes can still violate the information budget.” | Valid local wording objection | Apply TC-THEOREM-STATEMENTS; preserve the proof |
| “Stable categories need not mean fixed latent risk.” | Implicit target already present; explicit wording useful | TC-FULL-LAW-STABILITY; no unrestricted drift claim |

### Reviewer B: sequential inference and numerical methods

| Strong realistic objection | Assessment | Defensible response / minimal action |
|---|---|---|
| “Is every reported proven_upper actually upward?” | Verified implementation-level limitation | TC-ROUNDING-SCOPE. Retain conditional theorem; supply complete enclosure justification or narrow implementation scope. Tests/margins cannot replace that argument |
| “Are finer-partition power losses numerical artifacts?” | Additional analysis of existing evidence is necessary for attribution | TC-NUMERICAL-NONRESOLUTION. The decomposition supports early two-band advantage and exposes later stalled decisions |
| “Why union-bound categorical coordinates if joint CS methods exist?” | Valid comparison, not an invalid construction | Cite Lindon-Malek, explain simple aggregate envelopes; no unsupported guarantee that changing CS always improves power (TC-PRIOR-ART) |
| “The 500-event study does not stress time-uniformity much.” | Correct as an empirical limitation, already scoped | Add existing long-horizon descriptive exclusions (TC-LONG-HORIZON-VALIDITY); no new campaign needed |
| “What does actual near-boundary monitoring cost?” | Evidence exists but underreported | TC-RUNTIME-REPORTING; distinguish median-of-checkpoint-medians and actual timed region |
| “Four unadjusted partitions permit post hoc selection?” | Already resolved | Sequential:70 and discussion:6 explicitly prohibit that interpretation and describe joint-allocation alternatives |

### Reviewer C: experiments and practical relevance

| Strong realistic objection | Assessment | Defensible response / minimal action |
|---|---|---|
| “The strong-timing law was designed to win.” | Deliberate selection disclosed; pilot influence can be clearer | Preserve mechanistic designed-law scope, matched null and small-margin noncertifying example. Add pilot selection details (TC-PILOT-DISCLOSURE) |
| “Rho looks arbitrary and cannot be validated from incomplete outcomes.” | Nonidentifiability correctly acknowledged | Explain conditional completion scale and external elicitation, not a plug-in estimator (TC-RHO-CALIBRATION) |
| “The incompatibility state did not protect against a false budget.” | Empirically true at these horizons; not a theorem failure | Report zero detection with the already retained 16/100 false-model certificates (TC-INCOMPATIBILITY-DETECTION) |
| “Can I reproduce the claimed source/configuration/results relationship?” | Current data checks verified; historical source attestation incomplete and disclosed | Portable code/design/evidence archive with honest limits (TC-ARCHIVE-EQUIVALENCE); no fabricated historical equivalence |
| “There is no real application.” | Optional enhancement for current theory-led scope | Current claims do not require one; TC-REAL-DATA. An application becomes essential only for new deployment/generalization claims |

**Desk-return/rejection risks:** unfinished authorship/declarations; submitting to a venue whose main interest is a substantive application without explaining this theory/computation contribution; an unsupported fully verified numerical-implementation claim. **Likely major-revision questions:** numerical scope, stopping decomposition, practical sensitivity interpretation and closest-prior-art positioning. These are judgments, not predictions of any editor's decision. No evidence supports a plagiarism/misconduct accusation, a claim that synthetic-only evidence is intrinsically invalid, or a demand to remove the correct identification results.

## 12. Journal positioning

The current wrapper names CSDA, but scientific fit should determine the eventual venue. Current quartiles, impact factors, acceptance rates and APC amounts were not independently verified; no Q1 label or acceptance probability is asserted.

| Venue / family | Verified official scope and article information | Fit judgment and implications |
|---|---|---|
| Computational Statistics & Data Analysis, Elsevier | [Official description](https://shop.elsevier.com/journals/computational-statistics-and-data-analysis/0167-9473) includes statistical methodology, numerical optimization, algorithms and software validation | Strong candidate if numerical scope and operational cost are handled carefully. Existing theory/synthetic evidence can support a methods article; an application may help but is not shown to be compulsory |
| Journal of Statistical Planning and Inference, Elsevier | [Official description](https://shop.elsevier.com/journals/journal-of-statistical-planning-and-inference/0378-3758) covers statistical inference, probability and related methodology, including research articles, reviews and short notes | Plausible theory-led fit; center identification/decision geometry and its sequential guarantee without pretending the chain rule is a new theorem |
| International Journal of Approximate Reasoning, Elsevier | [Official description](https://shop.elsevier.com/journals/international-journal-of-approximate-reasoning/0888-613X) covers uncertainty/imprecision in computational intelligence, decision theory and risk analysis; research/review articles | Conditional fit if decision under incomplete information is the focus. A historical Manski article alone is not evidence of current fit; connect present scope explicitly |
| Statistics and Computing, Springer Nature | [Official scope](https://link.springer.com/journal/11222/aims-and-scope) includes statistical computing, search/optimization and uncertainty quantification; original research reports. [Author instructions](https://link.springer.com/journal/11222/submission-guidelines) retrieved | Strong computational-methods alternative. Current instructions specify a 150-250-word abstract; choose template and verify all submission declarations after selecting venue. The scope page flags an OA transition affecting submissions from July 2026; authors should check current terms rather than rely on old fee assumptions |

The Elsevier ScienceDirect guides for CSDA and JSPI returned HTTP 403; their exact current length, line-number, page-size, reference-style, article-menu and upload rules therefore remain unverified. The shop descriptions establish scope, not every submission requirement. Letter paper and the absence of line numbers are not classified as verified rule violations. Do not change the manuscript to a speculative template.

The main article is 17 preprint pages including references, with a six-page Supplement. That is an observed length, not a verified venue limit. Proofs of core results and essential assumptions are present in the main text, with appropriate elaboration and complete final outcomes in the Supplement. Theoretical-statistics venues may ask for more substantial novelty; an applied journal may ask for an application. Neither is automatically a defect in this article's present claims.

The existing highlights file has five lines, with maximum length 79 characters including spaces. General [Elsevier highlights instructions](https://www.elsevier.support/publishing/answer/how-do-i-include-highlights-with-my-manuscript) specify three to five points and at most 85 characters each; whether highlights are mandatory and which editable file formats are accepted is journal-specific. Current [AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals) requires disclosure and author accountability for manuscript preparation; research-process use also belongs in Methods. Keep the present figure-workflow assistance disclosure where it helps satisfy that distinction. No tool-generated replacement may assert completed human review before it happens.

## 13. Submission-readiness checklist

| Requirement / check | Status and remaining action |
|---|---|
| All canonical manuscript sections / Supplement proofs examined | Completed; every main theorem/proposition reconstructed |
| Theory correctness and boundary treatment | Core results supported; TC-THEOREM-STATEMENTS local fix required; separate oracle defect TC-ORACLE-DEGENERACY |
| Numerical implementation claim | TC-ROUNDING-SCOPE required; conditional theorem remains valid |
| Main numerical counts and intervals traceable | Completed: all 32 power cells, 160 checkpoints, seven validity cells and population/scaling sources checked |
| Statistical/numerical noncertification interpretation | TC-NUMERICAL-NONRESOLUTION required |
| Main tables, figures and complete PDF visual review | Completed; numeric log axes verified, no ordinal-axis defect retained |
| Current reference identities | All 17 entries checked; 28 works assessed, 27 DOI identities verified, one explicit no-DOI exception |
| Full-text citation completeness | Two cited works remain limited to narrow abstract support; no detailed priority exclusion rests on them |
| Recent/direct competitor review | Completed to the stated targeted-search scope; additions and version caveats in sections 8-9 |
| Plagiarism/writing review | Completed bounded source comparisons and local edits; no plagiarism or AI-authorship inference established |
| Per-partition/stream validity and no drift extrapolation | Already explicit; optional target clarification strengthens it |
| Exploratory vs confirmatory evidence | Disjoint indices verified; pilot/design description and portable record recommended |
| Current artifact reproducibility | 116 rendered pairs and 523 archive payloads match; verified consistency, not a new scientific rerun |
| Historical per-run source reproducibility | Partially demonstrated, explicitly limited; not independently attested for all power runs |
| Authors, affiliations, correspondence, conflicts, funding, CRediT | Required author actions; no facts inferred |
| AI disclosure and human approval | Existing factual disclosure retained; author review/approval outstanding |
| Venue compliance and current ranking/fees | Exact Elsevier guides inaccessible; authors verify after selection; no Q1 or fee assertion |
| New experiments required for current claims | None prescribed. Additional numerical verification is narrowly targeted; real application optional |

### Audit execution and repository integrity

The user-authorized persistent outputs are this authoritative `paper/audit.md` and legitimate PDFs in `paper/references_pdf/`. All intermediate extraction, rendering, metadata, checks and test outputs were placed outside the repository. No manuscript, bibliography, figure, table, Supplement, existing PDF, source code, test, config, lock or scientific result was edited. No experiment rerun, branch switch, commit, history rewrite or push was performed.

**Final integrity comparison:** PASS: all 13,981 inventoried protected files have identical SHA-256 digests, with no added protected-path files; Git HEAD remains e628f0a and branch remains paper. Only paper/audit.md and three new reference PDFs are audit outputs.. The comparison hashes the 13,981 protected files inventoried at audit start and checks additions separately. It excludes only the allowed audit/reference directory plus `.git`, environments/worktrees and cache directories. It covers all canonical manuscript/code/config/results and submission archives. Existing research PDFs were read and preserved; only the three new, validated scholarly versions listed above were added. The complete Git HEAD and branch are checked separately. Temporary audit artifacts are removed after validation.

The isolated deterministic diagnostics additionally checked the zero-resolved validation oracle; its failure is recorded separately from the 136 passing existing tests. Material limits remain explicit: no complete floating-point proof, full scientific campaign, final-version access for every reference, exhaustive similarity service, historical per-run source attestation, external-dataset audit or accessible exact Elsevier guide. These are investigation limits, not assertions that the corresponding claims have failed.

## 14. Final ordered revision roadmap

1. **Resolve the numerical contract before claiming an implemented verified certificate.** Addresses TC-ROUNDING-SCOPE. Choose either full arithmetic verification/authorized numerical repair or the explicit conditional-scope route proposed in section 3. Check singleton midpoint roots, mass/geometry/objective rounding and mixture sign evaluations. Completion: the stated implementation guarantee is exactly the one justified; the explicit singleton counterexample is either excluded from verified output or safely enclosed. Do not silently regenerate results.
2. **Add the existing-record stopping decomposition and correct causal attribution.** Addresses TC-NUMERICAL-NONRESOLUTION, TC-RUNTIME-REPORTING and TC-INCOMPATIBILITY-DETECTION. Create one Supplement table in a later revision from saved batches, covering current state, ever certification, targeted/full mode, termination, stopped paths and runtime. Main text should explain the early endpoint refutations, later stalls and zero incompatibility detection. Completion: counts sum to 100 overall or explicitly 96 targeted; headline ever-certified counts remain unchanged; runtime aggregation is correctly labeled.
3. **Make the local theory/target clarifications.** Addresses TC-THEOREM-STATEMENTS and TC-FULL-LAW-STABILITY. Qualify c=0 by rho>=tau, and identify the fixed full-law theta/u at the stream assumption. Also document or repair the separate zero-resolved validation-oracle case (TC-ORACLE-DEGENERACY) in a later authorized task; this is not a change to the production identification result. Completion: Theorem 1 agrees with the explicit fully resolved example and Supplement; no new unnecessary independence assumption or drift guarantee is introduced. TC-REJECTION-COROLLARY may be added with the stated numerical hypotheses if desired.
4. **Clarify the sensitivity question and its scale.** Addresses TC-BUDGET-DIRECTION and TC-RHO-CALIBRATION. Insert one budget-accounting paragraph after equation (13) and one conditional unresolved-harm calibration paragraph/table. Completion: the ordinary .493/.324 and odds 25/12 reproduce, equal-excess-budget interpretation remains, and no data-estimated rho is implied.
5. **Add a small set of precise prior-art contrasts.** Addresses TC-PRIOR-ART. Add Vansteelandt, Dalal, Lindon-Malek and Johansson at the specified points; optionally add recent categorical/risk-control sources if relevant to readership. Completion: versions/DOIs match section 8, no unsupported priority statement appears, and limited-access works are not described as fully read. Recheck Lindon-Kallus conference status before altering its valid arXiv-v2 entry.
6. **Complete the portable design/provenance record.** Addresses TC-PILOT-DISCLOSURE and TC-ARCHIVE-EQUIVALENCE. Describe how pilots selected grids/horizons/comparators; include the distinct exploratory 200,000-event observation without pooling it. Authors archive code, locks, evidence, frozen config and pilot summary with checksums; retain historical source-attestation limits. Completion: all named artifacts are externally retrievable and a release/DOI is cited only if it exists. A new scientific rerun is needed only for a further equivalence claim that existing evidence cannot support.
7. **Add descriptive longer-horizon validity context.** Addresses TC-LONG-HORIZON-VALIDITY. Deduplicate by law/partition at longest horizon and report 58/2,100 as descriptive, with sharing/stopping caveats. Completion: no pooled binomial interval, familywise guarantee or proof-by-simulation claim is attached; Table 4 retains its separate denominators.
8. **Apply local prose edits and retain sound displays and disclosures.** Addresses TC-WRITING-REGISTER. Use section 10 replacements, update interpretations from steps 1-7, and preserve necessary caveats, negative controls and factual AI assistance. Completion: each revised sentence preserves evidence type/numbers; all figures remain faithful to source data. Figure 2 already has a numeric logarithmic axis and needs no ordinal-axis correction. TC-REAL-DATA remains optional unless claims are expanded.
9. **Complete author information and select a verified submission route.** Addresses TC-DECLARATIONS. Human authors supply all facts and approvals, choose the venue, obtain its current guide, then check format, article type, reference style, abstract/highlights limits and portal declarations. Completion: no pending author placeholder remains, actual review and responsibility are approved, and compliance is checked against the selected venue rather than presumed from a template.
10. **Perform a final surgical-revision consistency pass.** Reconcile main text, Supplement, captions, bibliography, declaration metadata and submission package after the authorized edits; render both PDFs and check the changed pages. Verify table values against unchanged source records and document any intentionally authorized numerical/code work separately. Completion: all Required findings are resolved, retained limitations remain visible, and no unsupported scientific expansion or hidden result replacement has occurred.
