# BF16 算子验证说明

2026-10-26 BF16 算子测试记录

## 1. 范围与数值口径

Vivado/XSim 2026.1，10 ns 时钟。基础五种配置直接驱动原共享 Snake 非线性阵列；新版十种模式驱动未修改的 snake_acc_top，单行 M=1、K=4、N=768。另选 4 种模式测试生产配置 M=4、K=4、N=768。排除 PS、DDR、DMA，未测试面积、功耗、Fmax 或完整模型准确率。

F 为原始浮点输入的数学参考；Q 为 BF16 解码输入的数学参考，并按实际 BF16 接口边界舍入；R 为真实 RTL 捕获输出。Q 使用 FP64 数学运算，不逐级模拟内部 FP32 IP。GELU 对照实现的 x·sigmoid(1.7017449140548706x)。

预设数值判据：R 对 Q 的相对 L2≤5%；参考范数≤1e−12 时采用最大绝对误差≤0.002。全部检查还包含输出数量/顺序、未知值、舍入、FIFO、超时及算子性质；流水线增加 TLAST、握手背压稳定和完成状态。

同一模式的用例按顺序运行。行前复位顶层控制/FIFO，不重启整个浮点 IP 模型；用例名 cold 指这一复位流程。第 6 组保留输入重启，第 5 组含加载空拍和输出背压。四行补测独立启动 XSim。

## 2. 基础五种算子

|算子|全部检查|首输出/周期|末输出/周期|有限输出最大 |R−Q||
|---|---|---|---|---|
|Softmax|23/24|507|698|6.10352e-05|
|LayerNorm|23/24|330|521|0|
|RMSNorm|23/24|317|508|0|
|SiLU|23/24|79|270|0.03125|
|Sigmoid GELU|23/24|79|270|0.015625|

基础 Softmax、LayerNorm、RMSNorm 的首组零输入为 NaN。流水线的这三种及其 affine/masked 扩展共 6 种模式，在首组零输入出现 NaN；其余 5 组通过。四行随机补测中 Softmax 与 LayerNorm affine 的第 1 行也全为 NaN，后 3 行有限。因此问题与启动阶段相关，但尚未定位根因，不能断言只是全零输入问题，也不能据此推断板卡必然同样失败。

基础 SiLU/GELU 的 −16 输入相对 L2=1，但最大绝对误差仅约 1.8e−6/2.4e−11；未事后放宽阈值。直接阵列输入停顿时二者出现 384 拍输出与 FIFO 故障；新版顶层的加载停顿/输出背压检查均通过，这两个接口的测试条件不同。

## 3. 新版十种模式：M=1

|模式|常规通过|全部通过|协议通过|非有限用例|
|---|---|---|---|---|
|GEMM|4/4|6/6|6/6|0|
|Softmax|3/4|5/6|6/6|1|
|LayerNorm|3/4|5/6|6/6|1|
|RMSNorm|3/4|5/6|6/6|1|
|SiLU|4/4|6/6|6/6|0|
|Sigmoid GELU|4/4|6/6|6/6|0|
|LayerNorm affine|3/4|5/6|6/6|1|
|RMSNorm affine|3/4|5/6|6/6|1|
|Masked Softmax|3/4|5/6|6/6|1|
|SwiGLU|4/4|6/6|6/6|0|

60 组单行检查中，54 组通过全部检查，60 组协议检查通过。常规统计与探测统计分列，不能称全部通过。

## 4. 四行生产分帧补测

|四行随机补测|全部检查|各行有限元素数|start→末输出/周期|
|---|---|---|---|
|GEMM|通过|768 / 768 / 768 / 768|56836|
|Softmax|未通过|0 / 768 / 768 / 768|60723|
|LayerNorm affine|未通过|0 / 768 / 768 / 768|60083|
|SwiGLU|通过|768 / 768 / 768 / 768|117771|

这 4 组仅覆盖所列模式的一组随机输入，不等于十种模式的完整 M=4 验证。

## 5. 延时说明

基础组延时从首输入上升沿采样计到首/末输出；每周期 10 ns，不含复位和 GEMM。下表流水线组从 start 采样计时，包含 GEMM 与后处理，不含 A/B/辅助参数加载；CSV 另存首 A 输入至末输出，包含加载等待。下列值取无停顿常规用例；即使数值为 NaN 也保留其到达延时，不能将延时完成等同功能通过。

|模式|start→首输出/周期|start→末输出/周期|start→末输出/μs|
|---|---|---|---|
|GEMM|75|14209|142.09|
|Softmax|14989|15180|151.80|
|LayerNorm|14812|15003|150.03|
|RMSNorm|14799|14990|149.90|
|SiLU|14561|14752|147.52|
|Sigmoid GELU|14561|14752|147.52|
|LayerNorm affine|14829|15020|150.20|
|RMSNorm affine|14816|15007|150.07|
|Masked Softmax|14989|15180|151.80|
|SwiGLU|29251|29442|294.42|

## 6. 图表与原始证据

共 15 张图，每张为整体三折线、同一组的局部放大、共同有限常规集合的三组 MAE、全部用例逐组误差。局部纵轴按数据范围收紧；重合如实标注。例图预先固定正斜坡，未按误差挑选。延时只列文字/表格。提供 400 dpi PNG 与矢量 PDF、SVG。

NaN 不作为 0 误差。柱图只使用三者共同有限的常规用例，并标出数量；全体含 NaN 时总 MAE 未定义。额外输出不裁掉。图中红色标记与 CSV 保留所有失败。

图表入口：../../../../picture/bf16/index.html。每个模式的 results 子目录含原始 samples/summary CSV、xsim.log、validation.wdb。逐元素 F/Q/R 也已导出。输入和数值参考位于包根目录 data/bf16。数据、判据和导入源码哈希见 provenance.json、original_sources_sha256.json；文件清单见包根目录 build/package_manifest.json。

## 7. 全部失败与边界探测明细

|层级|算子|用例号（从1）|输入/类别|全部检查|有限值|协议|相对L2|最大绝对误差|
|---|---|---|---|---|---|---|---|---|
|基础|softmax|1|zeros|失败|False|True|未定义|未定义|
|基础|softmax|25|gap_probe_normal|通过|True|True|0.000878177|3.05176e-05|
|基础|softmax|26|extended_range_96|通过|True|True|5.70909e-11|1.45519e-11|
|基础|layernorm|1|zeros|失败|False|True|未定义|未定义|
|基础|layernorm|25|gap_probe_normal|通过|True|True|0|0|
|基础|layernorm|26|extended_range_96|通过|True|True|0|0|
|基础|rmsnorm|1|zeros|失败|False|True|未定义|未定义|
|基础|rmsnorm|25|gap_probe_normal|通过|True|True|0|0|
|基础|rmsnorm|26|extended_range_96|通过|True|True|0|0|
|基础|silu|23|constant_minus_16|失败|True|True|1|1.80304e-06|
|基础|silu|25|gap_probe_normal|失败|True|False|未定义|未定义|
|基础|silu|26|extended_range_96|通过|True|True|8.07422e-06|0.0078125|
|基础|gelu|23|constant_minus_16|失败|True|True|1|2.39879e-11|
|基础|gelu|25|gap_probe_normal|失败|True|False|未定义|未定义|
|基础|gelu|26|extended_range_96|通过|True|True|7.19621e-06|0.0078125|
|流水线 M=1|gemm|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|gemm|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=1|softmax|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|softmax|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|softmax|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=4|softmax|4|cold_random|失败|False|True|未定义|未定义|
|流水线 M=1|layernorm|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|layernorm|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|layernorm|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=1|rmsnorm|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|rmsnorm|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|rmsnorm|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=1|silu|5|random_input_bubbles_output_backpressure|通过|True|True|0.00133585|0.00195312|
|流水线 M=1|silu|6|retained_input_repeat|通过|True|True|0.00133585|0.00195312|
|流水线 M=1|gelu|5|random_input_bubbles_output_backpressure|通过|True|True|0.0011794|0.000976562|
|流水线 M=1|gelu|6|retained_input_repeat|通过|True|True|0.0011794|0.000976562|
|流水线 M=1|layernorm_affine|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|layernorm_affine|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|layernorm_affine|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=4|layernorm_affine|4|cold_random|失败|False|True|未定义|未定义|
|流水线 M=1|rmsnorm_affine|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|rmsnorm_affine|5|random_input_bubbles_output_backpressure|通过|True|True|0|0|
|流水线 M=1|rmsnorm_affine|6|retained_input_repeat|通过|True|True|0|0|
|流水线 M=1|masked_softmax|1|cold_zeros|失败|False|True|未定义|未定义|
|流水线 M=1|masked_softmax|5|random_input_bubbles_output_backpressure|通过|True|True|0.00125957|1.52588e-05|
|流水线 M=1|masked_softmax|6|retained_input_repeat|通过|True|True|0.00125957|1.52588e-05|
|流水线 M=1|swiglu|5|random_input_bubbles_output_backpressure|通过|True|True|0.00118957|0.000244141|
|流水线 M=1|swiglu|6|retained_input_repeat|通过|True|True|0.00118957|0.000244141|

## 8. 复现

详见包根目录 readme.md。scripts/run_all.ps1 执行全部流程；修改图形后只运行 scripts/plot_paper.py 即可重画，不需要板子。独立 testbench 在 sim/，GUI 工程由 scripts/create_all_projects.tcl 按需生成。

图形组织参考 SoftEx（https://arxiv.org/abs/2412.06321）的简洁子图和统一图例，本包只使用自己的仿真数据。
