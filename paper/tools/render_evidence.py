"""Render only stored, verified campaign values. No experiment execution."""
from pathlib import Path
import os
os.environ.setdefault("MPLCONFIGDIR",str(Path(__file__).resolve().parents[1]/"build/matplotlib"))
import csv,json,hashlib
import numpy as np
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1]; R=P.parent
plt.rcParams.update({'font.family':'serif','font.size':10,'axes.labelsize':10,'axes.titlesize':10,'legend.fontsize':9,'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
SOURCES=[]
def csvrows(exp,name):
 f=R/f'results/experiments/{exp}/tables/main/{name}.csv'; SOURCES.append(f);return list(csv.DictReader(f.open()))
def save(fig,name):
 fig.savefig(P/f'figures/{name}.pdf',bbox_inches='tight');fig.savefig(P/f'build/{name}.png',dpi=160,bbox_inches='tight');plt.close(fig)
def table(name,body): (P/f'tables/{name}.tex').write_text(body+'\n')
dec=csvrows('trajectory-decision-value','trajectory_decision_value')
pow=csvrows('anytime-certification-power','certification_power')
sumr=csvrows('anytime-certification-power','certification_power_summary')
cov=csvrows('anytime-coverage-stress','anytime_coverage')
sca=csvrows('computational-scaling','computational_scaling')
profilepath=R/'outputs/experiments/safety-and-intrinsic-impossibility/evaluations/aggregates/figure_information_profile.parquet'; SOURCES.append(profilepath)
profile=pq.read_table(profilepath).to_pylist()
colors=['#171717','#1971a5','#bd5b00','#87509f']; markers=['o','s','^','D']; styles=['-','--','-.',':']
fig,axs=plt.subplots(1,2,figsize=(6.7,2.7),layout='constrained')
a=axs[0];u=[r['u'] for r in profile];s=[r['information_profile'] for r in profile];a.plot(u,s,color=colors[0]);a.axhline(profile[0]['rho'],color=colors[1],ls='--',label=r'$\rho=0.05$');a.axhline(profile[0]['tau'],color=colors[2],ls=':',label=r'$\tau_8$');a.axvline(profile[0]['u_dagger'],color='0.6',lw=.8);a.axvspan(profile[0]['feasible_lower'],profile[0]['feasible_upper'],color=colors[1],alpha=.12);a.set(xlabel=r'Hidden harmful mass $u$',ylabel='Information (nats)',title='(a) Information profile at $K=8$',ylim=(0,max(s)*1.05));a.legend(loc='upper left',frameon=False)
a=axs[1]
for k,c,m,ls in zip([1,2,4,8],colors,markers,styles):
 rows=[r for r in dec if r['law_name']=='Timing and terminal: harmful outcomes resolve late' and int(r['K'])==k and float(r['beta'])==.06 and float(r['rho'])<=.15];rows.sort(key=lambda r:float(r['rho']))
 a.plot([float(r['rho']) for r in rows],[float(r['risk_upper']) if r['risk_upper'] else np.nan for r in rows],color=c,marker=m,ms=3,ls=ls,label=f'$K={k}$')
a.axhline(.06,color='0.4',ls='--',lw=.8);a.text(.146,.0615,r'$\beta=0.06$',ha='right',fontsize=9);a.set(xlabel=r'Sensitivity budget $\rho$ (nats)',ylabel='Sharp upper risk',title='(b) Risk under nested coarsening',xlim=(0,.15),ylim=(0,.12));a.legend(frameon=False,ncol=2,loc='upper left');a.set_xticks([0,.05,.10,.15]);a.set_xticklabels(['0','0.05','0.10','0.15']);save(fig,'identification')
fig,axs=plt.subplots(2,2,figsize=(6.7,5.5),layout='constrained')
scenarios=[('Strong timing contrast power','(a) Strong timing: $\u03b2=0.09$'),('Endpoint-uncertifiable budget','(b) Strong timing: $\u03b2=0.07$'),('Matched no-timing control','(c) Matched no-timing control'),('Low error-prevalence power','(d) Low prevalence: $\u03b8=0.01$')]
for a,(scenario,title) in zip(axs.flat,scenarios):
 for k,c,m,ls in zip([1,2,4,8],colors,markers,styles):
  rows=sorted([r for r in pow if r['scenario_name']==scenario and int(r['K'])==k],key=lambda r:int(r['n_matured']))
  x=np.array([int(r['n_matured']) for r in rows])/1000;y=np.array([float(r['ever_certified_rate']) for r in rows]);lo=np.array([float(r['ever_certified_cp_lower']) for r in rows]);hi=np.array([float(r['ever_certified_cp_upper']) for r in rows]);a.plot(x,y,color=c,marker=m,ls=ls,ms=4,label=f'$K={k}$');a.fill_between(x,lo,hi,color=c,alpha=.08)
 a.set(xscale='log',ylim=(0,1.045),title=title,xlabel='Matured events (thousands)',ylabel='Ever-certified proportion');a.set_xticks([.5,1,2,5,10,20] if scenario=='Low error-prevalence power' else ([10,20,50] if scenario=='Endpoint-uncertifiable budget' else [2,5,10,20,50]));a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x,pos:f'{x:g}'));a.xaxis.set_minor_locator(matplotlib.ticker.NullLocator());a.set_yticks([0,.25,.5,.75,1]);a.grid(axis='y',alpha=.18)
handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,frameon=False,ncol=4,loc='outside upper center');save(fig,'certification_power')
fig,axs=plt.subplots(1,2,figsize=(6.7,2.6),layout='constrained')
x=[int(r['K']) for r in sca]
for a,field,div,title,ylabel in [(axs[0],'population_median_runtime_ms',1,'(a) Population solver','Median runtime (ms)'),(axs[1],'outer_median_runtime_ms',1000,'(b) Outer projection','Median runtime (s)')]:
 a.plot(x,[float(r[field])/div for r in sca],'o-',color=colors[0],ms=4);a.set(xscale='log',title=title,ylabel=ylabel,xlabel='Resolved bands $K$',ylim=(0,.55 if div==1 else 8.3));a.set_xticks(x);a.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter());a.xaxis.set_minor_locator(matplotlib.ticker.NullLocator());a.grid(axis='y',alpha=.18)
save(fig,'computation')
rows=[r for r in dec if r['law_name']=='Timing and terminal: harmful outcomes resolve late' and float(r['rho'])==.05 and float(r['beta'])==.06]
table('population',r'\begin{tabular}{rrrrl}\toprule $K$ & $\tau_K$ & $\theta_{U,K}(0.05)$ & $\rho_K^*(0.06)$ & Decision\\\midrule'+'\n'+'\n'.join(f"{r['K']} & {float(r['tau']):.6f} & {float(r['risk_upper']):.6f} & {float(r['safety_frontier']):.6f} & "+('Certified' if r['scientific_state']=='CERTIFIED' else 'Uncertified')+r'\\' for r in rows)+r'\bottomrule\end{tabular}')
selected=[('Strong timing contrast power',1,50000),('Strong timing contrast power',2,5000),('Strong timing contrast power',4,5000),('Strong timing contrast power',4,10000),('Strong timing contrast power',8,10000),('Endpoint-uncertifiable budget',1,50000),('Endpoint-uncertifiable budget',2,50000),('Endpoint-uncertifiable budget',4,20000),('Endpoint-uncertifiable budget',8,50000)]
lines=[]
for scenario,k,n in selected:
 r=next(r for r in pow if r['scenario_name']==scenario and int(r['K'])==k and int(r['n_matured'])==n)
 lines.append(f"{float(r['beta']):.2f} & {k} & {n:,} & {round(float(r['ever_certified_rate'])*100)}/100 & [{float(r['ever_certified_cp_lower']):.4f}, {float(r['ever_certified_cp_upper']):.4f}]"+r'\\')
table('power_selected',r'\begin{tabular}{rrrrl}\toprule $\beta$ & $K$ & Horizon $n$ & Certified streams & Exact 95\% interval\\\midrule'+'\n'+'\n'.join(lines)+r'\bottomrule\end{tabular}')
labels={'High unresolvedness stress':'High unresolvedness','Independent resolution control':'Independent resolution','Low error-prevalence stress':'Low prevalence','Minimum-information completion stress':'Minimum-information completion','Near-certification risk-budget stress':'Near certification boundary','Near-degeneracy stress':'Near degeneracy','Thirty-two-band resolution stress':'Thirty-two bands'}
rows=[r for r in cov if r['method_name']=='TrajCert']
table('coverage',r'\begin{tabular}{lrrr}\toprule Scenario & $K$ & Violations / streams & One-sided 95\% upper\\\midrule'+'\n'+'\n'.join(f"{labels[r['stress_cell']]} & {r['K']} & {r['ever_violations']}/500 & {float(r['clopper_pearson_upper_95']):.5f}"+r'\\' for r in rows)+r'\bottomrule\end{tabular}')
# Complete final-cell summaries belong in the supplement, with all controls preserved.
short={'Endpoint-uncertifiable budget':'Endpoint-uncertifiable','Headline decision boundary':'Population decision boundary','Ignorable-delay valid regime':'Ignorable delay','Intrinsically uncertifiable law':'Intrinsic impossibility','Low error-prevalence power':'Low prevalence','Matched no-timing control':'No timing control','Misspecified sensitivity budget':'Misspecified sensitivity','Model-incompatible budget':'Incompatible budget','Near-degeneracy power':'Near degeneracy','Optional-stopping looks':'Dense monitoring','Strong timing contrast power':'Strong timing','True risk near budget':'Risk near budget','Unsafe compatible law':'Unsafe law'}
lines=[]
for r in sumr:
 lines.append(f"{short[r['scenario_name']]} & {r['K']} & {float(r['rho']):.4f} & {float(r['beta']):.3f} & {int(r['horizon']):,} & {r['certified_streams']}/100 & [{float(r['power_cp_lower']):.3f}, {float(r['power_cp_upper']):.3f}]"+r'\\')
table('all_power', r'\small\begin{longtable}{lrrrrrl}\caption{All 32 final-cell certification outcomes. Intervals are conditionwise two-sided exact 95\% intervals for ever certifying by the horizon, using 100 trials per row.}\label{tab:allpower}\\\toprule Scenario & $K$ & $\rho$ & $\beta$ & Horizon & Certified & 95\% interval\\\midrule\endfirsthead\toprule Scenario & $K$ & $\rho$ & $\beta$ & Horizon & Certified & 95\% interval\\\midrule\endhead'+'\n'+'\n'.join(lines)+r'\bottomrule\end{longtable}\normalsize')
# Copy only selected numerical evidence, never historical studies.
(P/'audits/figure_table_sources.json').write_text(json.dumps([{'path':str(f.relative_to(R)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in dict.fromkeys(SOURCES)],indent=2))
print('Rendered 3 vector figures and 4 tables from stored evidence.')
