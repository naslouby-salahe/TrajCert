"""Validate manuscript-only sources, PDFs and unchanged scientific inputs."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,os
P=Path(__file__).resolve().parents[1];R=P.parent

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def check(condition,message):
 if not condition:raise AssertionError(message)
texfiles=[P/'main.tex',P/'preamble.tex',*(P/'sections').glob('*.tex'),*(P/'tables').glob('*.tex'),P/'supplementary/supplement.tex']
article='\n'.join(f.read_text() for f in [P/'main.tex',*(P/'sections').glob('*.tex')])
alltex='\n'.join(f.read_text() for f in texfiles)
labels=re.findall(r'\\label\{([^}]+)\}',alltex)
check(not [k for k,v in Counter(labels).items() if v>1],'Duplicate labels')
refs=re.findall(r'\\(?:eqref|ref)\{([^}]+)\}',alltex)
check(set(refs)<=set(labels),'Missing source labels')
bib=(P/'references.bib').read_text();keys=re.findall(r'@\w+\{([^,]+),',bib)
check(len(keys)==len(set(keys))==17,'BibTeX key count/duplicates')
citations=[k.strip() for group in re.findall(r'\\cite\w*\{([^}]+)\}',alltex) for k in group.split(',')]
check(set(citations)==set(keys),'Missing or unused citations')
check(len(re.findall(r'\bdoi\s*=\s*\{',bib))==len(keys),'Missing DOI')
resolution=json.loads((P/'literature/doi_resolution.json').read_text())
check(len(resolution)==17 and all(r['status']=='RESOLVED' for r in resolution),'DOI resolution')
for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',alltex):check((P/name).is_file(),'Missing figure '+name)
for name in re.findall(r'\\input\{([^}]+)\}',alltex):check((P/(name if Path(name).suffix else name+'.tex')).is_file(),'Missing input '+name)
for forbidden in ['Timing-only harmful-late stress','Terminal-selection harmful-unresolved stress','Timing-and-terminal harmful-late stress','Timing-and-terminal harmful-early stress','Sixteen-band resolution stress','Sequential Sensitivity Utility','sequential utility','optimizer_stability','pre_campaign_projection']:
 check(forbidden.lower() not in (article+(P/'supplementary/supplement.tex').read_text()).lower(),'Excluded scientific narrative: '+forbidden)
check('/home/' not in article and 'C:\\' not in article,'Absolute manuscript input paths')
abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',article,re.S).group(1)
abstract_words=len(abstract.split());check(abstract_words<=250,'Provisional abstract ceiling')
pdfchecks={}
for name in ['main','supplement']:
 pdf=P/('main.pdf' if name=='main' else 'supplementary/supplement.pdf')
 check(pdf.exists(),'Missing final PDF')
 check(sha(pdf)==sha(P/f'build/{name}.pdf'),'Final PDF differs from latest build')
 log=(P/f'build/{name}.log').read_text()
 bad=[x for x in log.splitlines() if any(s in x for s in ['undefined','multiply defined','Overfull','Underfull','Missing character','LaTeX Error','! '])]
 check(not bad,'LaTeX warnings/errors '+str(bad))
 info=subprocess.check_output(['pdfinfo',str(pdf)]).decode();pages=int(re.search(r'Pages:\s*(\d+)',info).group(1))
 subprocess.run(['pdftotext','-layout',str(pdf),str(P/f'build/{name}.txt')],check=True)
 text=(P/f'build/{name}.txt').read_text();pagetext=text.split('\f')[:pages]
 check(all(len(re.sub(r'\s','',t))>100 for t in pagetext),'Blank/orphan PDF page')
 check('??' not in text,'Unresolved PDF reference')
 fonts=subprocess.check_output(['pdffonts',str(pdf)]).decode()
 for line in fonts.splitlines()[2:]:
  m=re.search(r'\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$',line)
  check(m and m.group(1)=='yes','Font embedding '+line)
 pdfchecks[name]={'pages':pages,'sha256':sha(pdf),'all_fonts_embedded':True,'no_missing_refs_or_bad_boxes':True,'page_text_lengths':[len(t) for t in pagetext]}
check(len(re.findall(r'\\bibitem', (P/'build/main.bbl').read_text()))==17,'Compiled bibliography count')
check(all(len(l)<=85 for l in (P/'highlights.txt').read_text().splitlines()),'Highlights length')
base=json.loads((P/'audits/repository_before.json').read_text())
changes=[]
for f,h in {**base['tracked_sha256'],**base['evidence_sha256']}.items():
 if not (R/f).is_file() or sha(R/f)!=h:changes.append(f)
check(not changes,'Scientific input changes '+str(changes[:10]))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip();check(head==base['commit'],'Changed Git HEAD')
status=subprocess.check_output(['git','status','--porcelain'],cwd=R).decode()
status_outside_paper='\n'.join(line for line in status.splitlines() if not line[3:].startswith('paper/'))
check(status_outside_paper.strip()==base['status'].strip(),'Changed Git status outside paper')
check(subprocess.run(['git','diff','--cached','--quiet'],cwd=R).returncode==0,'Index changed')
report=json.loads((R/'results/project_summary/reproducibility/report_reproducibility.json').read_text())
for s in report['sources']:check(sha(R/s['source_path'])==s['source_sha256'],'Source manifest mismatch')
check(sha(R/'requirements.lock')==report['environment']['environment_lock_digest'],'Environment lock digest')
review=[json.loads(l) for l in (P/'audits/review_validation.jsonl').read_text().splitlines()];check([x['pass'] for x in review]==list(range(1,6)),'Five review records')
validation={'status':'PASS','date':'2026-10-20','abstract_word_count_whitespace':abstract_words,'references':17,'doi_verified':17,'downloaded_cited_pdfs':sum((P/f'literature/references_pdf/{k}.pdf').exists() for k in keys),'additional_cited_fulltext_xml':1,'main_figures':len(re.findall(r'\\begin\{figure\}',article)),'main_tables':len(re.findall(r'\\begin\{table\}',article)),'supplementary_tables':1,'labels':len(labels),'pdf':pdfchecks,'initial_tracked_files_unchanged':len(base['tracked_sha256']),'existing_evidence_files_unchanged':len(base['evidence_sha256']),'git_head_unchanged':head,'git_status_outside_paper_unchanged':True,'git_status_current':status,'index_unchanged':True,'report_source_hashes_verified':len(report['sources']),'scientific_experiments_rerun':False,'review_passes':5,'journal_specific_guide':'NOT_VERIFIED_403','remaining_author_information':True,'source_attestation':'UNRESOLVED_REQUIRES_NEW_EVIDENCE'}
(P/'audits/final_validation.json').write_text(json.dumps(validation,indent=2));print(json.dumps(validation,indent=2))
