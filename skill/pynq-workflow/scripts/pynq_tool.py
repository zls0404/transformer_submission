"""Read-only PYNQ artifact and result checks, except writing the selected JSON report."""
import argparse,csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pynq_common import *

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('inspect');a.add_argument('--bit',required=True);a.add_argument('--hwh',required=True);a.add_argument('--part',required=True);a.add_argument('--hashes')
    a=sub.add_parser('check');a.add_argument('contract');a.add_argument('--artifact-root')
    a=sub.add_parser('compare')
    for k in ['actual','reference']:a.add_argument('--'+k,required=True);a.add_argument('--'+k+'-encoding',choices=['float','integer','bf16'],default='float');a.add_argument('--'+k+'-fraction-bits',type=int,default=0)
    a.add_argument('--atol',type=float,required=True);a.add_argument('--rtol',type=float,required=True)
    a=sub.add_parser('stats');a.add_argument('csv');a.add_argument('--column',required=True);a.add_argument('--unit',choices=['ns','us','ms','s'],required=True);a.add_argument('--scope',required=True)
    a=sub.add_parser('reports');a.add_argument('--timing',required=True);a.add_argument('--utilization',required=True);a.add_argument('--drc',required=True);a.add_argument('--part',required=True)
    for a in sub.choices.values():a.add_argument('--out')
    args=p.parse_args(argv)
    try:
        if args.cmd=='inspect':
            result=inspect_pair(args.bit,args.hwh,args.part,read_json(args.hashes) if args.hashes else None)
        elif args.cmd=='check':
            contract=read_json(args.contract);validate_contract(contract)
            root=Path(args.artifact_root).resolve() if args.artifact_root else Path(args.contract).resolve().parent
            art=contract['artifacts'];pair=inspect_pair(root/art['bit'],root/art['hwh'],contract['target_part'],art.get('sha256'))
            result=validate_contract(contract,pair['hwh']);result['pair']=pair
            for name,b in contract.get('buffers',{}).items():
                if b['direction']=='input':
                    input_values(root,b)
        elif args.cmd=='compare':
            a,_=read_values(args.actual,args.actual_encoding,args.actual_fraction_bits);b,_=read_values(args.reference,args.reference_encoding,args.reference_fraction_bits)
            result=compare(a,b,args.atol,args.rtol);result['sources']={'actual_sha256':sha256(args.actual),'reference_sha256':sha256(args.reference)}
        elif args.cmd=='stats':
            with Path(args.csv).open(encoding='utf-8-sig') as f:
                rr=csv.DictReader(f);require(args.column in (rr.fieldnames or []),'Latency column is missing');vals=[float(r[args.column]) for r in rr]
            result=latency_stats(vals,args.unit,args.scope);result['source_sha256']=sha256(args.csv)
        else:result=vivado_reports(args.timing,args.utilization,args.drc,args.part)
        if args.out:write_json(args.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0 if result.get('passed',True) else 1
    except (CheckError,OSError,ValueError,ET.ParseError) as e:
        result={'passed':False,'error':str(e),'hardware_executed':False}
        if args.out:write_json(args.out,result)
        print(json.dumps(result,ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
