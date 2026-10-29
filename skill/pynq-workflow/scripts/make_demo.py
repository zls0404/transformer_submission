"""Create two synthetic applications for offline reuse testing. No real bitstream."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_skill import fixture,Backend
from run_contract import run_transaction
from pynq_common import write_json,compare,read_values

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output).resolve()
    if root.exists():p.error('Output must be a new directory')
    root.mkdir(parents=True);results=[]
    for name,expected in [('loopback',[1,2,3,4]),('vector_add',[11,22,33,44])]:
        work=root/name;fixture(work,name);backend=Backend(name);r=run_transaction(work/'contract.json',work/'result',backend=backend)
        actual,_=read_values(work/'result/y.csv','integer');match=compare(actual,expected,0,0)
        results.append({'application':name,'transaction_passed':r['passed'],'comparison':match,'execution_kind':'offline_mock','physical_board_access':False})
    write_json(root/'reuse_results.json',results);print(str(root/'reuse_results.json'));return 0

if __name__=='__main__':sys.exit(main())
