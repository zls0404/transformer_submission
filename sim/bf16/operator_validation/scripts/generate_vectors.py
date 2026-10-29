from pathlib import Path
import csv,json
import numpy as np
from reference import N,OPS,to_bf16,from_bf16,reference,tanh_gelu

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parents[2]/"data/bf16"

def main():
    DATA.mkdir(exist_ok=True)
    rng=np.random.default_rng(20261021)
    vectors=[]
    def add(name,x,category="nominal",gap=0):
        x=np.broadcast_to(np.asarray(x,dtype=np.float64),(N,)).copy()
        vectors.append((name,x,category,gap))
    add("zeros",0.)
    add("constant_positive",1.)
    add("constant_negative",-1.)
    add("constant_nonexact",.3)
    add("mixed_ramp",np.linspace(-4,4,N))
    add("negative_ramp",np.linspace(-6,-.05,N))
    add("positive_ramp",np.linspace(.05,6,N))
    add("alternating_sign",np.tile([-1.,1.],N//2))
    add("lane_order_pattern",np.tile([.125,.5,1.,2.],N//4))
    x=np.zeros(N); x[0]=8.; add("first_element_peak",x)
    x=np.zeros(N); x[-1]=8.; add("last_element_peak",x)
    add("tiny_ramp",np.linspace(-.001,.001,N))
    for sigma in (.25,1.,3.): add(f"normal_sigma_{sigma}",rng.normal(0,sigma,N))
    add("uniform_2",rng.uniform(-2,2,N))
    add("uniform_8",rng.uniform(-8,8,N))
    add("near_constant_1",1+rng.uniform(-.002,.002,N))
    add("near_constant_100",100+rng.uniform(-.2,.2,N))
    add("alternating_16",np.tile([-16.,16.],N//2))
    add("signed_zeros",np.tile([0.,-0.,-0.,0.],N//4))
    add("constant_16",16.)
    add("constant_minus_16",-16.)
    add("asymmetric_lane_ramp",np.arange(N)%13/4.-1.5)
    add("gap_probe_normal",rng.normal(0,1,N),"protocol_probe",1)
    add("extended_range_96",np.linspace(-96,96,N),"range_probe")
    originals=np.stack([v[1] for v in vectors])
    words=to_bf16(originals); decoded=from_bf16(words)
    # Pad to the declared testbench memory size to avoid ambiguous short loads.
    padded=np.zeros((64,N),dtype=np.uint16);padded[:len(vectors)]=words
    (DATA/"inputs.hex").write_text("".join(f"{int(w):04x}\n" for w in padded.flat),encoding="ascii")
    (DATA/"gaps.hex").write_text("".join(f"{vectors[i][3] if i<len(vectors) else 0:02x}\n" for i in range(64)),encoding="ascii")
    cases=[dict(case_id=i,name=v[0],category=v[2],gap=v[3],N=N) for i,v in enumerate(vectors)]
    (DATA/"cases.json").write_text(json.dumps(cases,indent=2),encoding="utf-8")
    np.savez(DATA/"reference_data.npz",original=originals,input_bf16=words,input_decoded=decoded,
        **{f"fp64_op{op}":np.stack([reference(op,x) for x in originals]) for op in OPS},
        **{f"qinput_op{op}":np.stack([reference(op,x) for x in decoded]) for op in OPS},
        **{f"qref_op{op}":np.stack([from_bf16(to_bf16(reference(op,x))) for x in decoded]) for op in OPS},
        gelu_tanh=np.stack([tanh_gelu(x) for x in decoded]))
    with (DATA/"input_vectors.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["case_id","index","original_float64","bf16_hex","decoded_input"])
        for i in range(len(vectors)):
            for j in range(N):w.writerow([i,j,repr(originals[i,j]),f"{words[i,j]:04x}",float(decoded[i,j])])
    print(f"Prepared {len(vectors)} cases: 24 nominal + gap and range probes, N={N}, seed=20261021")

if __name__=="__main__":main()
