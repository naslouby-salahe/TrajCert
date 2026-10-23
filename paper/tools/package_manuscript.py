"""Package existing publication sources; does not run or package experiments."""
from pathlib import Path
import hashlib,json,zipfile
P=Path(__file__).resolve().parents[1]
files=[P/'main.tex',P/'preamble.tex',P/'references.bib',P/'highlights.txt',P/'highlights.rtf',P/'supplementary/supplement.tex',*sorted((P/'sections').glob('*.tex')),*sorted((P/'tables').glob('*.tex')),*sorted((P/'figures').glob('*.pdf'))]
payload={str(f.relative_to(P)):f.read_bytes() for f in files}
payload['main.bbl']=(P/'build/main.bbl').read_bytes()
payload['README.md']=b"""# TrajCert publication sources

Main document: main.tex. Supplement: supplementary/supplement.tex.
Build both from the archive root, using a TeX distribution with latexmk,
elsarticle, natbib, the standard packages declared in preamble.tex, and BibTeX:

    latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
    latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build supplementary/supplement.tex

All figure PDFs, table inputs and bibliography sources are included. main.bbl
is supplied for submission systems that request a compiled bibliography.
Scientific simulations are not needed to compile the documents. The numerical
supporting records are supplied separately in evidence_current.zip; its manifest
identifies unchanged source payloads. Third-party reference PDFs and internal
preparation audits are not submission material and are excluded.

The manuscript uses elsarticle as its existing preprint renderer without naming
a target journal. The theorem states conditional numerical hypotheses; the
current fast confidence-sign filter lacks a uniform error derivation in the
available evidence. Historical source identity is also not fully attested.
Author approval was confirmed by the user on 22 October 2026. Journal-specific
submission requirements remain to be checked after venue selection.
"""
manifest={'date':'2026-10-22','canonical_main':'main.tex','canonical_supplement':'supplementary/supplement.tex','canonical_bibliography':'references.bib','files':[{'path':name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(payload.items())]}
data=(json.dumps(manifest,indent=2)+'\n').encode();(P/'submission_manifest.json').write_bytes(data)
with zipfile.ZipFile(P/'submission_sources.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name,data in sorted(payload.items()):z.writestr(name,data)
 z.write(P/'submission_manifest.json','submission_manifest.json')
print(json.dumps({'payloads':len(payload),'archive_sha256':hashlib.sha256((P/'submission_sources.zip').read_bytes()).hexdigest(),'bytes':(P/'submission_sources.zip').stat().st_size}))
