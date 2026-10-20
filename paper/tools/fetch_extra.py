from pathlib import Path
import urllib.request,json,subprocess,concurrent.futures
P=Path(__file__).resolve().parents[1]
jobs={
'imbens2004':['https://scholar.harvard.edu/files/imbens/files/confidence_intervals_for_partially_identified_parameters.pdf','https://www.econstor.eu/bitstream/10419/79355/1/37481080X.pdf'],
'little1993':['https://escholarship.org/content/qt9jb3w254/qt9jb3w254.pdf?t=ldrw36'],
'shardell2009':['https://www.europepmc.org/articles/PMC3727411?pdf=render','https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3727411/fullTextXML'],
'carpenter2021':['https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7615108/fullTextXML'],
'lindon2026':['https://arxiv.org/pdf/2603.25971'],
}
def run(k,urls):
 for u in urls:
  try:
   req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
   with urllib.request.urlopen(req,timeout=25) as r:b=r.read()
   if b.startswith(b'%PDF'):
    f=P/f'literature/references_pdf/{k}.pdf';f.write_bytes(b);subprocess.run(['pdftotext','-layout',str(f),str(P/f'literature/fulltext/{k}.txt')],check=True)
    info={'key':k,'pdf_status':'DOWNLOADED','pdf_url':u};(P/f'literature/metadata/{k}_access.json').write_text(json.dumps(info,indent=2)); print(k,'PDF',flush=True);return
   elif b'<?xml' in b[:100]:
    (P/f'literature/fulltext/{k}.xml').write_bytes(b);(P/f'literature/metadata/{k}_access.json').write_text(json.dumps({'key':k,'pdf_status':'FULLTEXT_XML','fulltext_url':u},indent=2)); print(k,'XML',flush=True);return
   else: print(k,'NOT_PDF',flush=True)
  except Exception as e:print(k,str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(lambda kv:run(*kv),jobs.items()))
# Register and verify the arXiv DOI via its registration agency.
u='https://api.datacite.org/dois/10.48550/arxiv.2603.25971'
try:
 with urllib.request.urlopen(u,timeout=25) as r:d=json.load(r)
 (P/'literature/metadata/lindon2026.json').write_text(json.dumps(d,indent=2));print('LINDON_DATACITE_VERIFIED')
except Exception as e: print('DATACITE',e)
