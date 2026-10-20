# TrajCert manuscript

Canonical article: `main.tex`; bibliography: `references.bib`; supplement: `supplementary/supplement.tex`. All numerical sources outside this directory are read only.

From `paper/`, build with:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build supplementary/supplement.tex
cp build/main.pdf main.pdf
cp build/supplement.pdf supplementary/supplement.pdf
```

The build runs from this directory because the supplement shares the preamble and generated tables. No absolute paths occur in manuscript inputs.

Read `audits/FINAL_MANUSCRIPT_AUDIT.md` for actual check status and remaining author actions. Internal audits, build products and downloaded third-party literature are not submission material. `highlights.txt` and `highlights.rtf` contain five editable highlight lines; the journal-specific upload format remains to be checked.

Optional read-only evidence validation and figure regeneration:

```sh
../.venv/bin/python tools/audit_evidence.py
../.venv/bin/python tools/render_evidence.py
```

These scripts write only within `paper/` and do not regenerate scientific experiments.

`supplementary/evidence.zip` contains the existing final decision, power and validity records with their checksums. The public code URL and inspected commit are stated in the article; no permanent archival DOI is asserted.
