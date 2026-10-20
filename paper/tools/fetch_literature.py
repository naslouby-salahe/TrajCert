"""Retrieve registration metadata and lawful publisher/author PDFs into paper only."""
from pathlib import Path
import time,json,urllib.request,urllib.parse,concurrent.futures,subprocess,re
P=Path(__file__).resolve().parents[1]
REFS={
'manski2005':('10.1016/j.ijar.2004.10.006',[]),
'little1993':('10.1080/01621459.1993.10594302',['https://escholarship.org/content/qt9jb3w254/qt9jb3w254.pdf']),
'shardell2009':('10.1080/10543400903242779',[]),
'kline2013':('10.3982/QE176',['https://www.econstor.eu/bitstream/10419/150349/1/v4-i2-p231-267-QE176.pdf']),
'miao2025':('10.1093/jrsssb/qkae097',['https://arxiv.org/pdf/2112.02822']),
'jiang2018':('10.1214/17-AOAS1133',['https://arxiv.org/pdf/1610.01198']),
'alho1990':('10.1093/biomet/77.3.617',[]),
'imbens2004':('10.1111/j.1468-0262.2004.00555.x',[]),
'howard2021':('10.1214/20-AOS1991',['https://arxiv.org/pdf/1810.08240']),
'waudby2024':('10.1093/jrsssb/qkad009',['https://rss.org.uk/RSS/media/File-library/Events/Discussion%20meetings/Estimating-means-of-bounded-random-variables-by-betting.pdf','https://arxiv.org/pdf/2010.09686']),
'ramdas2023':('10.1214/23-STS894',['https://arxiv.org/pdf/2210.01948']),
'johari2022':('10.1287/opre.2021.2135',['https://arxiv.org/pdf/1512.04922']),
'clopper1934':('10.1093/biomet/26.4.404',[]),
'cro2019':('10.1111/rssa.12423',['https://arxiv.org/pdf/1805.05795']),
'carpenter2021':('10.1002/bimj.202000196',[]),
'christensen2023':('10.3982/ECTA17232',['https://arxiv.org/pdf/1904.00989']),
'jin2026':('10.1287/opre.2023.0001',['https://arxiv.org/pdf/2203.04373']),
'csiszar1975':('10.1214/aop/1176996454',[]),
}
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'TrajCert-manuscript-audit/1.0','Accept':'*/*'})
 for attempt in range(4):
  try:
   with urllib.request.urlopen(req,timeout=25) as r:return r.read(),r.geturl(),r.status
  except Exception:
   if attempt==3: raise
   time.sleep(2*(attempt+1))

def fetch(key,item):
 doi,urls=item;mp=P/'literature/metadata'/f'{key}.json'
 if mp.exists() and json.loads(mp.read_text())['DOI'].lower()==doi.lower():m=json.loads(mp.read_text())
 else:
  raw,_,_=get('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''));m=json.loads(raw)['message'];mp.write_text(json.dumps(m,indent=2))
 assert m['DOI'].lower()==doi.lower()
 info={'key':key,'doi':doi,'registration':'CROSSREF_VERIFIED','title':m['title'][0],'attempts':[]}
 pdf=P/'literature/references_pdf'/f'{key}.pdf'
 if pdf.exists(): info['pdf_status']='DOWNLOADED';info['pdf_url']='SEE_PREVIOUS_FETCH_LOG'
 else:
  urls=urls+[x['URL'] for x in m.get('link',[]) if x.get('content-type')=='application/pdf']
  for url in dict.fromkeys(urls):
   try:
    raw,final,status=get(url)
    if not raw.startswith(b'%PDF'): raise ValueError('NOT_PDF')
    pdf.write_bytes(raw);info['pdf_status']='DOWNLOADED';info['pdf_url']=final;break
   except Exception as e:info['attempts'].append({'url':url,'error':str(e)})
  else: info['pdf_status']='NOT_OBTAINED'
 if pdf.exists():subprocess.run(['pdftotext','-layout',str(pdf),str(P/'literature/fulltext'/f'{key}.txt')],check=True)
 (P/'literature/metadata'/f'{key}_access.json').write_text(json.dumps(info,indent=2))
 return info
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
  results=list(ex.map(lambda kv: fetch(*kv),REFS.items()))
 (P/'literature/fetch_log.json').write_text(json.dumps(results,indent=2))
 for r in results:print(r['key'],r['doi'],r['pdf_status'],r['title'])
