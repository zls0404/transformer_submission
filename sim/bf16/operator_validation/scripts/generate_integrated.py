from pathlib import Path
import json,numpy as np
from reference import to_bf16,from_bf16,reference,sigmoid
R=Path(__file__).resolve().parents[1];D=R.parents[2]/'data/bf16/integrated';D.mkdir(parents=True,exist_ok=True)
OPS={7:'gemm',0:'softmax',1:'layernorm',2:'rmsnorm',3:'silu',4:'gelu',8:'layernorm_affine',9:'rmsnorm_affine',10:'masked_softmax',11:'swiglu'}
M=K=4;N=768;rng=np.random.default_rng(20261023)
A=[];B=[];U=[]
for case in range(4):
 a=np.eye(4)
 if case==0:b=np.zeros((4,N))
 elif case==1:b=np.ones((4,N))
 elif case==2:b=np.array([np.linspace(.05,6,N)*s for s in [1,.5,1.25,.75]])
 else:a=rng.uniform(-.5,.75,(4,4));b=rng.normal(0,.25,(4,N))
 u=.7*b+.1 if case!=3 else rng.normal(0,.2,(4,N))
 A.append(a);B.append(b);U.append(u)
A=np.array(A+[A[3],A[3]]);B=np.array(B+[B[3],B[3]]);U=np.array(U+[U[3],U[3]])
G=np.broadcast_to(np.linspace(.75,1.25,N),(6,N)).copy();T=np.broadcast_to(np.linspace(-.1,.1,N),(6,N)).copy()
mask=np.arange(N)%5!=0
def rounded(x):return from_bf16(to_bf16(x)).astype(float)
def calc(op,a,b,u,g,t,quant):
 mm=a@b;up=a@u
 if quant:mm=rounded(mm);up=rounded(up)
 if op==7:y=mm
 elif op in range(5):y=np.array([reference(op,x) for x in mm])
 elif op in [8,9]:y=np.array([reference(1 if op==8 else 2,x) for x in mm])*g+t
 elif op==10:
  z=np.where(mask,mm,-np.inf);e=np.exp(z-z.max(axis=1,keepdims=True));y=e/e.sum(axis=1,keepdims=True)
 else:
  gate=mm*sigmoid(mm)
  if quant:gate=rounded(gate)
  y=gate*up
 return rounded(y) if quant else y
original=dict(A=A,B=B,U=U,G=G,T=T)
decoded={k:rounded(v) for k,v in original.items()}
refs={**original,**{'decoded_'+k:v for k,v in decoded.items()},'mask':mask}
for op in OPS:
 for quant,prefix,vals in [(False,'F',original),(True,'Q',decoded)]:
  refs[f'{prefix}_{op}']=np.array([calc(op,*[vals[k][i] for k in ['A','B','U','G','T']],quant) for i in range(6)])
np.savez(D/'references.npz',**refs)
def hexfile(name,words):
 (D/name).write_text(''.join(f'{int(v):04x}\n' for v in words.flat),encoding='ascii')
hexfile('a.hex',to_bf16(A));hexfile('b.hex',to_bf16(B))
aux=np.concatenate([G,T,np.broadcast_to(mask,(6,N)),U.reshape(6,-1)],axis=1)
hexfile('aux_data.hex',to_bf16(aux))
cases=[dict(id=i,name=n,category=c) for i,(n,c) in enumerate([
 ('cold_zeros','nominal'),('cold_constant_one','nominal'),('cold_positive_ramp','nominal'),
 ('cold_random','nominal'),('random_input_bubbles_output_backpressure','protocol_probe'),('retained_input_repeat','sequence_probe')])]
(D/'cases.json').write_text(json.dumps(cases,indent=2))
(D/'ops.json').write_text(json.dumps(OPS,indent=2))
print('Prepared 10 modes x 6 cases, M=K=4, N=768; no padding shortcut.')
