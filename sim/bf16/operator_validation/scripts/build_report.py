"""Build explanatory reports from the captured CSVs, without changing verdicts."""
from pathlib import Path
import csv,json,hashlib,math
import numpy as np
import argparse
parser=argparse.ArgumentParser();parser.add_argument("--markdown-only",action="store_true");options=parser.parse_args()
R=Path(__file__).resolve().parents[1];P=R/'report'
def read(name):
 with (P/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def yes(x):return str(x).lower()=='true'
def fmt(x):
 try:return f'{float(x):.6g}' if math.isfinite(float(x)) else '未定义'
 except (ValueError,TypeError):return str(x)
base=read('operator_summary.csv');bc=read('case_metrics.csv');sums=read('integrated_summary.csv');ic=read('integrated_case_metrics.csv')
names={'softmax':'Softmax','layernorm':'LayerNorm','rmsnorm':'RMSNorm','silu':'SiLU','gelu':'Sigmoid GELU','gemm':'GEMM','layernorm_affine':'LayerNorm affine','rmsnorm_affine':'RMSNorm affine','masked_softmax':'Masked Softmax','swiglu':'SwiGLU'}
bh=['算子','全部检查','首输出/周期','末输出/周期','有限输出最大 |R−Q|']
bt=[[names[b['operator']],b['all_checks_pass']+'/24',b['first_latency_cycles_min'],b['last_latency_cycles_min'],fmt(b['worst_finite_R_Q_max_abs'])] for b in base]
ih=['模式','常规通过','全部通过','协议通过','非有限用例']
it=[[names[b['operator']],b['nominal_passed']+'/4',b['passed']+'/6',b['protocol_passed']+'/6',b['nonfinite']] for b in sums]
lh=['模式','start→首输出/周期','start→末输出/周期','start→末输出/μs']
lt=[]
for b in sums:
 gs=[g for g in ic if g['operator']==b['operator'] and g['rows']=='1' and g['category']=='nominal']
 assert len(set(g['first_from_start_cycles'] for g in gs))==1
 assert len(set(g['last_from_start_cycles'] for g in gs))==1
 g=gs[0];lt.append([names[b['operator']],g['first_from_start_cycles'],g['last_from_start_cycles'],f"{int(g['last_from_start_cycles'])*.01:.2f}"])
mh=['四行随机补测','全部检查','各行有限元素数','start→末输出/周期']
arr=np.load(P/'integrated_captures.npz');mt=[]
for g in ic:
 if g['rows']=='4':
  a=arr[f"R_{g['op']}_4_{g['case_id']}"]
  mt.append([names[g['operator']],'通过' if yes(g['case_ok']) else '未通过',' / '.join(str(int(np.isfinite(row).sum())) for row in a),g['last_from_start_cycles']])
scope='Vivado/XSim 2026.1，10 ns 时钟。基础五种配置直接驱动原共享 Snake 非线性阵列；新版十种模式驱动未修改的 snake_acc_top，单行 M=1、K=4、N=768。另选 4 种模式测试生产配置 M=4、K=4、N=768。排除 PS、DDR、DMA，未测试面积、功耗、Fmax 或完整模型准确率。'
ref='F 为原始浮点输入的数学参考；Q 为 BF16 解码输入的数学参考，并按实际 BF16 接口边界舍入；R 为真实 RTL 捕获输出。Q 使用 FP64 数学运算，不逐级模拟内部 FP32 IP。GELU 对照实现的 x·sigmoid(1.7017449140548706x)。'
criterion='预设数值判据：R 对 Q 的相对 L2≤5%；参考范数≤1e−12 时采用最大绝对误差≤0.002。全部检查还包含输出数量/顺序、未知值、舍入、FIFO、超时及算子性质；流水线增加 TLAST、握手背压稳定和完成状态。'
startup='基础 Softmax、LayerNorm、RMSNorm 的首组零输入为 NaN。流水线的这三种及其 affine/masked 扩展共 6 种模式，在首组零输入出现 NaN；其余 5 组通过。四行随机补测中 Softmax 与 LayerNorm affine 的第 1 行也全为 NaN，后 3 行有限。因此问题与启动阶段相关，但尚未定位根因，不能断言只是全零输入问题，也不能据此推断板卡必然同样失败。'
seq='同一模式的用例按顺序运行。行前复位顶层控制/FIFO，不重启整个浮点 IP 模型；用例名 cold 指这一复位流程。第 6 组保留输入重启，第 5 组含加载空拍和输出背压。四行补测独立启动 XSim。'
boundary='基础 SiLU/GELU 的 −16 输入相对 L2=1，但最大绝对误差仅约 1.8e−6/2.4e−11；未事后放宽阈值。直接阵列输入停顿时二者出现 384 拍输出与 FIFO 故障；新版顶层的加载停顿/输出背压检查均通过，这两个接口的测试条件不同。'
timing='基础组延时从首输入上升沿采样计到首/末输出；每周期 10 ns，不含复位和 GEMM。下表流水线组从 start 采样计时，包含 GEMM 与后处理，不含 A/B/辅助参数加载；CSV 另存首 A 输入至末输出，包含加载等待。下列值取无停顿常规用例；即使数值为 NaN 也保留其到达延时，不能将延时完成等同功能通过。'
plot='共 15 张图，每张为整体三折线、同一组的局部放大、共同有限常规集合的三组 MAE、全部用例逐组误差。局部纵轴按数据范围收紧；重合如实标注。例图预先固定正斜坡，未按误差挑选。延时只列文字/表格。提供 400 dpi PNG 与矢量 PDF、SVG。'
def mdtable(h,rows):return '\n'.join(['|'+'|'.join(h)+'|','|'+'|'.join(['---']*len(h))+'|',*['|'+'|'.join(map(str,r))+'|' for r in rows]])
parts=['# BF16 算子验证说明','2026-10-26 BF16 算子测试记录','## 1. 范围与数值口径',scope,ref,criterion,seq,'## 2. 基础五种算子',mdtable(bh,bt),startup,boundary,'## 3. 新版十种模式：M=1',mdtable(ih,it),'60 组单行检查中，54 组通过全部检查，60 组协议检查通过。常规统计与探测统计分列，不能称全部通过。','## 4. 四行生产分帧补测',mdtable(mh,mt),'这 4 组仅覆盖所列模式的一组随机输入，不等于十种模式的完整 M=4 验证。','## 5. 延时说明',timing,mdtable(lh,lt),'## 6. 图表与原始证据',plot,'NaN 不作为 0 误差。柱图只使用三者共同有限的常规用例，并标出数量；全体含 NaN 时总 MAE 未定义。额外输出不裁掉。图中红色标记与 CSV 保留所有失败。','图表入口：../../../../picture/bf16/index.html。每个模式的 results 子目录含原始 samples/summary CSV、xsim.log、validation.wdb。逐元素 F/Q/R 也已导出。输入和数值参考位于包根目录 data/bf16。数据、判据和导入源码哈希见 provenance.json、original_sources_sha256.json；文件清单见包根目录 build/package_manifest.json。','## 7. 全部失败与边界探测明细']
fh=['层级','算子','用例号（从1）','输入/类别','全部检查','有限值','协议','相对L2','最大绝对误差']
fr=[]
for g in bc:
 if not yes(g['case_ok']) or g['category']!='nominal':fr.append(['基础',g['operator'],str(int(g['case_id'])+1),g['name'],'通过' if yes(g['case_ok']) else '失败',g['finite'],g['protocol_ok'],fmt(g['R_Q_relative_l2']),fmt(g['R_Q_max_abs'])])
for g in ic:
 if not yes(g['case_ok']) or g['category']!='nominal':fr.append(['流水线 M='+g['rows'],g['operator'],str(int(g['case_id'])+1),g['name'],'通过' if yes(g['case_ok']) else '失败',g['finite'],g['protocol_ok'],fmt(g['R_Q_relative_l2']),fmt(g['R_Q_max_abs'])])
parts+=[mdtable(fh,fr),'## 8. 复现','详见包根目录 readme.md。scripts/run_all.ps1 执行全部流程；修改图形后只运行 scripts/plot_paper.py 即可重画，不需要板子。独立 testbench 在 sim/，GUI 工程由 scripts/create_all_projects.tcl 按需生成。','图形组织参考 SoftEx（https://arxiv.org/abs/2412.06321）的简洁子图和统一图例，本包只使用自己的仿真数据。']
(P/'validation_report.md').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
if options.markdown_only:
 print("Created validation_report.md")
 raise SystemExit(0)
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

doc=Document();sec=doc.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
for st in doc.styles:
 for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
sec.top_margin=sec.bottom_margin=Inches(.8);sec.left_margin=sec.right_margin=Inches(1)
normal=doc.styles['Normal'];normal.font.name='Microsoft YaHei';normal._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei');normal.font.size=Pt(10.5);normal.paragraph_format.space_after=Pt(7);normal.paragraph_format.line_spacing=1.15
for sn,size in [('Title',20),('Heading 1',14),('Heading 2',12)]:
 st=doc.styles[sn];st.font.name='Microsoft YaHei';st._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei');st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
header=sec.header.paragraphs[0];header.text='BF16 算子验证 仿真记录与图表说明';header.runs[0].font.size=Pt(8);header.runs[0].font.color.rgb=RGBColor(0,0,0)
footer=sec.footer.paragraphs[0];footer.alignment=2
footer.add_run('第 ');fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld);footer.add_run(' 页')
def para(t):doc.add_paragraph(t)
def table(h,rows,widths):
 t=doc.add_table(rows=1,cols=len(h));t.autofit=False
 for c,w in zip(t.columns,widths):c.width=Inches(w)
 for c,v in zip(t.rows[0].cells,h):c.text=str(v)
 rep=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(rep)
 for row in rows:
  for c,v in zip(t.add_row().cells,row):c.text=str(v)
 for ri,row in enumerate(t.rows):
  cant=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(cant)
  for ci,c in enumerate(row.cells):
   c.width=Inches(widths[ci]);pr=c._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
   for side in ['top','left','bottom','right']:
    el=OxmlElement('w:'+side);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');b.append(el)
   pr.append(b)
   if ri==0:
    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'F2F2F2');pr.append(sh)
   for p in c.paragraphs:
    if ci>0:p.alignment=1
    p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1.05
    for run in p.runs:run.font.size=Pt(9);run.bold=ri==0
 doc.add_paragraph().paragraph_format.space_after=Pt(0)
doc.add_heading('BF16 算子验证说明',0);para('2026-10-23 | 原工程未修改 | 共 194 组仿真检查')
doc.add_heading('一 测试范围与比较口径',1)
for txt in [scope,ref,criterion,seq]:para(txt)
doc.add_heading('二 基础五种算子的常规输入测试',1);table(bh,bt,[1.25,.7,1.2,1.2,2.15]);para(boundary)
doc.add_page_break();doc.add_heading('三 新版十种模式的单行测试',1);para('每种 4 组常规输入 + 2 组协议/重复启动探测。60 组中 54 组通过全部检查；协议检查 60/60。')
table(ih,it,[2.25,1.05,1.05,1.05,1.1]);para(startup)
doc.add_heading('四 四行生产配置随机补测',1);table(mh,mt,[1.6,.8,2.5,1.6]);para('每行应有 768 个有限元素。以上 4 组仅测试所列模式的一组随机输入，不构成完整 M=4 覆盖；GEMM 和 SwiGLU 通过。')
doc.add_page_break();doc.add_heading('五 延时记录',1);para(timing);table(lh,lt,[2.0,1.5,1.5,1.5])
doc.add_heading('六 图表与复现',1);para(plot);para('NaN 不当成零误差；统计集合和失败标记均明确保留。三曲线的格式差异由 Q−F 解释，硬件计算偏差由 R−Q 解释。')
para('打开包根目录 picture/bf16/index.html 浏览全部图片；打开 readme.md 查看工程、波形及重跑步骤。完整逐组结果见 report/case_metrics.csv 与 integrated_case_metrics.csv，延时按周期记录，可乘 10 得 ns。')
para('本说明不证明所有输入均正确。源码、原始捕获、波形、逐元素对照、失败明细均随包提供，便于复查。')
doc.save(P/'validation_report.docx')
print('Created validation_report.md and validation_report.docx')
