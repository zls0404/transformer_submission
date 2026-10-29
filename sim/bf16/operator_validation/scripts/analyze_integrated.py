from pathlib import Path
import csv,json,numpy as np
from reference import to_bf16,from_bf16
from analyze_results import metrics,readcsv,writecsv
R=Path(__file__).resolve().parents[1];D=R.parents[2]/'data/bf16/integrated';P=R/'report'
refs=np.load(D/'references.npz');ops=json.loads((D/'ops.json').read_text());cases=json.loads((D/'cases.json').read_text())
rows=[];evidence={};missing=[]
for op_s,name in ops.items():
 op=int(op_s)
 for M in [1,4]:
  path=R/'results'/('integrated_'+name+('_m4' if M==4 else ''))
  if not (path/'summary.csv').exists():
   if M==1 or op in [7,0,8,11]:missing.append(path.name)
   continue
  summaries=readcsv(path/'summary.csv');raw=readcsv(path/'samples.csv');mm=readcsv(path/'mm_samples.csv')
  expected_cases=list(range(6)) if M==1 else [3]
  if [int(s['case_id']) for s in summaries]!=expected_cases:missing.append(path.name+':incomplete')
  for s in summaries:
   tc=int(s['case_id']);samples=[p for p in raw if int(p['case_id'])==tc]
   ordered=[int(p['beat'])*4+int(p['lane']) for p in samples]==list(range(M*768))
   arr=np.full(M*768,np.nan)
   if ordered:
    for j,p in enumerate(samples):
     try:arr[j]=float(from_bf16([int(p['bf16_hex'],16)])[0])
     except ValueError:pass
   arr=arr.reshape(M,768);F=refs[f'F_{op}'][tc,:M];Q=refs[f'Q_{op}'][tc,:M]
   numerical=metrics(arr,Q);finite=bool(np.isfinite(arr).all() and ordered)
   numeric_ok=finite and (numerical['relative_l2']<=.05 if np.linalg.norm(Q)>1e-12 else numerical['max_abs']<=.002)
   flags=['tl_errors','stall_errors','unknowns','fifo1','fifo2','error','timeout','load_timeout','premature']
   mmcase=[p for p in mm if int(p['case_id'])==tc]
   expected_order=[(row,proj,j) for row in range(M) for proj in range(2 if op==11 else 1) for j in range(768)]
   mm_order=[(int(p['row']),int(p['projection']),int(p['index'])) for p in mmcase]
   mm_round_ok=True
   for p in mmcase:
    try:
     fp=np.array([int(p['fp32_hex'],16)],dtype=np.uint32).view(np.float32)
     if int(to_bf16(fp)[0])!=int(p['bf16_hex'],16) or not np.isfinite(fp).all():mm_round_ok=False
    except ValueError:mm_round_ok=False
   protocol=ordered and all(int(s[k])==0 for k in flags) and mm_order==expected_order and int(s['done'])>=0
   invariant=finite
   if finite and op in [0,10]:
    invariant=bool(arr.min()>=0 and arr.max()<=1 and np.max(np.abs(arr.sum(axis=1)-1))<=.02)
    if op==10:invariant=invariant and bool(np.max(np.abs(arr[:,~refs['mask']]))<=.002)
   row=dict(op=op,operator=name,rows=M,case_id=tc,name=cases[tc]['name'],category=cases[tc]['category'],
     output_beats=int(s['out_beats']),mm_beats=int(s['mm_beats']),protocol_ok=bool(protocol),finite=finite,
     mm_rounding_ok=mm_round_ok,numeric_ok=bool(numeric_ok),invariant_ok=bool(invariant),
     case_ok=bool(protocol and finite and mm_round_ok and numeric_ok and invariant),
     first_from_start_cycles=int(s['first_out'])-int(s['start']) if int(s['first_out'])>=0 else -1,
     last_from_start_cycles=int(s['last_out'])-int(s['start']) if int(s['last_out'])>=0 else -1,
     done_from_start_cycles=int(s['done'])-int(s['start']) if int(s['done'])>=0 else -1,
     last_from_first_input_cycles=int(s['last_out'])-int(s['first_a']) if int(s['first_a'])>=0 and int(s['last_out'])>=0 else -1,
     **{k:int(s[k]) for k in flags})
   for tag,a,b in [('Q_F',Q,F),('R_F',arr,F),('R_Q',arr,Q)]:row.update({tag+'_'+k:v for k,v in metrics(a,b).items()})
   rows.append(row);evidence[f'R_{op}_{M}_{tc}']=arr
   # Retain all positions, including NaNs; no slicing away faulty frames.
   out=path/f'three_values_case_{tc}.csv'
   with out.open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['row','index','F','Q','R'])
    for i in range(M):
     for j in range(768):w.writerow([i,j,F[i,j],Q[i,j],arr[i,j]])
writecsv(P/'integrated_case_metrics.csv',rows)
np.savez(P/'integrated_captures.npz',**evidence)
summary=[]
for op_s,name in ops.items():
 gs=[r for r in rows if r['op']==int(op_s) and r['rows']==1]
 summary.append(dict(op=int(op_s),operator=name,total=len(gs),passed=sum(r['case_ok'] for r in gs),
  nominal=sum(r['category']=='nominal' for r in gs),nominal_passed=sum(r['case_ok'] and r['category']=='nominal' for r in gs),
  protocol_passed=sum(r['protocol_ok'] for r in gs),nonfinite=sum(not r['finite'] for r in gs)))
writecsv(P/'integrated_summary.csv',summary)
(P/'integrated_analysis.json').write_text(json.dumps(dict(summary=summary,missing=missing),indent=2))
print(json.dumps(dict(summary=summary,missing=missing),indent=2))
if missing:raise SystemExit('Missing required captures')
