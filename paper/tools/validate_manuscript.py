"""Check current publication sources and PDFs, without executing scientific code.

Optional --integrity-baseline DIR compares protected_before.json and git_before.json
captured before the editorial session. This is an editorial check, not a scientific test.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, re, subprocess
P=Path(__file__).resolve().parents[1]; R=P.parent
ap=argparse.ArgumentParser();ap.add_argument('--integrity-baseline',type=Path);args=ap.parse_args()
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def check(ok, message):
    if not ok: raise AssertionError(message)
def command(*a,cwd=P):return subprocess.check_output(a,cwd=cwd).decode()
texfiles=[P/'main.tex',P/'preamble.tex',*sorted((P/'sections').glob('*.tex')),*sorted((P/'tables').glob('*.tex')),P/'supplementary/supplement.tex']
alltex='\n'.join(f.read_text() for f in texfiles)
labels=re.findall(r'\\label\{([^}]+)\}',alltex)
check(not [k for k,v in Counter(labels).items() if v>1],'Duplicate labels')
check(set(re.findall(r'\\(?:eqref|ref)\{([^}]+)\}',alltex))<=set(labels),'Missing source label')
bib=(P/'references.bib').read_text(); entries=re.split(r'(?m)^@',bib)[1:]
keys=[re.match(r'\w+\{([^,]+),',e).group(1) for e in entries]
check(len(keys)==len(set(keys)),'Duplicate citation key')
cited={k.strip() for group in re.findall(r'\\cite\w*\{([^}]+)\}',alltex) for k in group.split(',')}
check(cited==set(keys),'Missing or unused citation: '+str(cited^set(keys)))
dois={};url_only={}
for key,entry in zip(keys,entries):
    d=re.search(r'\bdoi\s*=\s*\{([^}]+)\}',entry)
    u=re.search(r'\burl\s*=\s*\{([^}]+)\}',entry)
    if d:dois[key]=d.group(1).lower()
    else:
        check(u is not None,'No DOI or official URL: '+key);url_only[key]=u.group(1)
check(len(set(dois.values()))==len(dois),'Duplicate DOI')
metadata=json.loads((P/'literature/metadata/current_verification.json').read_text())
check({m['key'] for m in metadata}==set(dois),'DOI metadata coverage')
for m in metadata:check(m['status']=='VERIFIED' and m['doi'].lower()==dois[m['key']],'DOI metadata identity')
for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',alltex):check((P/name).is_file(),'Missing figure '+name)
for name in re.findall(r'\\input\{([^}]+)\}',alltex):check((P/(name if Path(name).suffix else name+'.tex')).is_file(),'Missing input '+name)
pdfchecks={}
for name,relative in [('main','main.pdf'),('supplement','supplementary/supplement.pdf')]:
    pdf=P/relative
    check(sha(pdf)==sha(P/f'build/{name}.pdf'),'Delivered PDF differs from latest build')
    log=(P/f'build/{name}.log').read_text()
    bad=[l for l in log.splitlines() if any(s in l for s in ['undefined','multiply defined','Overfull','Underfull','Missing character','LaTeX Error','! '])]
    check(not bad,'Build diagnostics: '+str(bad))
    info=command('pdfinfo',str(pdf));pages=int(re.search(r'Pages:\s*(\d+)',info).group(1))
    txt=command('pdftotext','-layout',str(pdf),'-');page_text=txt.split('\f')[:pages]
    check(all(len(re.sub(r'\s','',t))>100 for t in page_text),'Blank or nearly blank page')
    check('??' not in txt,'Unresolved PDF reference')
    for line in command('pdffonts',str(pdf)).splitlines()[2:]:
        m=re.search(r'\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$',line)
        check(m and m.group(1)=='yes','Unembedded font '+line)
    target='main.tex' if name=='main' else 'supplementary/supplement.tex'
    count=command('texcount','-inc','-sum',target)
    (P/f'build/{name}_texcount.txt').write_text(count)
    pdfchecks[name]={'pages':pages,'sha256':sha(pdf),'all_fonts_embedded':True,'no_missing_refs_or_bad_boxes':True,'page_text_lengths':[len(t) for t in page_text],'texcount_report':f'build/{name}_texcount.txt'}
check(len(re.findall(r'\\bibitem',(P/'build/main.bbl').read_text()))==len(keys),'Compiled bibliography count')
check(all(len(l)<=85 for l in (P/'highlights.txt').read_text().splitlines()),'Highlights longer than 85 characters')
report=json.loads((R/'results/project_summary/reproducibility/report_reproducibility.json').read_text())
for source in report['sources']:check(sha(R/source['source_path'])==source['source_sha256'],'Report source hash')
check(sha(R/'requirements.lock')==report['environment']['environment_lock_digest'],'Environment lock digest')
integrity={'baseline_checked':False}
if args.integrity_baseline:
    baseline=json.loads((args.integrity_baseline/'protected_before.json').read_text())
    changes=[str(f) for f,h in baseline.items() if not (R/f).is_file() or sha(R/f)!=h]
    check(not changes,'Protected file changed: '+str(changes[:10]))
    before=json.loads((args.integrity_baseline/'git_before.json').read_text())
    check(command('git','rev-parse','HEAD',cwd=R)==before['head'],'Git HEAD changed')
    check(command('git','ls-files','--stage',cwd=R)==before['index'],'Git index changed')
    outside=[l for l in command('git','status','--porcelain',cwd=R).splitlines() if not l[3:].startswith('paper/')]
    check(not outside,'Git changes outside paper: '+str(outside))
    integrity={'baseline_checked':True,'protected_files_unchanged':len(baseline),'head_unchanged':before['head'].strip(),'index_unchanged':True,'status_changes_only_in_paper':True}
validation={'date':'2026-10-22','mechanical_document_checks':'PASS','references':len(keys),'doi_metadata_verified':len(dois),'official_url_exceptions':url_only,'pdf':pdfchecks,'report_sources_hash_verified':len(report['sources']),'integrity':integrity,'scientific_guarantee_status':'CONDITIONAL: confidence-filter and summation contracts; see audit.md','author_review':'All-author approval confirmed by user on 2026-10-22; not inferred from mechanical checks','visual_inspection':'Recorded separately after inspecting rendered pages; not inferred from compilation'}
(P/'audits/final_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(validation,indent=2))
