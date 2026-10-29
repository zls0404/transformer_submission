"""Publication-style scientific figures from measured RTL samples only."""
from pathlib import Path
import os,csv,json,hashlib,sys
import numpy as np
R=Path(__file__).resolve().parents[1];O=R.parents[2]/'picture/bf16';O.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(R/'build/mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,AutoMinorLocator,ScalarFormatter
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.patches import Rectangle
from analyze_results import readcsv,metrics
from reference import from_bf16
font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/times.ttf'
if font_path.is_file():
    fontManager.addfont(str(font_path))
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':11,'axes.labelsize':11,'axes.titlesize':11.5,
 'axes.linewidth':.7,'xtick.labelsize':10,'ytick.labelsize':10,'xtick.direction':'in','ytick.direction':'in',
 'xtick.major.width':.65,'ytick.major.width':.65,'axes.spines.top':False,'axes.spines.right':False,
 'legend.frameon':False,'mathtext.fontset':'stix','svg.fonttype':'none','pdf.fonttype':42,'savefig.facecolor':'white'})
GRAY='#34383d';BLUE='#0072B2';ORANGE='#D55E00';RED='#a52231'
TITLES={'softmax':'Softmax','layernorm':'LayerNorm','rmsnorm':'RMSNorm','silu':'SiLU','gelu':'Sigmoid GELU',
 'gemm':'GEMM','layernorm_affine':'LayerNorm affine','rmsnorm_affine':'RMSNorm affine','masked_softmax':'Masked Softmax','swiglu':'SwiGLU'}
def sci(ax):
 f=ScalarFormatter(useMathText=True,useOffset=False);f.set_powerlimits((-3,3));ax.yaxis.set_major_formatter(f)
 ax.yaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_minor_locator(AutoMinorLocator(2))
def traces(ax,x,F,Q,A,local=False):
 h=[]
 h+=ax.plot(x,F,color=GRAY,lw=1.3,marker='^' if local else None,ms=4.7,label='Floating-point reference (F)',zorder=3)
 h+=ax.plot(x,Q,color=BLUE,lw=2 if local else 1.4,ls=(0,(5,2.5)),marker='s' if local else None,
  ms=6.2,mfc='white',mew=1.2,label='Python BF16 reference (Q)',zorder=4)
 h+=ax.plot(x,A,color=ORANGE,lw=1.1,ls=(0,(1,2)),marker='o' if local else None,
  ms=3.8,mfc='white',mew=1.05,label='RTL BF16 output (R)',zorder=5)
 return h
def draw(name,F,Q,A,groups,nominal,title_prefix,stem):
 # Predeclared positive ramp, no RTL-error-based case or window selection.
 case=6 if title_prefix=='Standalone' else 2
 s,e=(701,705) if name=='masked_softmax' else (704,711)
 assert A.shape==F.shape==Q.shape
 x=np.arange(768);finite=np.isfinite(A).all(axis=1)
 common=[i for i in nominal if finite[i]]
 pair=[metrics(Q[common].ravel(),F[common].ravel())['mae'],metrics(A[common].ravel(),F[common].ravel())['mae'],metrics(A[common].ravel(),Q[common].ravel())['mae']]
 fig,axs=plt.subplots(2,2,figsize=(10.8,6.75))
 fig.subplots_adjust(left=.092,right=.985,bottom=.13,top=.835,wspace=.32,hspace=.65)
 fig.suptitle(TITLES[name],fontsize=16,y=.994)
 for ax in axs.flat:
  ax.grid(axis='y',color='#e2e5e9',lw=.55);ax.set_axisbelow(True);sci(ax)
 ax=axs[0,0];handles=traces(ax,x,F[case],Q[case],A[case]);ax.set_xlim(0,767)
 ax.set_title('(a) Full-vector comparison',loc='left',pad=9)
 ax.set_xlabel('Element index');ax.set_ylabel('Output value')
 allvals=np.r_[F[case],Q[case],A[case]];lo=np.nanmin(allvals);hi=np.nanmax(allvals);span=max(hi-lo,1e-12)
 ax.set_ylim(lo-.07*span,hi+.10*span)
 ax.axvspan(s-.5,e-.5,color='#f4ddc6',alpha=.7,zorder=1)
 ax.annotate('Detail in (b)',xy=((s+e-1)/2,float(F[case,s])),xytext=(.47,.78),textcoords='axes fraction',
   fontsize=9.5,color='#555',arrowprops={'arrowstyle':'-','lw':.65,'color':'#888'})
 fig.legend(handles,[h.get_label() for h in handles],loc='upper center',bbox_to_anchor=(.54,.953),ncol=3,
  fontsize=10.5,columnspacing=1.7,handlelength=2.7)
 ax=axs[0,1];xx=x[s:e];local=np.stack([F[case,s:e],Q[case,s:e],A[case,s:e]])
 traces(ax,xx,*local,local=True)
 ax.set_xlim(s-.18,e-1+.18);ax.set_xticks(xx)
 delta=max(np.nanmax(local)-np.nanmin(local),1e-12)
 ax.set_ylim(np.nanmin(local)-.14*delta,np.nanmax(local)+.24*delta)
 ax.set_title('(b) Local magnification',loc='left',pad=9)
 ax.set_xlabel('Element index');ax.set_ylabel('Output value')
 if np.array_equal(local[1],local[2]):
  ax.text(.025,.94,'Q and R coincide in this window',transform=ax.transAxes,va='top',fontsize=9.3,color='#555')
 else:
  ax.text(.025,.94,f'max |R − Q| = {np.nanmax(np.abs(local[2]-local[1])):.3g}',transform=ax.transAxes,va='top',fontsize=9.3,color='#555')
 # Honest common finite subset; never treat NaN as zero.
 ax=axs[1,0];bars=ax.bar(np.arange(3),pair,width=.48,color=[GRAY,BLUE,ORANGE],alpha=.92,zorder=3)
 top=max(max(pair)*1.4,1e-12);ax.set_ylim(0,top)
 for b,v in zip(bars,pair):
  ax.annotate('0' if v==0 else f'{v:.3g}',(b.get_x()+b.get_width()/2,v),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
  if v==0:ax.plot(b.get_x()+b.get_width()/2,0,marker='_',ms=17,color=b.get_facecolor(),clip_on=False)
 ax.set_xticks(np.arange(3),['Q − F','R − F','R − Q']);ax.set_ylabel('Mean absolute error')
 ax.set_title('(c) Aggregate error',loc='left',pad=9)
 ax.text(.98,.94,f'{len(common)}/{len(nominal)} finite nominal cases',transform=ax.transAxes,ha='right',va='top',fontsize=9.3,color='#555')
 ax=axs[1,1];ys=np.array([float(g['R_Q_mae']) for g in groups]);valid=np.isfinite(ys)
 ax.plot(np.arange(len(groups))[valid]+1,ys[valid],ls='none',marker='o',ms=3.9,color=BLUE,zorder=3)
 top=max(np.max(ys[valid])*1.45 if valid.any() else 0,1e-7);ax.set_ylim(-.07*top,top)
 ax.set_xlim(.25,len(groups)+.75);ax.xaxis.set_major_locator(MaxNLocator(7,integer=True))
 ax.set_xlabel('Test case');ax.set_ylabel('RTL–Python MAE');ax.set_title('(d) Error across all cases',loc='left',pad=9)
 probes=[i for i,g in enumerate(groups) if g['category']!='nominal']
 if probes:ax.axvspan(min(probes)+.5,len(groups)+.5,color='#f0f2f4',zorder=0)
 failed=0
 for i,g in enumerate(groups):
  ok=str(g.get('case_ok','')).lower()=='true'
  if not ok:failed+=1
  if not valid[i]:
   ax.plot(i+1,.86*top,marker='x',color=RED,ms=6,mew=1.2)
   label='NaN' if str(g.get('finite','')).lower()=='false' else 'invalid frame'
   right=i>=.75*len(groups)
   ax.annotate(label,(i+1,.86*top),xytext=(-5 if right else 5,-13),ha='right' if right else 'left',textcoords='offset points',fontsize=8.7,color=RED)
  elif not ok:ax.plot(i+1,ys[i],marker='o',mfc='none',mec=RED,ms=7.3,mew=1.1,zorder=4)
 fig.text(.092,.045,f'{title_prefix} · N = 768 · ramp example #{case+1} · shaded cases: probes · red markers: failed checks',fontsize=9,color='#4b5056')
 missing=len(nominal)-len(common)
 note=f'All-case RTL MAE is undefined ({missing} nonfinite nominal case'+('s).' if missing!=1 else ').') if missing else 'All nominal cases are finite; zero RTL–Python error means numerical equality for those samples.'
 fig.text(.092,.019,note,fontsize=8.7,color='#4b5056')
 paths={}
 for ext in ['png','svg','pdf']:
  p=O/(stem+'.'+ext);fig.savefig(p,dpi=400,metadata={'Date':None} if ext=='svg' else None);paths[ext]=p.name
 preview=O/'preview';preview.mkdir(exist_ok=True);fig.savefig(preview/(stem+'.png'),dpi=150)
 plt.close(fig)
 return dict(operator=name,title=TITLES[name],stage=title_prefix,nominal_cases=len(nominal),common_finite_cases=len(common),
  aggregate_mae=pair,failed_cases=failed,example_case=case,zoom_indices=list(range(s,e)),zoom_F=local[0].tolist(),
  zoom_Q=local[1].tolist(),zoom_R=local[2].tolist(),**paths)
def main():
 details=[];base=np.load(R.parents[2]/'data/bf16/reference_data.npz');ms=readcsv(R/'report/case_metrics.csv')
 for op,name in enumerate(['softmax','layernorm','rmsnorm','silu','gelu']):
  groups=[g for g in ms if int(g['op'])==op];A=np.full((26,768),np.nan)
  for tc in range(26):
   rr=[g for g in readcsv(R/f'results/{name}/rtl_samples.csv') if int(g['case_id'])==tc]
   if [int(g['beat'])*4+int(g['lane']) for g in rr]==list(range(768)):
    try:A[tc]=from_bf16([int(g['bf16_hex'],16) for g in rr])
    except ValueError:pass
  details.append(draw(name,base[f'fp64_op{op}'],base[f'qref_op{op}'].astype(float),A,groups,list(range(24)),'Standalone','standalone_'+name))
 if (R/'report/integrated_case_metrics.csv').exists():
  refs=np.load(R.parents[2]/'data/bf16/integrated/references.npz');actual=np.load(R/'report/integrated_captures.npz');gs=readcsv(R/'report/integrated_case_metrics.csv')
  for op,name in json.loads((R.parents[2]/'data/bf16/integrated/ops.json').read_text()).items():
   groups=[g for g in gs if int(g['op'])==int(op) and int(g['rows'])==1]
   if len(groups)!=6:continue
   A=np.stack([actual[f'R_{op}_1_{i}'][0] for i in range(6)])
   details.append(draw(name,refs[f'F_{op}'][:,0],refs[f'Q_{op}'][:,0],A,groups,list(range(4)),'GEMM + operator' if op!='7' else 'GEMM','pipeline_'+name))
 (O/'figure_data.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
 cards=''.join(f'<section><h2>{d["stage"]} / {d["title"]}</h2><a href="{d["png"]}"><img src="preview/{d["png"]}"></a><p><a href="{d["svg"]}">SVG</a> · <a href="{d["pdf"]}">PDF</a> · <a href="{d["png"]}">400 dpi PNG</a></p></section>' for d in details)
 (O/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>BF16算子验证图表</title><style>body{max-width:1200px;margin:40px auto;font:16px Microsoft YaHei;color:#222}img{width:100%}section{margin:50px 0}a{color:#0072b2}</style><h1>BF16 算子三值比较与精度验证</h1><p>三条原值折线与局部放大；所有延时仅列于测试说明。红色标记保留异常，完整原始记录见results。论文式排版参考SoftEx（arXiv:2412.06321）的简洁子图、统一图例与细轴线，图中数据均为本工程实测，不引用论文实验结果。</p>'+cards,encoding='utf-8')
 print('Generated',len(details),'figures')
if __name__=='__main__':main()
