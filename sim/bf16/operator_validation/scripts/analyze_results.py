"""Analyze actual XSim captures without altering, trimming, or repairing them."""
from pathlib import Path
import csv,hashlib,html,json,math
from datetime import datetime,timezone,timedelta
import numpy as np
from reference import OPS,N,to_bf16,from_bf16,EPS,GELU_COEF

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parents[2]/"data/bf16"
REPORT=ROOT/"report"

def readcsv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def writecsv(path,rows):
    if not rows:return
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def metrics(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    if a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        return {k:float("nan") for k in ("mae","rmse","max_abs","relative_l2")}
    d=a-b;denom=np.linalg.norm(b)
    return dict(mae=float(np.mean(np.abs(d))),rmse=float(np.sqrt(np.mean(d*d))),
        max_abs=float(np.max(np.abs(d))),relative_l2=float(np.linalg.norm(d)/denom) if denom>1e-12 else float("nan"))

def valhex(word,width):
    try:return int(word,16)
    except ValueError:return None

def fnum(v):
    if isinstance(v,(int,np.integer)):return str(v)
    if isinstance(v,(float,np.floating)):return f"{v:.6g}" if np.isfinite(v) else "N/A"
    return str(v)

def main():
    REPORT.mkdir(exist_ok=True)
    cases=json.loads((DATA/"cases.json").read_text(encoding="utf-8"))
    refs=np.load(DATA/"reference_data.npz")
    rows=[];aggregate=[];missing=[]
    for op,name in OPS.items():
        result=ROOT/"results"/name
        if not (result/"rtl_summary.csv").is_file():missing.append(name);continue
        summaries=readcsv(result/"rtl_summary.csv");samples=readcsv(result/"rtl_samples.csv")
        bycase={i:[] for i in range(len(cases))}
        for sample in samples:bycase[int(sample["case_id"])].append(sample)
        per_element=result/"three_value_comparison.csv"
        with per_element.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(["case_id","case_name","category","index","original_input","input_bf16_hex",
                "decoded_input","F_original_fp64","Q_bf16_input_output_reference","R_rtl_bf16","rtl_fp32",
                "Q_minus_F","R_minus_F","R_minus_Q","rtl_fp32_minus_ideal_qinput","cycle","rtl_bf16_hex"])
            for s in summaries:
                tc=int(s["case_id"]);case=cases[tc];raw=bycase[tc]
                order=[int(a["beat"])*4+int(a["lane"]) for a in raw]
                ordered=(order==list(range(N)))
                bits32=[valhex(a["fp32_hex"],32) for a in raw]
                bits16=[valhex(a["bf16_hex"],16) for a in raw]
                a32=np.array([0 if x is None else x for x in bits32],dtype=np.uint32).view(np.float32).astype(np.float64)
                a16=from_bf16([0 if x is None else x for x in bits16]).astype(np.float64)
                invalid=np.array([x is None or y is None for x,y in zip(bits32,bits16)])
                a32[invalid]=np.nan;a16[invalid]=np.nan
                flags=["unknown_beats","unknown_valid","premature_beats","fifo1_fault","fifo2_fault","timeout"]
                protocol_ok=ordered and int(s["in_beats"])==192 and int(s["out_beats"])==192 and all(int(s[k])==0 for k in flags)
                finite=bool(np.isfinite(a32).all() and np.isfinite(a16).all())
                rounding_mismatches=int(sum(x!=int(y) for x,y in zip(bits16,to_bf16(a32)))) if not invalid.any() else -1
                F=refs[f"fp64_op{op}"][tc];Q=refs[f"qref_op{op}"][tc];ideal=refs[f"qinput_op{op}"][tc]
                r=dict(op=op,operator=name,case_id=tc,name=case["name"],category=case["category"],N=N,
                    in_beats=int(s["in_beats"]),out_beats=int(s["out_beats"]),protocol_ok=protocol_ok,
                    finite=finite,rounding_mismatches=rounding_mismatches,
                    first_latency_cycles=int(s["first_out"])-int(s["first_in"]) if int(s["first_out"])>=0 else -1,
                    last_latency_cycles=int(s["last_out"])-int(s["first_in"]) if int(s["last_out"])>=0 else -1,
                    output_span_cycles=int(s["last_out"])-int(s["first_out"]) if int(s["first_out"])>=0 else -1,
                    last_input_to_last_output_cycles=int(s["last_out"])-int(s["last_in"]) if int(s["last_out"])>=0 else -1,
                    **{k:int(s[k]) for k in flags})
                r["first_latency_ns"]=r["first_latency_cycles"]*10 if r["first_latency_cycles"]>=0 else -1
                r["last_latency_ns"]=r["last_latency_cycles"]*10 if r["last_latency_cycles"]>=0 else -1
                for tag,a,b in [("Q_F",Q,F),("R_F",a16,F),("R_Q",a16,Q),("FP32_ideal",a32,ideal)]:
                    m=metrics(a,b) if ordered or tag=="Q_F" else {k:float("nan") for k in ("mae","rmse","max_abs","relative_l2")}
                    r.update({f"{tag}_{k}":v for k,v in m.items()})
                r["output_sum"]=float(a16.sum()) if ordered else float("nan")
                r["output_mean"]=float(a16.mean()) if ordered else float("nan")
                r["output_mean_square"]=float(np.mean(a16*a16)) if ordered else float("nan")
                numeric_ok=False;invariant_ok=False
                if ordered and finite:
                    # Predeclared application criterion inherited from supplied
                    # bench_snake_report.py: 5% relative L2. For zero references,
                    # use an explicit 0.002 absolute limit instead of dividing by 0.
                    numeric_ok=(r["R_Q_relative_l2"]<=.05 if np.linalg.norm(Q)>1e-12 else r["R_Q_max_abs"]<=.002)
                    if op==0:invariant_ok=bool(a16.min()>=0 and a16.max()<=1 and abs(a16.sum()-1)<=.02)
                    elif op==1:invariant_ok=abs(a16.mean())<=.02*max(1.,float(np.sqrt(np.mean(a16*a16))))
                    elif op==2:invariant_ok=bool(np.mean(a16*a16)<=1.03)
                    else:
                        x=refs["input_decoded"][tc].astype(np.float64)
                        invariant_ok=bool(np.all(a16*x>=-1e-8) and np.all(np.abs(a16)<=np.abs(x)*1.01+1e-6))
                if ordered:
                    for j in range(N):
                        w.writerow([tc,case["name"],case["category"],j,refs["original"][tc,j],f"{int(refs['input_bf16'][tc,j]):04x}",
                            refs["input_decoded"][tc,j],F[j],Q[j],a16[j],a32[j],Q[j]-F[j],a16[j]-F[j],a16[j]-Q[j],
                            a32[j]-ideal[j],raw[j]["cycle"],raw[j]["bf16_hex"]])
                r["numeric_criterion_ok"]=bool(numeric_ok);r["invariant_ok"]=bool(invariant_ok)
                r["case_ok"]=bool(protocol_ok and finite and rounding_mismatches==0 and numeric_ok and invariant_ok)
                if op==4:
                    for k,v in metrics(a16,refs["gelu_tanh"][tc]).items():r["R_tanh_"+k]=v
                rows.append(r)
        nominal=[r for r in rows if r["op"]==op and r["category"]=="nominal"]
        if len(nominal)!=24:missing.append(name+":incomplete_nominal_cases")
        aggregate.append(dict(operator=name,nominal_cases=len(nominal),protocol_pass=sum(r["protocol_ok"] for r in nominal),
            numeric_pass=sum(r["numeric_criterion_ok"] for r in nominal),invariant_pass=sum(r["invariant_ok"] for r in nominal),
            all_checks_pass=sum(r["case_ok"] for r in nominal),
            nonfinite_cases=sum(not r["finite"] for r in nominal),
            first_latency_cycles_min=min((r["first_latency_cycles"] for r in nominal),default=-1),
            first_latency_cycles_max=max((r["first_latency_cycles"] for r in nominal),default=-1),
            last_latency_cycles_min=min((r["last_latency_cycles"] for r in nominal),default=-1),
            last_latency_cycles_max=max((r["last_latency_cycles"] for r in nominal),default=-1),
            worst_R_Q_max_abs=max((r["R_Q_max_abs"] for r in nominal),default=float("nan")),
            worst_finite_R_Q_max_abs=max((r["R_Q_max_abs"] for r in nominal if np.isfinite(r["R_Q_max_abs"])),default=float("nan")),
            worst_R_Q_relative_l2=max((r["R_Q_relative_l2"] for r in nominal if np.isfinite(r["R_Q_relative_l2"])),default=float("nan"))))
    # Union keys: GELU has extra comparison columns.
    keys=list(dict.fromkeys(k for r in rows for k in r))
    writecsv(REPORT/"case_metrics.csv",[{k:r.get(k,"") for k in keys} for r in rows])
    writecsv(REPORT/"operator_summary.csv",aggregate)
    manifest=json.loads((ROOT/"original_sources_sha256.json").read_text())
    changed=[m["path"] for m in manifest if hashlib.sha256((ROOT/m["path"]).read_bytes()).hexdigest()!=m["sha256"]]
    provenance=dict(path_base="project_root",time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        tool="Vivado/XSim 2026.1",clock_period_ns=10,seed=20261021,N=N,
        epsilon=EPS,gelu_coefficient=GELU_COEF,nominal_relative_l2_limit=.05,zero_ref_absolute_limit=.002,
        modified_imported_sources=changed,missing_results=missing,
        files=[dict(path=p.relative_to(ROOT.parents[2]).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in [DATA/"inputs.hex",DATA/"reference_data.npz",*sorted((ROOT/"results").glob("*/rtl_*.csv")),
                      *sorted((ROOT/"results/accumulator_startup").glob("*.csv"))]])
    (REPORT/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# BF16 算子独立仿真报告","",
        "本报告来自原工程 RTL 与 AMD 浮点 IP 的真实 XSim 行为仿真。没有用 Python 结果替代硬件输出。",
        "五种算子是共享 Snake 阵列的五种配置；测试入口排除了 GEMM、PS、DMA 和 AXI-Lite。", "",
        "## 测试配置与数值基准","",
        "- 时钟周期 10 ns（100 MHz 仿真激励），固定每行 768 个元素、每拍 4 个 BF16，共 192 拍。",
        "- 每个算子 24 组常规输入；另外各 1 组输入停顿探测、1 组扩展数值范围探测，单独列出。",
        "- 常规输入连续，每行前复位控制/FIFO 并排空浮点 IP；不代表已支持无复位连续多行。",
        "- F：对原始浮点输入做 FP64 数学参考；Q：对 BF16 解码输入做 FP64 参考，再舍入成 BF16；R：RTL 的实际 BF16 输出。",
        "- Q−F 含输入/输出格式舍入误差；R−Q 用于检查硬件计算偏差。Q 不模拟每一级 FP32 舍入，不能要求逐位相同。",
        "- 同时保留 RTL 原始 FP32 输出，检查最终 BF16 转换是否与原始 RNE 规则逐位一致。",
        "- LayerNorm/RMSNorm 使用 RTL 的 epsilon，无 affine 参数（gamma=1、beta=0）。",
        f"- GELU 的主参考是 RTL 的 x*sigmoid({GELU_COEF:.16g}*x)，tanh GELU 仅作为额外算法差异比较。",
        "- 数值判据预设为 R 对 Q 的相对 L2≤5%（沿用所给上板脚本的应用判据）；零参考改用最大绝对误差≤0.002。此阈值不是模型任务精度保证。",
        "- 功能检查：输出数量/顺序、无 X/Z、有限数值、FIFO 故障、超时、额外输出、BF16 舍入、各算子的数值性质。接口没有 ready/TLAST，不虚构这些协议检查。", "",
        "## 常规测试汇总","",
        "|算子|帧完整性通过|数值判据通过|全部检查通过|首输出周期|末输出周期|非有限数用例数|有限输出最大绝对误差 R−Q|",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for a in aggregate:
        lat=lambda key:f"{a[key+'_min']}～{a[key+'_max']}" if a[key+'_min']!=a[key+'_max'] else str(a[key+'_min'])
        lines.append(f"|{a['operator']}|{a['protocol_pass']}/{a['nominal_cases']}|{a['numeric_pass']}/{a['nominal_cases']}|{a['all_checks_pass']}/{a['nominal_cases']}|{lat('first_latency_cycles')}|{lat('last_latency_cycles')}|{a['nonfinite_cases']}|{fnum(a['worst_finite_R_Q_max_abs'])}|")
    lines.extend(["", "延时从首个有效输入被上升沿采样，到首个/最后一个有效输出被上升沿采样的周期差计算；乘以 10 得 ns。包含算子内部缓存与流水线，不包含行前复位、矩阵乘法、DDR 或 DMA，也不是综合后的最高频率。", "",
        "## 异常与边界探测（保留全部结果）", "",
        "|算子|用例|类别|输出拍数|协议|数值判据|最大绝对误差 R−Q|FIFO故障|",
        "|---|---|---|---:|---|---|---:|---|"])
    for r in rows:
        if r["category"]!="nominal" or not r["case_ok"]:
            lines.append(f"|{r['operator']}|{r['name']}|{r['category']}|{r['out_beats']}|{'通过' if r['protocol_ok'] else '异常'}|{'通过' if r['numeric_criterion_ok'] else '未通过'}|{fnum(r['R_Q_max_abs'])}|{r['fifo1_fault']}/{r['fifo2_fault']}|")
    lines.extend(["", "输入停顿探测超出了原集成顶层连续送入 192 拍的常规使用方式，不把其结果混入常规通过统计。扩展范围结果不代表已验证所有 BF16 数值范围。异常不删除、不修正原 RTL。", "",
        "## 如何理解本次异常", "",
        "1. Softmax、LayerNorm、RMSNorm 的首组全零输入出现 NaN；后面的 signed_zeros 用例输出有限且通过。这里不能据此断定任何全零输入都会失败，也不能直接归因到板卡。尚需定位共享阵列的启动路径。",
        "2. SiLU、GELU 在恒定 −16 输入上输出 0，而理想结果分别约为 −1.8e−6、−2.4e−11。相对 L2 为 1，因此未通过预设的相对误差判据；绝对误差很小，两者必须一起解读。本报告没有事后放宽阈值。",
        "3. 输入每隔 17 拍插入一次空拍时，SiLU、GELU 各输出 384 拍并出现 FIFO 故障；这是连续输入假设之外的探测结果，应避免据此宣称接口支持任意输入停顿。",
        "4. 对很接近的输入，BF16 输入舍入本身可能抹掉差异。尤其归一化要同时查看 Q−F 和 R−Q，不能把输入量化损失都归到硬件计算。", ""])
    diagnostic=ROOT/"results/accumulator_startup/frame_ends.csv"
    if diagnostic.exists():
        captures=readcsv(diagnostic)
        words=[r["fp32_hex"] for r in captures]
        expected=["00000000","44400000","00000000","44400000"]
        lines.extend(["### 额外的累加 IP 诊断", "",
            "`tb_accumulator_startup.sv` 直接连接原始 floating_acc IP，连续测试四帧：每帧 192 个 0 或 4，理论帧和依次为 0、768、0、768。",
            f"实测帧末编码为 `{', '.join(words)}`；{'四帧均正确' if words==expected else '与理论不符，需查看原始记录'}。这项测试独立于 Snake 控制和 FIFO，说明不能仅凭首帧 NaN 就认定累加 IP 本身启动错误。诊断证据保存在 `results/accumulator_startup/`。", ""])
    lines.extend([
        "## 文件与限制", "",
        "- `case_metrics.csv`：每个算子、每组用例的全部误差与延时。",
        "- `operator_summary.csv`：常规测试汇总。",
        "- `../results/<算子>/rtl_samples.csv`、`rtl_summary.csv`、`xsim.log`、`validation.wdb`：原始仿真证据和波形。",
        "- `../results/<算子>/three_value_comparison.csv`：完整输出用例的逐元素 F/Q/R 与内部 FP32 对比（包含 NaN）；不完整或额外输出始终保留在原始采样 CSV。",
        "- `../sim/tb_softmax.sv` 等：五种算子的独立仿真顶层；公共激励与记录在 `tb_operator_validation.sv`。",
        "- `provenance.json` 与 `../original_sources_sha256.json`：文件来源、判据、校验记录。",
        f"- 导入源码/IP 校验：{'全部未修改' if not changed else '发现修改：'+str(changed)}。",
        "- 本次未测上板延时、面积、功耗、Fmax 或神经网络任务准确率；独立入口使用同一原始共享阵列，不代表已经完成五套最小面积硬件裁剪。",
        "- 五种算子的通过证据来自命令行 XSim。GUI 工程可由 scripts/create_project.tcl 创建；本报告不将 GUI 交互启动作为已验证路径。",
        f"- 结果完整性：{'五种算子全部采集完成' if not missing else '缺失：'+str(missing)}。", ""])
    (REPORT/"standalone_report.md").write_text("\n".join(lines),encoding="utf-8")
    # A standalone readable table report; scientific numerical data remain in CSV.
    headers=["operator","nominal_cases","protocol_pass","numeric_pass","all_checks_pass","nonfinite_cases","first_latency_cycles_min","last_latency_cycles_max","worst_finite_R_Q_max_abs"]
    table="<table><thead><tr>"+"".join(f"<th>{html.escape(k)}</th>" for k in headers)+"</tr></thead><tbody>"
    for a in aggregate:table+="<tr>"+"".join(f"<td>{html.escape(fnum(a[k]))}</td>" for k in headers)+"</tr>"
    table+="</tbody></table>"
    detail="<pre>"+html.escape("\n".join(lines))+"</pre>"
    (REPORT/"standalone_report.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>BF16 算子独立仿真</title><style>body{font-family:Segoe UI,Microsoft YaHei,sans-serif;margin:40px;line-height:1.7;color:#172b4d}table{border-collapse:collapse;max-width:100%;font-size:13px}th,td{padding:10px;border:1px solid #ccd6e3}th{background:#edf3fa}pre{white-space:pre-wrap;font-family:inherit}h1{color:#163d78}</style><h1>BF16 算子独立仿真</h1>'+table+detail+'</html>',encoding="utf-8")
    print(json.dumps(dict(summary=aggregate,modified_sources=changed,missing=missing),ensure_ascii=False,indent=2))
    if changed or missing:raise SystemExit("Incomplete evidence or imported source modification detected")

if __name__=="__main__":main()
