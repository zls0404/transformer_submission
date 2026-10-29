"""Verify imported files, real captures, plotted numbers and artifact completeness."""
from pathlib import Path
import csv,json,hashlib,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from reference import from_bf16
R=Path(__file__).resolve().parents[1]
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
manifest=json.loads((R/'original_sources_sha256.json').read_text())
for item in manifest:assert hashlib.sha256((R/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
bc=read(R/'report/case_metrics.csv');ic=read(R/'report/integrated_case_metrics.csv')
assert len(bc)==130 and len(ic)==64
assert sum(g['case_ok']=='True' for g in bc)==123
assert sum(g['case_ok']=='True' for g in ic if g['rows']=='1')==54
assert sum(g['case_ok']=='True' for g in ic if g['rows']=='4')==2
refs=np.load(R.parents[2]/'data/bf16/reference_data.npz');irefs=np.load(R.parents[2]/'data/bf16/integrated/references.npz');actual=np.load(R/'report/integrated_captures.npz')
figs=json.loads((R.parents[2]/'picture/bf16/figure_data.json').read_text());assert len(figs)==15
for f in figs:
 name=f['operator'];standalone=f['stage']=='Standalone'
 if standalone:
  gs=[g for g in bc if g['operator']==name];op=int(gs[0]['op']);num=26;nominal=24
  F=refs[f'fp64_op{op}'];Q=refs[f'qref_op{op}'].astype(float);A=np.full((num,768),np.nan)
  raw=read(R/f'results/{name}/rtl_samples.csv')
 else:
  gs=[g for g in ic if g['operator']==name and g['rows']=='1'];op=int(gs[0]['op']);num=6;nominal=4
  F=irefs[f'F_{op}'][:,0];Q=irefs[f'Q_{op}'][:,0];A=np.full((num,768),np.nan)
  raw=read(R/f'results/integrated_{name}/samples.csv')
 for tc in range(num):
  rows=[g for g in raw if int(g['case_id'])==tc]
  if [int(g['beat'])*4+int(g['lane']) for g in rows]==list(range(768)):
   A[tc]=from_bf16([int(g['bf16_hex'],16) for g in rows])
  if not standalone:assert np.array_equal(A[tc],actual[f'R_{op}_1_{tc}'][0],equal_nan=True)
 case=f['example_case'];idx=f['zoom_indices']
 for key,a in [('F',F),('Q',Q),('R',A)]:assert np.array_equal(a[case,idx],np.array(f['zoom_'+key])),(name,key)
 common=[i for i in range(nominal) if np.isfinite(A[i]).all()]
 maes=[np.mean(np.abs(Q[common]-F[common])),np.mean(np.abs(A[common]-F[common])),np.mean(np.abs(A[common]-Q[common]))]
 assert np.allclose(maes,f['aggregate_mae'],rtol=1e-14,atol=0),name
 assert len(common)==f['common_finite_cases']
 assert sum(g['case_ok']!='True' for g in gs)==f['failed_cases']
 for ext in ['png','pdf','svg']:assert (R.parents[2]/'picture/bf16'/f[ext]).stat().st_size>1000
 with Image.open(R.parents[2]/'picture/bf16'/f['png']) as im:
  assert im.size==(4320,2700) and abs(im.info['dpi'][0]-400)<.1
projects=list((R/'gui').rglob('*.xpr'));# GUI projects are optional generated outputs.
for p in projects:
 root=ET.parse(p).getroot()
 for node in root.findall('.//File'):
  path=node.attrib.get('Path','')
  if path.startswith('$PPRDIR/'):
   assert (p.parent/path[len('$PPRDIR/'):]).resolve().is_file(),(p,path)
result={'imported_source_files_unchanged':len(manifest),'test_cases':194,'passed':179,'failed':15,
 'standalone_cases':130,'pipeline_single_row_cases':60,'production_four_row_cases':4,
 'figures':15,'png_dpi':400,'vivado_simulation_projects':len(projects),'waveform_files':len(list((R/'results').rglob('*.wdb'))),
 'checked':'SHA-256, CSV capture shape, plotted F/Q/R points, independently recomputed aggregate MAE, project source references, retained raw captures and WDBs'}
(R/'report/delivery_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
