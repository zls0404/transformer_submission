"""Measured INT8 captures; figures retain the original coordinates and all cases."""
from pathlib import Path
import sys,os,csv,json,math
import numpy as np
R=Path(__file__).resolve().parents[4];T=R/'sim/int8/operator_validation';O=R/'picture/int8';D=R/'data/int8'
O.mkdir(parents=True,exist_ok=True);(O/'preview').mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR']=str(T/'build/mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,AutoMinorLocator,ScalarFormatter
from matplotlib.font_manager import fontManager
font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/times.ttf'
if font_path.is_file():
    fontManager.addfont(str(font_path))
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':11,'axes.labelsize':11,'axes.titlesize':11.5,'axes.linewidth':.7,'xtick.labelsize':10,'ytick.labelsize':10,'xtick.direction':'in','ytick.direction':'in','xtick.major.width':.65,'ytick.major.width':.65,'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,'mathtext.fontset':'stix','svg.fonttype':'none','pdf.fonttype':42,'savefig.facecolor':'white'})
GRAY='#34383d';BLUE='#0072B2';ORANGE='#D55E00';RED='#a52231'
def rows(p):
 with p.open(encoding='utf-8-sig') as f:return [{k:v.strip() for k,v in r.items()} for r in csv.DictReader(f)]
def writecsv(p,rr):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def metric(a,b):return float(np.mean(np.abs(a-b)))
def extend(g,F,Q,A):
 for name,a,b in [('q_f',Q,F),('r_f',A,F),('r_q',A,Q)]:
  delta=np.asarray(a)-np.asarray(b);den=float(np.linalg.norm(b));num=float(np.linalg.norm(delta))
  g[name+'_rmse']=float(np.sqrt(np.mean(delta*delta)))
  g[name+'_max_abs']=float(np.max(np.abs(delta)))
  g[name+'_relative_l2']=num/den if den else (0.0 if num==0 else float('inf'))
 return g
def traces(ax,x,F,Q,A,local=False,qlabel='Python fixed-point reference (Q)'):
 h=[]
 h+=ax.plot(x,F,color=GRAY,lw=1.3,marker='^' if local else None,ms=4.7,label='Floating-point reference (F)',zorder=3)
 h+=ax.plot(x,Q,color=BLUE,lw=2 if local else 1.4,ls=(0,(5,2.5)),marker='s' if local else None,ms=6.2,mfc='white',mew=1.2,label=qlabel,zorder=4)
 h+=ax.plot(x,A,color=ORANGE,lw=1.1,ls=(0,(1,2)),marker='o' if local else None,ms=3.8,mfc='white',mew=1.05,label='Measured RTL output (R)',zorder=5)
 return h
def draw(stem,title,Fs,Qs,As,gs,case=6,s=8,e=15,qlabel='Python fixed-point reference (Q)',note=''):
 F,Q,A=Fs[case],Qs[case],As[case];x=np.arange(len(F));e=min(e,len(F));s=min(s,e-2)
 finite=[i for i,(f,q,a) in enumerate(zip(Fs,Qs,As)) if np.isfinite(a).all() and a.shape==q.shape]
 if finite:
  ff=np.concatenate([Fs[i] for i in finite]);qq=np.concatenate([Qs[i] for i in finite]);aa=np.concatenate([As[i] for i in finite]);pair=[metric(qq,ff),metric(aa,ff),metric(aa,qq)]
 else:pair=[float('nan')]*3
 fig,axs=plt.subplots(2,2,figsize=(10.8,6.75));fig.subplots_adjust(left=.092,right=.985,bottom=.13,top=.835,wspace=.32,hspace=.65)
 fig.suptitle(title,fontsize=16,y=.994)
 for ax in axs.flat:
  ax.grid(axis='y',color='#e2e5e9',lw=.55);ax.set_axisbelow(True)
  f=ScalarFormatter(useMathText=True,useOffset=False);f.set_powerlimits((-3,3));ax.yaxis.set_major_formatter(f)
  ax.yaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_minor_locator(AutoMinorLocator(2))
 ax=axs[0,0];h=traces(ax,x,F,Q,A,qlabel=qlabel);ax.set_xlim(0,len(F)-1);ax.set_title('(a) Full-vector comparison',loc='left',pad=9);ax.set_xlabel('Element index');ax.set_ylabel('Output value')
 vals=np.r_[F,Q,A];lo=np.nanmin(vals);hi=np.nanmax(vals);span=max(hi-lo,1e-10);ax.set_ylim(lo-.07*span,hi+.10*span);ax.axvspan(s-.5,e-.5,color='#f4ddc6',alpha=.7,zorder=1)
 ax.annotate('Detail in (b)',xy=((s+e-1)/2,float(F[s])),xytext=(.54,.78),textcoords='axes fraction',fontsize=9.5,color='#555',arrowprops={'arrowstyle':'-','lw':.65,'color':'#888'})
 fig.legend(h,[a.get_label() for a in h],loc='upper center',bbox_to_anchor=(.54,.953),ncol=3,fontsize=9.7,columnspacing=1.3,handlelength=2.7)
 ax=axs[0,1];local=np.stack([F[s:e],Q[s:e],A[s:e]]);xx=x[s:e];traces(ax,xx,*local,local=True,qlabel=qlabel)
 d=max(np.nanmax(local)-np.nanmin(local),1e-10);ax.set_ylim(np.nanmin(local)-.14*d,np.nanmax(local)+.24*d);ax.set_xlim(s-.18,e-1+.18);ax.set_xticks(xx);ax.set_xlabel('Element index');ax.set_ylabel('Output value');ax.set_title('(b) Local magnification',loc='left',pad=9)
 eq=np.array_equal(local[1],local[2]);ax.text(.025,.94,'Q and R coincide in this window' if eq else f'max |R − Q| = {np.nanmax(np.abs(local[2]-local[1])):.3g}',transform=ax.transAxes,va='top',fontsize=9.3,color='#555')
 ax=axs[1,0];bs=ax.bar(range(3),pair,width=.48,color=[GRAY,BLUE,ORANGE],alpha=.92,zorder=3);top=max(np.nanmax(pair)*1.4,1e-8);ax.set_ylim(0,top)
 for b,v in zip(bs,pair):
  ax.annotate('0' if v==0 else f'{v:.3g}',(b.get_x()+b.get_width()/2,v),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
  if v==0:ax.plot(b.get_x()+b.get_width()/2,0,marker='_',ms=17,color=b.get_facecolor(),clip_on=False)
 ax.set_xticks(range(3),['Q − F','R − F','R − Q']);ax.set_ylabel('Mean absolute error');ax.set_title('(c) Aggregate error',loc='left',pad=9)
 ax.text(.98,.94,f'{len(finite)}/{len(gs)} finite cases',transform=ax.transAxes,ha='right',va='top',fontsize=9.3,color='#555')
 ax=axs[1,1];ys=np.array([g['r_q_mae'] for g in gs]);valid=np.isfinite(ys);top=max(np.max(ys[valid])*1.45 if valid.any() else 0,1e-7)
 ax.plot(np.arange(len(gs))[valid]+1,ys[valid],ls='none',marker='o',ms=3.9,color=BLUE,zorder=3);ax.set_ylim(-.07*top,top);ax.set_xlim(.25,len(gs)+.75);ax.xaxis.set_major_locator(MaxNLocator(7,integer=True));ax.set_title('(d) Error across all cases',loc='left',pad=9);ax.set_xlabel('Test case');ax.set_ylabel('RTL–Python MAE')
 for i,g in enumerate(gs):
  if not valid[i]:ax.plot(i+1,.82*top,marker='x',color=RED,ms=7)
  elif not g['check_ok']:ax.plot(i+1,ys[i],marker='o',mfc='none',mec=RED,ms=7.3,mew=1.1,zorder=4)
 fig.text(.092,.045,note,fontsize=8.7,color='#4b5056');fig.text(.092,.019,'No vertical offsets. Red markers retain failed checks; all timing values are reported in tables.',fontsize=8.7,color='#4b5056')
 for ext in ['png','svg','pdf']:fig.savefig(O/f'{stem}.{ext}',dpi=400,metadata={'Date':None} if ext=='svg' else None)
 fig.savefig(O/'preview'/f'{stem}.png',dpi=150);plt.close(fig)
 return dict(stem=stem,title=title,cases=len(gs),finite_cases=len(finite),aggregate_mae=pair,example_case=case+1,zoom_indices=list(range(s,e)),zoom_f=local[0].tolist(),zoom_q=local[1].tolist(),zoom_r=local[2].tolist(),reference=qlabel)
details=[];allmetrics=[];samples=rows(T/'raw/rtl_samples.csv');ss=rows(T/'raw/rtl_summary.csv');cases=json.loads((D/'softmax_cases.json').read_text())
for name,title in [('baseline','INT8 Softmax · deployed baseline'),('serial','INT8 Softmax · ISCAS serial candidate'),('parallel','INT8 Softmax · ISCAS parallel candidate')]:
 Fs=[];Qs=[];As=[];gs=[]
 for c in cases:
  cid=c['id'];rr=[x for x in samples if x['module']==name and int(x['case_id'])==cid];summary=next(x for x in ss if x['module']==name and int(x['case_id'])==cid)
  f=np.array(c['float_reference']);q=np.array(c['baseline_format_codes'] if name=='baseline' else c['python_codes'])/128;a=np.array([int(x['actual_code']) for x in rr])/128
  protocol=int(summary['output_count'])==c['n'] and int(summary['protocol_errors'])==0 and int(summary['unknowns'])==0 and int(summary['last_count'])==1
  ok=protocol and (name=='baseline' or np.array_equal(q,a))
  g=dict(operator=name,case_id=cid,n=c['n'],protocol_ok=protocol,code_mismatches=int(summary['code_mismatches']),check_ok=ok,q_f_mae=metric(q,f),r_f_mae=metric(a,f),r_q_mae=metric(a,q),first_ns=int(summary['first_ns']),completion_ns=int(summary['completion_ns']))
  Fs.append(f);Qs.append(q);As.append(a);gs.append(g);allmetrics.append(extend(g,f,q,a))
 qlabel='Python INT8 format reference (Q)' if name=='baseline' else 'Python fixed-point reference (Q)'
 note='100 predeclared cases · input Q6 / output Q7 · example #7 · baseline Q is a format target, not a bit-accurate model.' if name=='baseline' else '100 predeclared cases · 14,720 elements · input Q6 / output Q7 · example #7 · candidate implementation.'
 details.append(draw('softmax_'+name,title,Fs,Qs,As,gs,qlabel=qlabel,note=note))
# Exhaustive scalar GELU sweeps.
gc=json.loads((D/'gelu_cases.json').read_text());gr=rows(T/'raw/gelu_samples.csv');summ=rows(T/'raw/gelu_summary.csv');Fs=[];Qs=[];As=[];gs=[]
for c,su in zip(gc,summ):
 scale=c['scale'];x=np.array(c['input_codes'])/2**scale;f=.5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+.044715*x**3)));q=np.array(c['python_codes'])/2**scale
 rr=[r for r in gr if int(r['case_id'])==c['id']];a=np.array([int(r['actual_code']) for r in rr])/2**scale
 ok=len(rr)==256 and int(su['unknowns'])==0 and np.array_equal(q,a)
 g=dict(operator='gelu',case_id=c['id'],n=256,protocol_ok=len(rr)==256 and int(su['unknowns'])==0,code_mismatches=int(su['code_mismatches']),check_ok=ok,q_f_mae=metric(q,f),r_f_mae=metric(a,f),r_q_mae=metric(a,q),first_ns=10*int(su['first_cycles']),completion_ns=10*int(su['completion_cycles']))
 Fs.append(f);Qs.append(q);As.append(a);gs.append(g);allmetrics.append(extend(g,f,q,a))
details.append(draw('gelu','INT8 GELU · scalar datapath',Fs,Qs,As,gs,case=6,s=128,e=135,note='15 exhaustive scale sweeps (Q0–Q14) · 3,840 elements · example Q6 · SIMD backpressure is a separate check.'))
# MM measured beat decoding; unknown values remain NaN and fail the checks.
mc=json.loads((D/'mm_cases.json').read_text());mr=rows(T/'raw/mm_samples.csv');ms=rows(T/'raw/mm_summary.csv');ref=np.load(D/'mm_reference.npz');Fs=[];Qs=[];As=[];gs=[]
for c,su in zip(mc,ms):
 cid=c['id'];rr=[r for r in mr if int(r['case_id'])==cid];a=[]
 for r in rr:
  h=r['data_hex']
  for lane in range(16):
   hh=h[len(h)-2*(lane+1):len(h)-2*lane]
   try:v=int(hh,16);a.append((v-256 if v>=128 else v)/16)
   except ValueError:a.append(float('nan'))
 f=ref[f'F_{cid}'].ravel();q=ref[f'Q_{cid}'].ravel();a=np.array(a)
 sizeok=len(a)==len(q)
 if not sizeok:a=np.full(q.shape,np.nan)
 ok=sizeok and np.isfinite(a).all() and np.array_equal(q,a) and int(su['last_count'])==1 and int(su['hold_errors'])==0 and int(su['timeout'])==0
 g=dict(operator='gemm',case_id=cid,n=len(q),protocol_ok=sizeok and int(su['last_count'])==1 and int(su['hold_errors'])==0,code_mismatches=int(np.count_nonzero(a!=q)),check_ok=bool(ok),q_f_mae=metric(q,f),r_f_mae=metric(a,f),r_q_mae=metric(a,q),first_ns=10*int(su['first_cycles']) if int(su['first_cycles'])>=0 else '',completion_ns=10*int(su['completion_cycles']) if int(su['completion_cycles'])>=0 else '')
 Fs.append(f);Qs.append(q);As.append(a);gs.append(g);allmetrics.append(extend(g,f,q,a))
if np.isfinite(As[4]).all():
 # Plot every matrix element; the zoom uses a predeclared window.
 details.append(draw('gemm','INT8 GEMM · integer matrix multiplication',Fs,Qs,As,gs,case=4,note='16 cases · input Q4 / output Q4 · example #5: M=16 / K=32 / N=32 · cases 9–16 include stalls.'))
writecsv(T/'report/case_metrics.csv',allmetrics)
(O/'figure_data.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
stats=[]
for op in ['baseline','serial','parallel','gelu','gemm']:
 gg=[g for g in allmetrics if g['operator']==op];stats.append(dict(operator=op,total=len(gg),check_basis='framing only; accuracy not graded' if op=='baseline' else 'bit equality and recorded protocol checks',passed=sum(g['check_ok'] for g in gg),failed=sum(not g['check_ok'] for g in gg),elements=sum(g['n'] for g in gg)))
(T/'report/summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
cards=''.join(f'<section><h2>{d["title"]}</h2><a href="{d["stem"]}.png"><img src="preview/{d["stem"]}.png"></a><p><a href="{d["stem"]}.png">PNG 400 dpi</a> · <a href="{d["stem"]}.svg">SVG</a> · <a href="{d["stem"]}.pdf">PDF</a></p></section>' for d in details)
(O/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>INT8 算子测试</title><style>body{max-width:1200px;margin:40px auto;font:16px Microsoft YaHei;color:#222}img{width:100%}section{margin:50px 0}a{color:#0072b2}</style><h1>INT8 算子测试</h1><p>原值折线、局部放大和全量误差。三条曲线重合时保留原坐标；延时见测试报告。baseline 是当前 Z2 工程使用的 Softmax，ISCAS 两种实现只作为候选版本比较。</p>'+cards,encoding='utf-8')
print(json.dumps(stats,ensure_ascii=False));print('Figures:',len(details))
