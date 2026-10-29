"""Bind a template to inspected artifacts and inputs; never downloads hardware."""
from pathlib import Path
import argparse,copy,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from pynq_common import *

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('template');p.add_argument('--artifact-root',required=True);p.add_argument('--input-root');p.add_argument('--out',required=True)
    args=p.parse_args(argv)
    try:
        source=Path(args.template).resolve();root=Path(args.artifact_root).resolve();inputs=Path(args.input_root).resolve() if args.input_root else root;out=Path(args.out).resolve()
        require(not out.exists(),'Output contract exists; choose a new filename')
        data=copy.deepcopy(read_json(source));validate_contract(data);a=data['artifacts']
        pair=inspect_pair(root/a['bit'],root/a['hwh'],data['target_part'])
        validate_contract(data,pair['hwh'])
        for b in data.get('buffers',{}).values():
            if b['direction']=='input':
                payload=(inputs/b['file']).read_bytes();input_values(inputs,b,payload)
                b['sha256']=hashlib.sha256(payload).hexdigest()
        for key in ['bit','hwh']:a[key]=Path(os.path.relpath(root/a[key],out.parent)).as_posix()
        a['sha256']={key:pair[key]['sha256'] for key in ['bit','hwh']}
        for b in data.get('buffers',{}).values():
            if b['direction']=='input':b['file']=Path(os.path.relpath(inputs/b['file'],out.parent)).as_posix()
        data['binding']={'template_sha256':sha256(source),'same_build_proof':'User supplies files from the same export; hashes bind the selected files but do not prove their build origin.','hardware_executed':False}
        write_json(out,data);print(str(out));return 0
    except (CheckError,OSError,ValueError,ET.ParseError) as e:
        print(str(e),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
