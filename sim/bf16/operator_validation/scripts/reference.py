"""Independent numerical references; not a bit-accurate floating-IP model."""
import numpy as np

N = 768
OPS = {0:"softmax",1:"layernorm",2:"rmsnorm",3:"silu",4:"gelu"}
EPS = float(np.array([0x3727C5AC], dtype=np.uint32).view(np.float32)[0])
GELU_COEF = float(np.array([0x3FD9D2C7], dtype=np.uint32).view(np.float32)[0])

def to_bf16(x):
    bits = np.asarray(x, dtype=np.float32).view(np.uint32)
    with np.errstate(over="ignore"):
        result = ((bits + np.uint32(0x7fff) + ((bits >> 16) & 1)) >> 16).astype(np.uint16)
    nan = ((bits & 0x7f800000)==0x7f800000) & ((bits & 0x007fffff)!=0)
    return np.where(nan, ((bits >> 16) & 0x8000) | 0x7fff, result).astype(np.uint16)

def from_bf16(x):
    return (np.asarray(x,dtype=np.uint16).astype(np.uint32)<<16).view(np.float32)

def sigmoid(x):
    x=np.asarray(x,dtype=np.float64)
    # Stable for the extended-range probes as well as nominal cases.
    e=np.exp(-np.abs(x))
    return np.where(x>=0, 1/(1+e), e/(1+e))

def reference(op,x):
    x=np.asarray(x,dtype=np.float64)
    if op==0:
        e=np.exp(x-x.max()); return e/e.sum()
    if op==1:
        centered=x-x.mean(); return centered/np.sqrt(np.mean(centered**2)+EPS)
    if op==2: return x/np.sqrt(np.mean(x*x)+EPS)
    if op==3: return x*sigmoid(x)
    if op==4: return x*sigmoid(GELU_COEF*x)
    raise ValueError(op)

def tanh_gelu(x):
    x=np.asarray(x,dtype=np.float64)
    return .5*x*(1+np.tanh(np.sqrt(2/np.pi)*(x+.044715*x**3)))
