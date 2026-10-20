# Reference and novelty audit

Retrieval/audit date: 20 October 2026. Canonical bibliography: `paper/references.bib`. All 17 cited works have independently retrieved registration metadata and successful DOI redirects (16 Crossref, one DataCite preprint). Exact HTTP outcomes are in `doi_resolution.json`; raw registration records are in `metadata/`. The DOI's destination need not permit automated full-text access.

Thirteen cited full-text PDFs are downloaded for private research, one additional full text is retained as XML. Shardell--El-Kamary was checked in full-text PMC HTML. Little's web PDF has encoding/download limitations; its narrow pattern-mixture attribution is corroborated by the publisher abstract. Manski is `ABSTRACT_ONLY` and supports only the general identification-region principle stated explicitly in that abstract. No detailed theorem, absence-of-equivalence claim, or priority claim rests on either limited-access source. Local antecedents and differing authorship/version histories are identified below rather than treated as final published PDFs. No copyrighted literature is placed in the submission bundle.

## Search and equivalence screening

Primary-source searches through 20 October 2026 included mutual-information sensitivity with missing outcomes; informative coarsening; callback resistance; missing-type sharp bounds; f-divergence sensitivity; divergence neighborhoods of latent laws; confidence-sequence projection; delayed and missing-outcome sequential inference. Indispensable foundations were retained, alongside 2021--2026 missing-data, confidence-sequence, callback and divergence literature. No arbitrary citation quota was used.

The principal novelty challenges are Jiang--Ding (richer observation types), Shardell--El-Kamary (informative coarsening), Miao et al. (callback paradata identification), Jin--Ren--Zhou (average divergence sensitivity), and established martingale inversion/projection. Their assumptions and targets were inspected as described below. The manuscript explicitly treats these as precedents and claims only the exact binary table specialization, profile/decision identities and integrated conservative procedure.

Additional 2026 screening: [Jung--Kang](https://arxiv.org/html/2601.17160) studies observational/interventional divergence bounds for causal effects; [sequential coverage-constrained model selection](https://arxiv.org/abs/2609.28522) uses confidence-region projection for a different estimand. These are background novelty checks, not cited evidence or claimed competitors. The former's setup and divergence formulation were inspected; the latter was abstract-level screening only, insufficient for a detailed equivalence exclusion. No universal or first-of-its-kind assertion is made.

## Version discipline

A resolvable DOI is not proof of bibliographic identity: the initial candidate Imbens DOI ended in 00538.x and resolved to a different work. It was rejected and replaced by the title-matched 00555.x record before bibliography delivery. Year fields use issue/publication years rather than automatically taking the first online date. Clopper--Pearson degree suffixes were removed from the author field after checking the original paper.

## manski2005

- Citation: Charles F. Manski (2005). Partial identification with missing data: concepts and findings. International Journal of Approximate Reasoning 39(2-3), 151-165.
- DOI: [10.1016/j.ijar.2004.10.006](https://doi.org/10.1016/j.ijar.2004.10.006); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://www.sciencedirect.com/science/article/pii/S0888613X04001124](https://www.sciencedirect.com/science/article/pii/S0888613X04001124). Status: `ABSTRACT_ONLY`.
- Local source: `Not downloaded; access outcomes above`.
- Relevant content: Publisher abstract.
- Manuscript attribution: Partial identification combines observed data with admissible missing-outcome laws.
- Verification/version: No detailed theorem or novelty exclusion relies on this inaccessible full text.
- Assumptions and relationship: General incomplete-outcome framework; binary bounds are proved independently here.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## little1993

- Citation: Roderick J. A. Little (1993). Pattern-Mixture Models for Multivariate Incomplete Data. Journal of the American Statistical Association 88(421), 125-134.
- DOI: [10.1080/01621459.1993.10594302](https://doi.org/10.1080/01621459.1993.10594302); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://escholarship.org/content/qt9jb3w254/qt9jb3w254.pdf](https://escholarship.org/content/qt9jb3w254/qt9jb3w254.pdf). Status: `FULLTEXT_WEB_ENCODING_LIMITED`.
- Local source: `Not downloaded; access outcomes above`.
- Relevant content: Publisher abstract; original article p.125, web PDF cover and partially encoded text.
- Manuscript attribution: Pattern-mixture factorization by missingness pattern.
- Verification/version: Web PDF exists but local download returned 403 and extraction was corrupted; the narrow attribution is independently verified in the publisher abstract.
- Assumptions and relationship: Foundational factorization; no claim that TrajCert subsumes general pattern-mixture models.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## shardell2009

- Citation: Michelle Shardell; Samer S. El-Kamary (2009). Sensitivity Analysis of Informatively Coarsened Data Using Pattern Mixture Models. Journal of Biopharmaceutical Statistics 19(6), 1018-1038.
- DOI: [10.1080/10543400903242779](https://doi.org/10.1080/10543400903242779); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://pmc.ncbi.nlm.nih.gov/articles/PMC3727411/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3727411/). Status: `FULLTEXT_WEB_VERIFIED`.
- Local source: `Not downloaded; access outcomes above`.
- Relevant content: Sections 2.1--2.3, equations (1)--(9), conclusion.
- Manuscript attribution: Pattern-mixture exponential tilting relaxes coarsening at random for incomplete outcomes and interval-censored times.
- Verification/version: PDF download challenged; full mathematical setup read through the lawful PMC HTML.
- Assumptions and relationship: Close conceptual predecessor; different observation structure and restrictions, not a quantitative power comparator.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## kline2013

- Citation: Patrick Kline; Andres Santos (2013). Sensitivity to missing data assumptions: Theory and an evaluation of the U.S. wage structure. Quantitative Economics 4(2), 231-267.
- DOI: [10.3982/qe176](https://doi.org/10.3982/qe176); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://www.econstor.eu/bitstream/10419/150349/1/v4-i2-p231-267-QE176.pdf](https://www.econstor.eu/bitstream/10419/150349/1/v4-i2-p231-267-QE176.pdf). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/kline2013.pdf`.
- Relevant content: Section 2.1 (index of selection), Assumption 2.1, sharp quantile bounds.
- Manuscript attribution: Maximal conditional Kolmogorov--Smirnov distance indexes missing-data sensitivity.
- Verification/version: Published article, EconStor cover preceding article.
- Assumptions and relationship: Different discrepancy and quantile target; no claimed universal mapping to rho.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## miao2025

- Citation: Wang Miao; Xinyu Li; Ping Zhang; Baoluo Sun (2025). A stableness of resistance model for nonresponse adjustment with callback data. Journal of the Royal Statistical Society Series B: Statistical Methodology 87(2), 433-456.
- DOI: [10.1093/jrsssb/qkae097](https://doi.org/10.1093/jrsssb/qkae097); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/2112.02822](https://arxiv.org/pdf/2112.02822). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/miao2025.pdf`.
- Relevant content: Section 2, Assumption 1, Proposition 1, Theorem 1 and identification proof.
- Manuscript attribution: Stableness of resistance across the first two callbacks, plus positivity, identifies the full law.
- Verification/version: Downloaded arXiv v5 dated 1 June 2025; some supplemental cross-reference placeholders occur in that author version. Final journal bibliographic metadata verified independently.
- Assumptions and relationship: Close paradata/identification predecessor. Path timing is not claimed new; no callback estimator dominance or nesting claimed.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## jiang2018

- Citation: Zhichao Jiang; Peng Ding (2018). Using missing types to improve partial identification with application to a study of HIV prevalence in Malawi. The Annals of Applied Statistics 12(3), 1831-1852.
- DOI: [10.1214/17-aoas1133](https://doi.org/10.1214/17-aoas1133); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/1610.01198](https://arxiv.org/pdf/1610.01198). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/jiang2018.pdf`.
- Relevant content: Section 2, Assumption 1, Theorem 1 and its proof.
- Manuscript attribution: Multiple missing types under partial missing-at-random restrictions can sharpen binary bounds.
- Verification/version: Author version v6, 11 September 2018.
- Assumptions and relationship: Close example of observation-type information; different restriction from a joint information budget.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## imbens2004

- Citation: Guido W. Imbens; Charles F. Manski (2004). Confidence Intervals for Partially Identified Parameters. Econometrica 72(6), 1845-1857.
- DOI: [10.1111/j.1468-0262.2004.00555.x](https://doi.org/10.1111/j.1468-0262.2004.00555.x); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://www.cemmap.ac.uk/wp-content/uploads/2020/08/CWP0903.pdf](https://www.cemmap.ac.uk/wp-content/uploads/2020/08/CWP0903.pdf). Status: `FULLTEXT_PDF_VERIFIED_ANTECEDENT`.
- Local source: `literature/references_pdf/imbens2004.pdf`.
- Relevant content: Working-paper abstract and Section 1; final publisher abstract corroborates the distinction.
- Manuscript attribution: Parameter coverage and simultaneous identified-set coverage are different targets.
- Verification/version: CWP09/03, May 2003; not represented as the final 2004 typeset article. No final-version theorem is imported.
- Assumptions and relationship: TrajCert gives a conservative uniform upper projection for the identified set.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## howard2021

- Citation: Steven R. Howard; Aaditya Ramdas; Jon McAuliffe; Jasjeet Sekhon (2021). Time-uniform, nonparametric, nonasymptotic confidence sequences. The Annals of Statistics 49(2), 1055-1080.
- DOI: [10.1214/20-aos1991](https://doi.org/10.1214/20-aos1991); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/1810.08240](https://arxiv.org/pdf/1810.08240). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/howard2021.pdf`.
- Relevant content: Mixture construction; beta-binomial mixture, Proposition 7; Section 3/Appendix conjugate mixtures.
- Manuscript attribution: Confidence sequences and mixture martingales supply established time-uniform machinery.
- Verification/version: Downloaded arXiv v9, August 2022; final 2021 journal metadata independently verified.
- Assumptions and relationship: Ingredient, not claimed invention. TrajCert separately derives its exact Bernoulli mixture and projection proof.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## waudby2024

- Citation: Ian Waudby-Smith; Aaditya Ramdas (2024). Estimating means of bounded random variables by betting. Journal of the Royal Statistical Society Series B: Statistical Methodology 86(1), 1-27.
- DOI: [10.1093/jrsssb/qkad009](https://doi.org/10.1093/jrsssb/qkad009); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://rss.org.uk/RSS/media/File-library/Events/Discussion%20meetings/Estimating-means-of-bounded-random-variables-by-betting.pdf](https://rss.org.uk/RSS/media/File-library/Events/Discussion%20meetings/Estimating-means-of-bounded-random-variables-by-betting.pdf). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/waudby2024.pdf`.
- Relevant content: Section 2, Theorem 1 and bounded-mean constructions.
- Manuscript attribution: Betting methods construct confidence sequences for bounded means.
- Verification/version: RSS discussion-meeting author manuscript, 2023; final issue is 2024, not online-first 2023.
- Assumptions and relationship: Alternative established confidence machinery; no superiority assertion or substitution into scientific code.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## ramdas2023

- Citation: Aaditya Ramdas; Peter Grünwald; Vladimir Vovk; Glenn Shafer (2023). Game-Theoretic Statistics and Safe Anytime-Valid Inference. Statistical Science 38(4), 576-601.
- DOI: [10.1214/23-sts894](https://doi.org/10.1214/23-sts894); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/2210.01948](https://arxiv.org/pdf/2210.01948). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/ramdas2023.pdf`.
- Relevant content: Sections 1--3: test martingales, e-processes, confidence sequences.
- Manuscript attribution: Nonnegative martingales and inversion underlie safe anytime-valid inference.
- Verification/version: Author version v2, 17 June 2023.
- Assumptions and relationship: General foundations; conservative projection is positioned as a specialization.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## johari2022

- Citation: Ramesh Johari; Pete Koomen; Leonid Pekelis; David Walsh (2022). Always Valid Inference: Continuous Monitoring of A/B Tests. Operations Research 70(3), 1806-1821.
- DOI: [10.1287/opre.2021.2135](https://doi.org/10.1287/opre.2021.2135); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/1512.04922](https://arxiv.org/pdf/1512.04922). Status: `FULLTEXT_PDF_VERIFIED_ANTECEDENT`.
- Local source: `literature/references_pdf/johari2022.pdf`.
- Relevant content: Introduction and always-valid inference construction; published title and abstract corroboration.
- Manuscript attribution: Always-valid inference supports continuous A/B monitoring.
- Verification/version: Local v3 (2019) lists Johari, Pekelis, Walsh; final 2022 Crossref/publisher record also includes Pete Koomen. Bibliography uses the four-author final record. Narrow continuous-monitoring attribution is shared; no claim of identical versions.
- Assumptions and relationship: Different observed target; no missing-label sensitivity identification is attributed to it.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## clopper1934

- Citation: C. J. CLOPPER; E. S. PEARSON (1934). THE USE OF CONFIDENCE OR FIDUCIAL LIMITS ILLUSTRATED IN THE CASE OF THE BINOMIAL. Biometrika 26(4), 404-413.
- DOI: [10.1093/biomet/26.4.404](https://doi.org/10.1093/biomet/26.4.404); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://www.barestatistics.nl/uploads/1/1/7/9/11797954/clopper__pearson_1934.pdf](https://www.barestatistics.nl/uploads/1/1/7/9/11797954/clopper__pearson_1934.pdf). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/clopper1934.pdf`.
- Relevant content: Sections 1--3, binomial probability equations and confidence limits.
- Manuscript attribution: Exact binomial confidence limits for stream-level certification proportions.
- Verification/version: Original article reproduction for personal research; authors normalized to names without academic degree suffixes. No redistribution in submission bundle.
- Assumptions and relationship: Monte Carlo reporting only; limits also independently recomputed from beta quantiles.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## cro2019

- Citation: Suzie Cro; James R. Carpenter; Michael G. Kenward (2019). Information-Anchored Sensitivity Analysis: Theory and Application. Journal of the Royal Statistical Society Series A: Statistics in Society 182(2), 623-645.
- DOI: [10.1111/rssa.12423](https://doi.org/10.1111/rssa.12423); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/1805.05795](https://arxiv.org/pdf/1805.05795). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/cro2019.pdf`.
- Relevant content: Section 2, definition of information anchoring and inferential-information ratio.
- Manuscript attribution: Information anchoring concerns loss of inferential information for treatment effects.
- Verification/version: Author version 2018; final issue-year 2019.
- Assumptions and relationship: Naming distinction from Shannon mutual information; not an equivalent sensitivity model.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## carpenter2021

- Citation: James R. Carpenter; Melanie Smuk (2021). Missing data: A statistical framework for practice. Biometrical Journal 63(5), 915-947.
- DOI: [10.1002/bimj.202000196](https://doi.org/10.1002/bimj.202000196); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7615108/fullTextXML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7615108/fullTextXML). Status: `FULLTEXT_XML_VERIFIED`.
- Local source: `literature/fulltext/carpenter2021.xml`.
- Relevant content: Introduction; missing-data assumptions and sensitivity-analysis sections.
- Manuscript attribution: Practical missing-data analysis requires explicit sensitivity assumptions.
- Verification/version: Full text lawfully obtained as XML and extracted to text; no PDF acquired.
- Assumptions and relationship: Motivation only; no detailed novel result is attributed.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## christensen2023

- Citation: Timothy Christensen; Benjamin Connault (2023). Counterfactual Sensitivity and Robustness. Econometrica 91(1), 263-298.
- DOI: [10.3982/ecta17232](https://doi.org/10.3982/ecta17232); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/1904.00989](https://arxiv.org/pdf/1904.00989). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/christensen2023.pdf`.
- Relevant content: Introduction, divergence neighborhoods and finite-dimensional dual formulation.
- Manuscript attribution: Counterfactual sensitivity can be studied by optimizing over neighborhoods of latent-variable laws.
- Verification/version: Author manuscript associated with the published work; reference is final 2023 Econometrica record.
- Assumptions and relationship: Establishes broad divergence-sensitivity precedent; different structural/causal targets.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## jin2026

- Citation: Ying Jin; Zhimei Ren; Zhengyuan Zhou (2026). Sensitivity Analysis Under the f -Sensitivity Model: A Distributional Robustness Perspective. Operations Research 74(2), 860-878.
- DOI: [10.1287/opre.2023.0001](https://doi.org/10.1287/opre.2023.0001); Crossref registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/2203.04373](https://arxiv.org/pdf/2203.04373). Status: `FULLTEXT_PDF_VERIFIED_ANTECEDENT`.
- Local source: `literature/references_pdf/jin2026.pdf`.
- Relevant content: Sections 1--3, Definition 1 (f,rho selection), Theorem 1/DRO formulation.
- Manuscript attribution: Average f-divergence selection restrictions lead to counterfactual bounds and robust estimation.
- Verification/version: Public v2 author version from September 2022; final publisher/Crossref record is Operations Research 74(2), 860--878, 2026. Broad model comparison corroborated by current publisher abstract.
- Assumptions and relationship: Closest divergence-sensitivity family found; no claim of invention of average discrepancy restrictions or generic DRO sensitivity.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.

## lindon2026

- Citation: Michael Lindon and Nathan Kallus (2026). Design-Based Anytime-Valid Inference for Randomized Experiments with Delayed Outcomes and Staggered Entry. Preprint arXiv:2603.25971v2.
- DOI: [10.48550/arxiv.2603.25971](https://doi.org/10.48550/arxiv.2603.25971); DataCite registration metadata independently retrieved; doi.org redirect `RESOLVED`.
- Full text: [https://arxiv.org/pdf/2603.25971](https://arxiv.org/pdf/2603.25971). Status: `FULLTEXT_PDF_VERIFIED`.
- Local source: `literature/references_pdf/lindon2026.pdf`.
- Relevant content: Sections 2--4, observations/estimands/filtration, arm-level CS and union bound.
- Manuscript attribution: Delayed outcomes and staggered entry require appropriate filtrations in design-based inference.
- Verification/version: Preprint v2, 29 May 2026. DOI is the arXiv/DataCite DOI, accurately labeled preprint; no journal publication asserted.
- Assumptions and relationship: Different design-based cumulative causal target, not binary latent stable-stream risk.
- Manuscript location: Related work; for clopper1934, Experimental design and Supplement.
