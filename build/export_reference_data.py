"""Export human-readable golden references from the packaged numerical data.

No PYNQ import or hardware access occurs. Board references are regenerated
software expectations, while board timing/check summaries come from saved logs.
"""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,re
import numpy as np

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump_csv(path,header,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(header);count=0
  for row in rows:w.writerow(row);count+=1
 return count
def load_json(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def bf16(x):
 bits=np.asarray(x,dtype=np.float32).view(np.uint32)
 return ((bits+np.uint32(0x7fff)+((bits>>16)&1))>>16).astype(np.uint16)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args();root=args.root.resolve();data=root/'data';records=[]
 def record(path,count,sources,kind='golden_reference'):
  records.append({'path':path.relative_to(root).as_posix(),'rows':count,'kind':kind,'sha256':digest(path),'sources':[p.relative_to(root).as_posix() for p in sources]})
 d=data/'int8';out=d/'reference'
 p=d/'softmax_cases.json';cases=load_json(p)
 path=out/'softmax_reference.csv'
 n=dump_csv(path,['case_id','index','input_code','input_scale','output_scale','floating_reference','baseline_format_reference_code','iscas_reference_code'],((c['id'],i,c['input_codes'][i],c['scale_in'],c['scale_out'],float(c['float_reference'][i]),c['baseline_format_codes'][i],c['python_codes'][i]) for c in cases for i in range(c['n'])))
 record(path,n,[p])
 p=d/'gelu_cases.json';cases=load_json(p);path=out/'gelu_reference.csv'
 def gelu_rows():
  for c in cases:
   for i,code in enumerate(c['input_codes']):
    x=code/(2**c['scale']);f=.5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+.044715*x**3)))
    yield c['id'],i,c['scale'],code,float(f),c['python_codes'][i],c['python_codes'][i]/(2**c['scale'])
 n=dump_csv(path,['case_id','index','fraction_bits','input_code','floating_reference','expected_code','expected_value'],gelu_rows());record(path,n,[p])
 p=d/'mm_reference.npz';case_path=d/'mm_cases.json';refs=np.load(p);cases=load_json(case_path);path=out/'gemm_reference.csv'
 n=dump_csv(path,['case_id','row','column','floating_reference','quantized_reference','expected_code'],((c['id'],i,j,float(refs[f"F_{c['id']}"][i,j]),float(refs[f"Q_{c['id']}"][i,j]),int(refs[f"codes_{c['id']}"][i,j])) for c in cases for i in range(c['m']) for j in range(c['n'])))
 record(path,n,[p,case_path])

 d=data/'bf16';p=d/'reference_data.npz';refs=np.load(p)
 names={0:'softmax',1:'layernorm',2:'rmsnorm',3:'silu',4:'gelu'}
 for op,name in names.items():
  f=refs[f'fp64_op{op}'];q=refs[f'qref_op{op}'];codes=bf16(q);path=d/'reference'/('standalone_'+name+'.csv')
  n=dump_csv(path,['case_id','index','floating_reference','bf16_reference','expected_bf16_hex'],((c,i,float(f[c,i]),float(q[c,i]),f'{int(codes[c,i]):04x}') for c in range(f.shape[0]) for i in range(f.shape[1])))
  record(path,n,[p])
 p=d/'integrated/references.npz';refs=np.load(p);ops=load_json(d/'integrated/ops.json')
 for key,name in ops.items():
  f=refs['F_'+key];q=refs['Q_'+key];codes=bf16(q);path=d/'reference'/('pipeline_'+name+'.csv')
  n=dump_csv(path,['case_id','row','column','floating_reference','bf16_reference','expected_bf16_hex'],((c,i,j,float(f[c,i,j]),float(q[c,i,j]),f'{int(codes[c,i,j]):04x}') for c in range(f.shape[0]) for i in range(f.shape[1]) for j in range(f.shape[2])))
  record(path,n,[p])

 # Importing these CPU helpers does not call main() or import PYNQ.
 source=root/'src/bf16/ps/bench_snake_report.py';spec=importlib.util.spec_from_file_location('bench_reference',source);bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
 a,b=bench.make_inputs();a_cpu=bench.bf16_to_f32(a);b_cpu=bench.bf16_to_f32(b)
 rng=np.random.default_rng(bench.SEED+1);up=np.zeros((bench.K,bench.N),dtype=np.float32);up[:,:bench.ACTIVE_N]=rng.uniform(-.2,.3,(bench.K,bench.ACTIVE_N));up=bench.f32_to_bf16(up)
 gamma=bench.f32_to_bf16(rng.uniform(.75,1.25,bench.N));beta=bench.f32_to_bf16(rng.uniform(-.1,.1,bench.N));mask=np.zeros(bench.N,dtype=bool);mask[:bench.ACTIVE_N]=True;mask[:bench.ACTIVE_N:5]=False
 d=data/'board/bf16';d.mkdir(parents=True,exist_ok=True)
 np.savez(d/'inputs.npz',a_bf16=a,b_bf16=b,w_up_bf16=up,gamma_bf16=gamma,beta_bf16=beta,mask=mask)
 expected={}
 for op in bench.OPS:
  if op<8:out=bench.cpu_pipeline(op,a_cpu,b_cpu)
  else:out=bench.cpu_extended_pipeline(op,a_cpu,b_cpu,bench.bf16_to_f32(up),bench.bf16_to_f32(gamma),bench.bf16_to_f32(beta),mask)
  expected['op_'+str(op)]=out;codes=bench.f32_to_bf16(out);path=d/f'expected_op_{op}.csv'
  n=dump_csv(path,['row','column','expected_value','expected_bf16_hex'],((i,j,float(out[i,j]),f'{int(codes[i,j]):04x}') for i in range(out.shape[0]) for j in range(out.shape[1])))
  record(path,n,[source],'regenerated_board_software_reference')
 np.savez(d/'references.npz',**expected)
 log=root/'board/bf16/results/bench_log.txt';s=log.read_text(encoding='utf-8')
 for label,words in [('A',a),('B',b)]:
  m=re.search(label+r" first values: (\[[^\n]+\])",s);assert m
  listed=re.findall(r"'([0-9A-Fa-f]{4})'",m.group(1));assert [f'{int(v):04X}' for v in words.flat[:len(listed)]]==[x.upper() for x in listed]
 summary=s.split('[6] Summary and interpretation',1)[1];measured=[]
 for line in summary.splitlines():
  m=re.match(r'\s+(.+?)\s+(PASS|FAIL)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)x\s*$',line)
  if m:measured.append(m.groups())
 assert len(measured)==10
 path=d/'bench_summary.csv';n=dump_csv(path,['operation','check','cpu_mean_us','fpga_mean_us','cpu_fpga_ratio'],measured);record(path,n,[log],'measured_summary_from_existing_board_log')
 info={'evidence_kind':'regenerated_software_inputs_and_reference_plus_existing_measured_summary','seed':bench.SEED,'m':bench.M,'k':bench.K,'n':bench.N,'active_n':bench.ACTIVE_N,'hardware_executed_by_export':False,'input_prefixes_match_saved_log':True,'board_log_sha256':digest(log),'reference_script_sha256':digest(source),'latency_scope':'Same-board ARM NumPy vs FPGA; repeated runs exclude A/B upload and include result DMA. Not full-model speedup.','actual_full_output_arrays_available':False,'note':'Expected CSV/NPZ values are software references regenerated from the saved benchmark code. They are not newly captured FPGA outputs.'}
 (d/'metadata.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
 (data/'reference_catalog.json').write_text(json.dumps({'schema_version':1,'references':records,'images':'picture/index.html','actual_rtl_outputs':['sim/int8/operator_validation/raw','sim/bf16/operator_validation/results'],'no_new_physical_board_test':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Exported numerical references:',len(records),'CSVs;',sum(x['rows'] for x in records),'rows')

if __name__=='__main__':main()
