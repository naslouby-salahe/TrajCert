# TrajCert manuscript

Canonical article: `main.tex`; bibliography: `references.bib`; supplement: `supplementary/supplement.tex`.

The current scientific disposition is in `audit.md`. Older files under `audits/` are preparation records and do not override it. Machine-readable current checks are `audits/verified_evidence.json`, `audits/revision_verification.json` and `audits/final_validation.json`.

Build from this directory using the established project process:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build supplementary/supplement.tex
cp build/main.pdf main.pdf
cp build/supplement.pdf supplementary/supplement.pdf
```

Read-only scientific-evidence checks and manuscript-only rendering:

```sh
../.venv/bin/python tools/audit_evidence.py
../.venv/bin/python tools/verify_revision.py
../.venv/bin/python tools/render_evidence.py
../.venv/bin/python tools/validate_manuscript.py
```

These operations do not run experiments or modify scientific inputs. The render script writes publication figures and the four original tables only; the foreign-information table is checked separately against completed records.

Current deliverables are `main.pdf`, `supplementary/supplement.pdf`, `submission_sources.zip`, and `supplementary/evidence_current.zip`. The current evidence archive contains 8,313 unchanged payloads with a SHA-256 manifest. The older `supplementary/evidence.zip` is preserved as historical evidence and is not distributed in the current source package. No permanent release DOI is claimed.

The source package is journal-neutral in content, using elsarticle as its existing preprint renderer. Author approval was confirmed by the user on 22 October 2026. Select a journal and adapt its template. The outstanding confidence-sign numerical contract is explicit in `audit.md` and the manuscript. Compilation is not submission approval.

Internal audits, build products and third-party reference PDFs are not submission material. Five editable highlights are supplied; their upload format must be checked for the chosen journal.
