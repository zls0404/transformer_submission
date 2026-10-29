"""Verify a packaged source tree. This does not program hardware or run simulation."""
from pathlib import Path
import argparse,ast,csv,hashlib,json,re,sys,xml.etree.ElementTree as ET

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def rows(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--out',type=Path);parser.add_argument('--skip-manifest',action='store_true');args=parser.parse_args();root=args.root.resolve();issues=[]
 files=sorted(p for p in root.rglob('*') if p.is_file())
 for p in files:
  rel=p.relative_to(root).as_posix()
  if not re.fullmatch('[a-z0-9_./-]+',rel):issues.append('Invalid filename: '+rel)
  if any(x in p.parts for x in ['__pycache__','.Xil','.git','xsim.dir','generated','gui']):issues.append('Generated directory: '+rel)
  if p.suffix in ['.md','.py','.json','.yaml','.ps1','.tcl','.ini','.csv','.html']:
   try:t=p.read_text(encoding='utf-8-sig')
   except UnicodeError:issues.append('Not UTF-8: '+rel);continue
   if '\ufffd' in t:issues.append('Replacement character: '+rel)
   if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',t):issues.append('Control character in text: '+rel)
   try:
    if p.suffix=='.py':ast.parse(t)
    if p.suffix=='.json':read(p)
    if p.suffix in ['.md','.html']:
     for link in re.findall(r'\]\(([^)]+)\)',t):
      if '://' not in link and not link.startswith('#') and not (p.parent/link.split('#')[0]).exists():issues.append('Broken documentation link: '+rel+' -> '+link)
     if p.suffix=='.html':
      for link in re.findall(r'(?:src|href)=[\"\x27]([^\"\x27]+)',t):
       if '://' not in link and not link.startswith('#') and not (p.parent/link.split('#')[0]).exists():issues.append('Broken HTML asset: '+rel+' -> '+link)
   except Exception as e:issues.append(rel+': '+str(e))
  if p.name=='component.xml':
   doc=ET.parse(p);ns={'s':'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'}
   for node in doc.findall('.//s:file/s:name',ns):
    if node.text and not (p.parent/node.text).is_file():issues.append('Missing IP file: '+rel+' -> '+node.text)
 for record in read(root/'data/input_manifest.json')['files']:
  path=root/record['path']
  if not path.is_file() or sha(path)!=record['sha256']:issues.append('Input/reference integrity mismatch: '+record['path'])
 for record in read(root/'data/reference_catalog.json')['references']:
  path=root/record['path']
  if not path.is_file() or sha(path)!=record['sha256']:issues.append('Reference CSV mismatch: '+record['path'])
  elif len(rows(path))!=record['rows']:issues.append('Reference CSV row count mismatch: '+record['path'])
 if not args.skip_manifest:
  manifest=read(root/'build/package_manifest.json');declared={x['path']:x for x in manifest}
  actual={p.relative_to(root).as_posix() for p in files}-{ 'build/package_manifest.json'}
  if actual!=set(declared):issues.append('Manifest file set differs')
  for rel,e in declared.items():
   p=root/rel
   if not p.is_file() or p.stat().st_size!=e['bytes'] or sha(p)!=e['sha256']:issues.append('Manifest mismatch: '+rel)
 bf=rows(root/'sim/bf16/operator_validation/report/case_metrics.csv')+rows(root/'sim/bf16/operator_validation/report/integrated_case_metrics.csv')
 bf_failed=[x for x in bf if x['case_ok'].lower()!='true']
 hold=rows(root/'sim/int8/operator_validation/raw/gelu_backpressure.csv')[0]
 result={'file_integrity_passed':not issues,'file_count':len(files),'issues':issues,'functional_results':{'bf16_cases':len(bf),'bf16_passed':len(bf)-len(bf_failed),'bf16_failed':len(bf_failed),'int8_simd_hold_errors':int(hold['hold_errors'])},'all_functional_checks_passed':not bf_failed and int(hold['hold_errors'])==0,'scope':'Source/archive integrity and retained verdicts. Does not prove all hardware inputs, synthesis, or board execution.'}
 output=json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n'
 if args.out:args.out.write_text(output,encoding='utf-8')
 print(output,end='');return 0 if not issues else 2
if __name__=='__main__':sys.exit(main())
