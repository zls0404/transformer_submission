from pathlib import Path
import os,json,subprocess,time,shutil,argparse,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
R=Path(__file__).resolve().parents[1];B=R/'build';L=R/'logs';D=R.parents[2]/'data/bf16/integrated'
ops=json.loads((D/'ops.json').read_text())
parser=argparse.ArgumentParser();parser.add_argument('--skip-compile',action='store_true');parser.add_argument('--vivado',default='D:/vivado/2026.1/Vivado');options=parser.parse_args()
B.mkdir(parents=True,exist_ok=True);L.mkdir(parents=True,exist_ok=True)
if not (B/'xsim.dir/operator_validation').is_dir():
 if options.skip_compile:raise SystemExit('Base library missing: run run_validation.py --compile-only first')
 subprocess.run([sys.executable,'-X','utf8',str(R/'scripts/run_validation.py'),'--vivado',options.vivado,'--compile-only'],check=True)
V=Path(options.vivado);env=os.environ.copy();env['XILINX_VIVADO']=str(V);env['PATH']=str(V/'bin')+os.pathsep+env.get('PATH','')
def tool(name,args,label,cwd=B):
 cmd=[(V/'bin'/(name+'.bat')).as_posix(),*[x.replace('\\','/') for x in args]]
 launcher=B/('launch_'+label+'.cmd')
 launcher.write_text('@echo off\ncall '+' '.join('"'+x+'"' for x in cmd)+'\nexit /b %errorlevel%\n',encoding='ascii')
 t=time.perf_counter()
 with (L/(label+'.log')).open('w',encoding='utf-8') as log:
  p=subprocess.run([str(launcher)],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(f'{label} failed; see logs')
 return round(time.perf_counter()-t,2)
for op,name in ops.items():
 (R/f'sim/tb_pipeline_{name}.sv').write_text(f'`timescale 1ns/1ps\nmodule tb_pipeline_{name};tb_integrated #(.OP_FILTER({op})) run();endmodule\n')
if not options.skip_compile:
 print('Compiling integrated testbench',flush=True)
 tool('xvlog',['--incr','--relax','--sv','--work','xil_defaultlib',str(R/'sim/tb_integrated.sv'),*[str(p) for p in (R/'sim').glob('tb_pipeline_*.sv')]],'integrated_compile')
 for snapshot,top in [('integrated','tb_integrated'),('integrated_m4','tb_integrated_m4')]:
  print('Elaborating',snapshot,flush=True)
  tool('xelab',['--incr','--relax','--debug','typical','--mt','2','-L','xil_defaultlib','-L','floating_point_v7_1_22','-L','unisims_ver','-L','secureip','--snapshot',snapshot,'xil_defaultlib.'+top,'xil_defaultlib.glbl'],'elaborate_'+snapshot)
def simulate(op,name,rows):
 label=f'integrated_{name}'+('_m4' if rows==4 else '')
 out=R/'results'/label;out.mkdir(exist_ok=True)
 snapshot='integrated_m4' if rows==4 else 'integrated'
 # XSim writes the plusargs into xsim.dir/<snapshot>/xsim_script.tcl.
 # Each concurrent invocation MUST have a private snapshot/working directory.
 cwd=B/'runs'/label;cwd.mkdir(parents=True,exist_ok=True)
 shutil.copytree(B/'xsim.dir'/snapshot,cwd/'xsim.dir'/snapshot,dirs_exist_ok=True)
 args=[snapshot,'--tclbatch',str(R/'scripts/run_wave.tcl'),'--wdb',str(out/'validation.wdb'),'--log',str(out/'xsim.log'),
       '--testplusarg',f'OP={op}','--testplusarg',f'DATA_DIR={D}','--testplusarg',f'OUT_DIR={out}']
 if rows==4:args+=['--testplusarg','CASE_START=3','--testplusarg','CASE_STOP=4']
 print('Starting',label,flush=True)
 elapsed=tool('xsim',args,label,cwd)
 text=(out/'xsim.log').read_text(errors='replace')
 assert f'INTEGRATED_COMPLETED op={op} rows={rows} cases={1 if rows==4 else 6}' in text,label+' incomplete'
 print('Completed',label,elapsed,'s',flush=True)
 return dict(op=op,name=name,rows=rows,elapsed_s=elapsed,directory=label)
jobs=[(int(op),name,1) for op,name in ops.items()]+[(op,ops[str(op)],4) for op in [7,0,8,11]]
records=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 futures=[pool.submit(simulate,*job) for job in jobs]
 for f in as_completed(futures):
  records.append(f.result());(L/'integrated_commands.json').write_text(json.dumps(records,indent=2))
print('INTEGRATED_ALL_CAPTURES_COMPLETE',flush=True)
