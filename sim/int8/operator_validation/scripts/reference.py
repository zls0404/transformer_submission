"""INT8 reference functions. All arithmetic widths follow the packaged RTL."""
import numpy as np
def fixed_softmax(codes,si=6,so=7):
 maximum=max(codes);weights=[]
 for q in codes:
  sub=(q-maximum)*(1<<(10-si))-1024
  magnitude=-(sub+sub//2);whole,frac=divmod(magnitude,1024)
  weights.append(0 if whole>=14 else (16384-8*frac)//(1<<whole))
 total=sum(weights);den=min((1<<k for k in range(26)),key=lambda p:(abs(total-p),-p))
 return [min(127,((w<<so)+den//2)//den) for w in weights]
def mm(a,b,shift=4):
 acc=np.asarray(a,dtype=np.int64)@np.asarray(b,dtype=np.int64)
 return np.clip((acc+(1<<(shift-1)))>>shift,-128,127) if shift else np.clip(acc,-128,127)
def signed(v,b):return ((int(v)+(1<<(b-1)))%(1<<b))-(1<<(b-1))
def gelu(q,scale):
 x=signed(q<<(7-scale),16) if scale<=7 else q>>(scale-7)
 z=signed(signed(x,10)*3,12);u=signed(z>>2,10);t=signed((-u if z<0 else u)-224,10)
 ll=signed(-37*signed(t*t,19)+(1<<21),26);ll=-ll if z<0 else ll
 l=signed((ll>>14),9);out=signed(signed(l+128,10)*signed(x,10),19);y=signed(out>>8,11)
 if q<0 and x<=-320:return 0
 if q>=0 and x>=320:return q
 return signed(y>>(7-scale) if scale<=7 else y<<(scale-7),8)
