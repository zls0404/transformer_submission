"""Compile original AMD IP simulation models and run each operator separately."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from reference import OPS

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parents[2]/"data/bf16"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vivado",default=r"D:/vivado/2026.1/Vivado")
    ap.add_argument("--skip-compile",action="store_true")
    ap.add_argument("--compile-only",action="store_true")
    ap.add_argument("--op",type=int,choices=list(OPS))
    ap.add_argument("--smoke",action="store_true")
    ap.add_argument("--accumulator-probe",action="store_true")
    args=ap.parse_args()
    build=ROOT/"build";build.mkdir(exist_ok=True)
    logs=ROOT/"logs";logs.mkdir(exist_ok=True)
    viv=Path(args.vivado);env=os.environ.copy()
    env["XILINX_VIVADO"]=str(viv)
    env["PATH"]=str(viv/"bin")+os.pathsep+env.get("PATH","")
    record=json.loads((logs/"commands.json").read_text()) if (logs/"commands.json").exists() else []
    def run(tool,argv,label):
        cmd=[str(viv/"bin"/(tool+".bat")),*[str(x).replace("\\","/") for x in argv]]
        if tool=="xsim":
            # CMD treats '=' as an argument separator inside batch files unless
            # the plusarg is explicitly quoted. Python's automatic quoting does
            # not quote '='. Keep a reviewable fully quoted launcher per run.
            if any(any(c in s for c in '\r\n"%') for s in cmd):
                raise ValueError("Unsupported character in simulator launch path")
            launcher=build/("launch_"+label+".cmd")
            launcher.write_text('@echo off\ncall '+" ".join('"'+s+'"' for s in cmd)+'\nexit /b %errorlevel%\n',encoding="ascii")
            launch_cmd=[str(launcher)]
        else:launch_cmd=cmd
        print(f"Starting {label}",flush=True)
        t=time.perf_counter()
        with (logs/(label+".log")).open("w",encoding="utf-8") as log:
            p=subprocess.run(launch_cmd,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT)
        record.append(dict(step=label,returncode=p.returncode,elapsed_s=time.perf_counter()-t,command=cmd))
        (logs/"commands.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
        if p.returncode:
            tail=(logs/(label+".log")).read_text(encoding="utf-8",errors="replace")[-6500:]
            print(tail);raise SystemExit(f"{label} failed ({p.returncode}); see logs")
        print(f"Finished {label} ({record[-1]['elapsed_s']:.1f}s)",flush=True)
    if args.accumulator_probe:
        result=ROOT/"results/accumulator_startup";result.mkdir(parents=True,exist_ok=True)
        run("xvlog",["--incr","--relax","--sv","--work","xil_defaultlib",str(ROOT/"sim/tb_accumulator_startup.sv")],"compile_accumulator_probe")
        run("xelab",["--incr","--relax","--debug","typical","--mt","2","-L","xil_defaultlib",
            "-L","floating_point_v7_1_22","-L","unisims_ver","-L","secureip",
            "--snapshot","accumulator_probe","xil_defaultlib.tb_accumulator_startup","xil_defaultlib.glbl"],"elaborate_accumulator_probe")
        run("xsim",["accumulator_probe","--runall","--log","../results/accumulator_startup/xsim.log"],"simulate_accumulator_probe")
        return
    if not args.skip_compile:
        ipfiles=sorted((ROOT/"ip").glob("*/sim/*.vhd"))
        (build/"vhdl.prj").write_text("\n".join(f'vhdl xil_defaultlib "{p.as_posix()}"' for p in ipfiles)+"\nnosort\n",encoding="utf-8")
        run("xvhdl",["--incr","--relax","-prj","vhdl.prj"],"compile_vhdl")
        rtl=sorted(p for p in (ROOT/"rtl").iterdir() if p.suffix in (".v",".sv"))
        sim=sorted((ROOT/"sim").glob("*.sv"))
        run("xvlog",["--incr","--relax","--sv","--work","xil_defaultlib",*[str(p) for p in rtl+sim],str(viv/"data/verilog/src/glbl.v")],"compile_verilog")
        run("xelab",["--incr","--relax","--debug","typical","--mt","2",
            "-L","xil_defaultlib","-L","floating_point_v7_1_22","-L","unisims_ver","-L","secureip",
            "--snapshot","operator_validation","xil_defaultlib.tb_operator_validation","xil_defaultlib.glbl"],"elaborate")
    if args.compile_only:
        return
    count=len(json.loads((DATA/"cases.json").read_text(encoding="utf-8")))
    for op in ([args.op] if args.op is not None else OPS):
        name=OPS[op]+("_smoke" if args.smoke else "")
        result=ROOT/"results"/name;result.mkdir(parents=True,exist_ok=True)
        argv=["operator_validation","--tclbatch","../scripts/run_wave.tcl",
              "--wdb",f"../results/{name}/validation.wdb",
              "--testplusarg",f"DATA_DIR={DATA.as_posix()}","--testplusarg",f"OP={op}","--testplusarg",f"CASES={count}",
              "--testplusarg",f"OUT_DIR=../results/{name}","--log",f"../results/{name}/xsim.log"]
        if args.smoke:argv.extend(["--testplusarg","CASE_LIMIT=1"])
        run("xsim",argv,"simulate_"+name)
        log=(logs/("simulate_"+name+".log")).read_text(encoding="utf-8",errors="replace")
        if f"CAPTURE_COMPLETED op={op} cases={1 if args.smoke else count}" not in log:
            raise SystemExit(f"Simulation did not reach completion: {name}")
    print("All selected captures completed. Run scripts/analyze_results.py for numerical verdicts.")

if __name__=="__main__":main()
