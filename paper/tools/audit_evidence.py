"""Read-only checks of existing campaign artifacts; writes only paper/audits."""
from pathlib import Path
import csv, hashlib, json, math
from collections import Counter
import pyarrow.parquet as pq
from scipy.stats import beta
ROOT=Path(__file__).resolve().parents[2]
PAPER=ROOT/'paper'
def readcsv(exp,name):
 return list(csv.DictReader((ROOT/f'results/experiments/{exp}/tables/main/{name}.csv').open()))
def dump(name,x): (PAPER/'audits'/name).write_text(json.dumps(x,indent=2))
rpt=json.loads((ROOT/'results/project_summary/reproducibility/report_reproducibility.json').read_text())
checks=[]
for a in rpt['rendered_artifacts']:
 for kind in ['source','destination']:
  f=ROOT/a[kind+'_path']; assert hashlib.sha256(f.read_bytes()).hexdigest()==a[kind+'_sha256'], f
 checks.append(a)
assert hashlib.sha256((ROOT/'configs/trajcert.yaml').read_bytes()).hexdigest()==rpt['configuration_sha256']
assert (ROOT/'configs/trajcert.yaml').read_bytes()==(ROOT/'docs/audit/exploratory_pilots/configs_trajcert_frozen_2026-10-19.yaml').read_bytes()
summary=readcsv('anytime-certification-power','certification_power_summary')
power=readcsv('anytime-certification-power','certification_power')
allrecords={}
for f in (ROOT/'outputs/experiments/anytime-certification-power/evaluations/records').rglob('scientific_result.json'):
 d=json.loads(f.read_text()); allrecords[d['scenario_name'],d['band_count']]=(f,d)
assert len(allrecords)==len(summary)==32
batch_count=0
for row in summary:
 key=(row['scenario_name'],int(row['K'])); f,d=allrecords[key]
 assert d['streams']==int(row['independent_streams'])==100
 completed=ROOT/str(f.parent.relative_to(ROOT)).replace('evaluations/records','checkpoints/execution')/'COMPLETED.json'
 assert completed.exists()
 batches=list(completed.parent.glob('batch_*_result.json')); outcomes=[]
 for b in batches: outcomes+=json.loads(b.read_text())['outcomes']
 batch_count+=len(batches)
 assert len(outcomes)==100
 assert sorted(o['stream_index'] for o in outcomes)==list(range(1000000,1000100))
 for cp in [r for r in power if (r['scenario_name'],int(r['K']))==key]:
  n=int(cp['n_matured']); count=sum(any(c['matured_count']<=n and c['scientific_state']=='CERTIFIED' for c in o['checkpoints']) for o in outcomes)
  assert count==round(float(cp['ever_certified_rate'])*100)
  lo=0 if count==0 else beta.ppf(.025,count,101-count)
  hi=1 if count==100 else beta.ppf(.975,count+1,100-count)
  assert abs(lo-float(cp['ever_certified_cp_lower']))<1e-12
  assert abs(hi-float(cp['ever_certified_cp_upper']))<1e-12
 assert d['trajcert']['ever_certified']==int(row['certified_streams'])
 assert d['confidence_sequence_exclusions']==int(row['coverage_exclusions'])
 assert d['trajcert']['false_certifications']==int(row['false_certifications'])
 assert d['trajcert']['premature_certifications']==int(row['premature_certifications'])
 assert sum(v is None for v in d['first_certified'])/100==float(row['censored_fraction'])
coverage=readcsv('anytime-coverage-stress','anytime_coverage')
coverage=[r for r in coverage if r['method_name']=='TrajCert'];assert len(coverage)==7
for row in coverage:
 v=int(row['ever_violations']); assert int(row['independent_streams'])==500
 upper=beta.ppf(.95,v+1,500-v);assert abs(upper-float(row['clopper_pearson_upper_95']))<1e-12
 assert upper<.06
 assert int(row['certified_streams'])==0
coverage_batch=[]
for f in (ROOT/'outputs/experiments/anytime-coverage-stress/evaluations/records').rglob('scientific_result.json'):
 d=json.loads(f.read_text()); cp=ROOT/str(f.parent.relative_to(ROOT)).replace('evaluations/records','checkpoints/execution')
 assert (cp/'COMPLETED.json').exists()
 bs=[json.loads(b.read_text()) for b in cp.glob('batch_*_result.json')]
 assert sum(b['seed_index_stop_exclusive']-b['seed_index_start'] for b in bs)==500
 v=sum(b['confidence_sequence_violations'] for b in bs)
 coverage_batch.append({'path':str(f.relative_to(ROOT)),'construction_violations':v})
decision=readcsv('trajectory-decision-value','trajectory_decision_value');assert len(decision)==2160
flips=[r for r in decision if r['decision_changed']=='true'];assert len(flips)==34
unique={(r['law_name'],r['rho'],r['K']) for r in decision};assert len(unique)==360
scaling=readcsv('computational-scaling','computational_scaling')
for r in scaling:
 f=ROOT/f"outputs/experiments/computational-scaling/evaluations/records/k={r['K']}/scientific_result.json"
 d=json.loads(f.read_text())
 for t,prefix in [('population','population'),('outer_projection','outer')]:
  assert abs(float(r[prefix+'_median_runtime_ms'])-1000*d[t]['median_runtime_seconds'])<1e-9
oracle=readcsv('production-solver-vs-independent-oracle','solver_oracle_validation')
equiv=json.loads((ROOT/'docs/audit/campaign_run/verification/equivalence.json').read_text())
assert all(t['certified_full']==t['certified_fast'] for r in equiv for t in r['targets'])
science_files=[str(f.relative_to(ROOT)) for exp in ['anytime-certification-power','trajectory-decision-value','anytime-coverage-stress','production-solver-vs-independent-oracle','computational-scaling'] for f in (ROOT/f'outputs/experiments/{exp}/evaluations/records').rglob('scientific_result.json')]
# Confirm publication Parquet and CSV rows agree for the major tables.
for exp,name in [('anytime-certification-power','certification_power'),('anytime-certification-power','certification_power_summary'),('trajectory-decision-value','trajectory_decision_value'),('anytime-coverage-stress','anytime_coverage'),('computational-scaling','computational_scaling')]:
 par=pq.read_table(ROOT/f'outputs/experiments/{exp}/evaluations/aggregates/{name}.parquet').to_pylist()
 assert len(par)==len(readcsv(exp,name))
 keys=[k for k in ['scenario_name','law_name','stress_cell','method_name','rho','beta','K','n_matured'] if k in par[0]]
 def key(r): return tuple(str(r[k]) for k in keys)
 for a,b in zip(sorted(par,key=key),sorted(readcsv(exp,name),key=key)):
  for k,v in a.items():
   if v is None: assert b[k]==''
   elif isinstance(v,bool): assert b[k]==str(v).lower()
   elif isinstance(v,(float,int)): assert math.isclose(float(b[k]),v,rel_tol=1e-12,abs_tol=1e-14)
   else: assert str(v)==b[k], (exp,name,k,v,b[k])
results={'date':'2026-10-20','render_manifest_commit':rpt['git_commit'],'configuration_sha256':rpt['configuration_sha256'],'rendered_artifacts_hash_verified':len(checks),'power_cells':32,'power_batches':batch_count,'streams_per_power_cell':100,'checkpoint_rows':len(power),'power_false_certifications':sum(int(r['false_certifications']) for r in summary),'power_premature_certifications':sum(int(r['premature_certifications']) for r in summary),'power_coverage_exclusions_range':[min(int(r['coverage_exclusions']) for r in summary),max(int(r['coverage_exclusions']) for r in summary)],'decision_rows':2160,'distinct_law_rho_partition_profiles':len(unique),'decision_changed_rows':34,'decision_flips_by_law':dict(Counter(r['law_name'] for r in flips)),'decision_max_oracle_error':max(float(r['oracle_error']) for r in decision if r['oracle_error']),'coverage':coverage,'coverage_batch_checks':coverage_batch,'scaling':scaling,'solver_oracle_rows':len(oracle),'solver_oracle_columns':list(oracle[0]),'targeted_full_decisions':sum(len(r['targets']) for r in equiv),'all_targeted_full_decisions_agree':True,'scientific_records':science_files,'power_summary':summary}
dump('verified_evidence.json',results)
print(json.dumps({k:v for k,v in results.items() if k not in ['scientific_records','power_summary','coverage','coverage_batch_checks','scaling']},indent=2))
