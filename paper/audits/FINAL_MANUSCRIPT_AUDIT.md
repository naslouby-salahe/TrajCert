# Final manuscript audit

Date: 20 October 2026.

**Title:** TrajCert: Sharp risk identification and anytime-valid certification with informative outcome-resolution paths.

**Verdict:** Complete scientific manuscript and submission-oriented package for author review. No correctable substantive mathematical/numerical manuscript blocker remains identified. Administrative upload readiness is not asserted; external author information, exact CSDA-specific rules and source-attestation limitations remain as itemized below.

## Deliverable metrics

| Item | Verified result |
|---|---|
| Main source | main.tex, with shared preamble and eight section files |
| Main PDF | main.pdf; 17 pages |
| Abstract | 195 whitespace-delimited words; within provisional250-word ceiling |
| Bibliography | references.bib;17 cited, unique scholarly entries; no uncited filler |
| DOI validation |17/17 registration-verified and independently redirected successfully;16 Crossref,1 DataCite preprint |
| Full-text retrieval |13 cited PDFs retained;1 additional full text as XML; Shardell verified in full-text HTML; Little encoding/download limitation and Manski abstract-only recorded |
| Main figures |3 vector PDF plots |
| Main tables |4 |
| Supplement | supplementary/supplement.tex and supplement.pdf;6 pages; complete analytical details,1 full32-row final-cell table, configuration/seed/provenance details |
| Scientific evidence archive | supplementary/evidence.zip;523 unchanged existing scientific data files plus manifest; no internal campaign-history or external raw dataset |
| Submission source archive | submission_sources.zip; canonical TeX/BibTeX, standard-package inputs, vector figures, tables, compiled bibliography, editable highlights; no audits/downloaded literature |
| Reference audit | literature/REFERENCE_AUDIT.md, raw registration records, DOI redirect results and13 PDFs |
| Evidence and review audits | EVIDENCE_AUDIT.md, HOSTILE_REVIEW.md, JOURNAL_COMPLIANCE.md |

## Technical checks actually performed

- `PASS`: main LaTeX and BibTeX compilation; supplementary compilation.
- `PASS`: no undefined citations/references, duplicate labels/keys, missing inputs/figures, missing glyph warnings, overfull boxes or underfull boxes in final logs.48 labels checked.
- `PASS`: all fonts embedded in both final PDFs; metadata titles and pending-author metadata are accurate. PDFs are unencrypted. PDF/UA tagging was not requested or audited.
- `PASS`: every page rendered and visually inspected through page contact sheets, with detailed review of the equations, power figure, numerical tables, final declarations and figures. No blank page, clipped item, orphaned float or overlapping legend remains identified.
- `PASS`: source archive freshly extracted and both documents compiled within paper/build/package_check; both resulting PDF text extractions exactly match the canonical build. This checks portability from packaged sources, not byte-identical creation timestamps.
- `PASS`: all17 bibliography entries are cited; all17 have title-matched registration metadata and successful DOI redirects. Specific antecedent-versus-final-version differences are disclosed in the reference audit.
- `PASS`: numeric tables, profile/decision and power figures use existing data only; meaningful denominators and units independently checked.
- `PASS`: current seven-cell validity evidence used; five retired scenarios, old12-cell study and deferred study absent from public manuscript/supplement. No obsolete optimizer-budget or sample-size narrative restored.
- `PASS`: five completed adversarial review lenses with actual corrections and recompile records. These are agent review passes, not independent external or human peer review.
- `PASS`: deterministic invisible-Unicode inspection of reader-facing sources; zero suspicious characters. No statistical watermark-removal or human-authorship claim.

Machine-readable results: final_validation.json, verified_evidence.json, package_validation.json, text_hygiene.json, review_validation.jsonl and figure_table_sources.json.

## Scientific consistency and contribution assessment

The central established result is the sharp scalar risk interval under the stated mutual-information model, with a constructive proof including degenerate cases. The exact timing-information increment supplies the compatibility and risk-frontier shift. Population information gain is not confused with finite-sample ordering; the effective-budget identity and partition-relative sharpness are explicit. The anytime theorem conditions on a stable observable law, a valid sensitivity budget and conservative numerical projection, with a per-fixed-partition error allocation.

The strongest verified empirical contribution is the frozen strong-timing experiment: K=2 certifies100/100 by5000 matured events versus96/100 for endpoint K=1 by50000 at rho=.08,beta=.09. At beta=.07, endpoint population identification cannot certify, while refined procedures certify99--100/100 by50000. These are designed synthetic-law findings, not a universal tenfold complexity rate. The matched null94/28/0/0 at50000 demonstrates the finite-sample cost of resolution without information. Population34/2160 decision-row changes and exact compatible intervals are independently traced to their original records.

The final coverage study has seven500-stream conditions with1,1,0,0,0,0,0 recorded diagnostics, whose exact one-sided upper limits are <=.0094523. It validates implementation behavior conditionwise and is separated from practical power. Direct-oracle errors are around10^-13, and the computational benchmark correctly distinguishes sub-millisecond population solving from second-scale broader finite-sample processing.

## Remaining issues, accurately scoped

1. **AUTHOR_ACTION:** names, affiliations, corresponding author details, funding, competing interests and CRediT contributions. Human authors must critically review and approve all mathematical/scientific content and the accurate Codex disclosure. No human review is falsely represented as complete.
2. **NOT_VERIFIED:** exact current CSDA guide details because the official guide returned403. Official Elsevier general LaTeX, highlights, AI and scope guidance was checked. Aims/scope fit is established; exact abstract/length/keyword/style/upload requirements remain flagged rather than invented.
3. **UNRESOLVED_REQUIRES_NEW_EVIDENCE:** per-run source-code digests/full equivalence of every power cell after runtime optimization. Available targeted/full decisions were independently verified; the separate11-case speed-equivalence assertion is described as campaign-reported. Resolving the missing per-run attestation would require evidence generation forbidden by this task. Claims were narrowed and the issue disclosed proportionately.
4. **ACCESS_LIMITATION:** Manski's full text was not obtained; only its explicit general abstract principle is attributed. Little's web PDF has local-download/encoding limitations; its narrow foundational attribution is independently supported by the publisher abstract. No detailed novelty exclusion relies on either source.
5. **No permanent release DOI/tag:** the actual public GitHub URL and inspected commit were verified; no permanent archive identity is invented. Supplementary evidence is supplied locally for submission.

These issues do not invalidate the conditional analytical results or the verified numerical claims. They prevent an unqualified assertion that the manuscript is ready for administrative upload without author review.

## Scientific repository preservation

- All427 initially tracked files have unchanged SHA-256.
- All12950 pre-existing files under docs/,configs/,outputs/,results/ have unchanged SHA-256.
- Source code, tests, configurations, dependency locks, roadmap, README and experimental output bytes were untouched. No scientific experiments were rerun and no raw HITL-IoT data were modified.
- Git HEAD remains6a37400fc10e977d4c568d7e94d88f3f49dd67aa. No branch, stage, commit, reset, push or history change was made.
- The only new working-tree entry is the authorized untracked paper/ directory; Git status outside paper/ and the staged index remain unchanged.
- All created files, retrieved literature, technical build files and packaged artifacts reside inside paper/.

## Files created

Technical build products and rendered QA pages are confined to build/. The non-build inventory follows; all were created within paper/.

- `README.md`
- `audits/EVIDENCE_AUDIT.md`
- `audits/HOSTILE_REVIEW.md`
- `audits/JOURNAL_COMPLIANCE.md`
- `audits/figure_table_sources.json`
- `audits/final_validation.json`
- `audits/package_validation.json`
- `audits/repository_before.json`
- `audits/repository_public_access.json`
- `audits/review_validation.jsonl`
- `audits/text_hygiene.json`
- `audits/verified_evidence.json`
- `figures/certification_power.pdf`
- `figures/computation.pdf`
- `figures/identification.pdf`
- `highlights.rtf`
- `highlights.txt`
- `literature/REFERENCE_AUDIT.md`
- `literature/doi_resolution.json`
- `literature/fetch_log.json`
- `literature/fulltext/carpenter2021.txt`
- `literature/fulltext/carpenter2021.xml`
- `literature/fulltext/christensen2023.txt`
- `literature/fulltext/clopper1934.txt`
- `literature/fulltext/cro2019.txt`
- `literature/fulltext/howard2021.txt`
- `literature/fulltext/imbens2004.txt`
- `literature/fulltext/jiang2018.txt`
- `literature/fulltext/jin2026.txt`
- `literature/fulltext/johari2022.txt`
- `literature/fulltext/kline2013.txt`
- `literature/fulltext/lindon2026.txt`
- `literature/fulltext/miao2025.txt`
- `literature/fulltext/ramdas2023.txt`
- `literature/fulltext/waudby2024.txt`
- `literature/metadata/alho1990.json`
- `literature/metadata/alho1990_access.json`
- `literature/metadata/carpenter2021.json`
- `literature/metadata/carpenter2021_access.json`
- `literature/metadata/christensen2023.json`
- `literature/metadata/christensen2023_access.json`
- `literature/metadata/clopper1934.json`
- `literature/metadata/clopper1934_access.json`
- `literature/metadata/cro2019.json`
- `literature/metadata/cro2019_access.json`
- `literature/metadata/csiszar1975.json`
- `literature/metadata/csiszar1975_access.json`
- `literature/metadata/howard2021.json`
- `literature/metadata/howard2021_access.json`
- `literature/metadata/imbens2004.json`
- `literature/metadata/imbens2004_access.json`
- `literature/metadata/jiang2018.json`
- `literature/metadata/jiang2018_access.json`
- `literature/metadata/jin2026.json`
- `literature/metadata/jin2026_access.json`
- `literature/metadata/johari2022.json`
- `literature/metadata/johari2022_access.json`
- `literature/metadata/kline2013.json`
- `literature/metadata/kline2013_access.json`
- `literature/metadata/lindon2026.json`
- `literature/metadata/lindon2026_access.json`
- `literature/metadata/little1993.json`
- `literature/metadata/little1993_access.json`
- `literature/metadata/manski2005.json`
- `literature/metadata/manski2005_access.json`
- `literature/metadata/miao2025.json`
- `literature/metadata/miao2025_access.json`
- `literature/metadata/ramdas2023.json`
- `literature/metadata/ramdas2023_access.json`
- `literature/metadata/shardell2009.json`
- `literature/metadata/shardell2009_access.json`
- `literature/metadata/waudby2024.json`
- `literature/metadata/waudby2024_access.json`
- `literature/references_pdf/christensen2023.pdf`
- `literature/references_pdf/clopper1934.pdf`
- `literature/references_pdf/cro2019.pdf`
- `literature/references_pdf/howard2021.pdf`
- `literature/references_pdf/imbens2004.pdf`
- `literature/references_pdf/jiang2018.pdf`
- `literature/references_pdf/jin2026.pdf`
- `literature/references_pdf/johari2022.pdf`
- `literature/references_pdf/kline2013.pdf`
- `literature/references_pdf/lindon2026.pdf`
- `literature/references_pdf/miao2025.pdf`
- `literature/references_pdf/ramdas2023.pdf`
- `literature/references_pdf/waudby2024.pdf`
- `main.pdf`
- `main.tex`
- `preamble.tex`
- `references.bib`
- `sections/declarations.tex`
- `sections/discussion.tex`
- `sections/experiments.tex`
- `sections/identification.tex`
- `sections/introduction.tex`
- `sections/model.tex`
- `sections/results.tex`
- `sections/sequential.tex`
- `submission_manifest.json`
- `submission_sources.zip`
- `supplementary/evidence.zip`
- `supplementary/supplement.pdf`
- `supplementary/supplement.tex`
- `tables/all_power.tex`
- `tables/coverage.tex`
- `tables/population.tex`
- `tables/power_selected.tex`
- `tools/audit_evidence.py`
- `tools/fetch_extra.py`
- `tools/fetch_literature.py`
- `tools/render_evidence.py`
- `tools/validate_manuscript.py`
- `audits/FINAL_MANUSCRIPT_AUDIT.md`
