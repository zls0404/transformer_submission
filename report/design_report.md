# 基于 PYNQ-Z2 的 Transformer 核心算子加速系统设计说明

## 1. 目标与范围

Transformer 相关计算包括矩阵乘法、Softmax、归一化和激活函数。工程在 PYNQ-Z2 上组织 PS 侧 Python、DDR、DMA 和 PL 计算模块，提供 INT8 与 BF16 两套独立实现，研究不同数据格式下的算子计算、接口与验证方法。

INT8 采用定点缩放、舍入与饱和。BF16 使用 16 位浮点输入/输出及内部计算流水线。两套实现分别构建并加载，当前没有单比特流动态精度选择，也没有完整 Transformer 网络任务精度结论。

## 2. 系统结构与软硬件划分

|部分|职责|
|---|---|
|PS Python / PYNQ|准备输入、加载 Overlay、配置寄存器、组织 DMA、比较结果和计时|
|DDR 与 AXI DMA|保存输入/输出，连接存储访问与 AXI4-Stream|
|PL INT8|整数矩阵乘法、baseline Softmax、GELU 及 AXI 封装|
|PL BF16|BF16 GEMM、共享非线性阵列和扩展后处理模式|
|AXI-Lite 与 AXI4-Stream|分别承载控制状态与数据帧|

PS 负责灵活的任务组织与验证，PL 承担流水化计算。总体数据通路为 PS/DDR 经输入 DMA 进入计算核，再经结果 DMA 回到 DDR；AXI-Lite 单独配置控制与状态。INT8 使用 feature、weight、result 三条 DMA；BF16 使用 dma_a、dma_b、dma_out。

目标器件 xc7z020clg400-1，PL 100 MHz。PS7 来源为 PYNQ 官方 Z2 预设，时钟、复位、HP 端口和地址由 build 中 Tcl 明确建立。软件不得仅凭文件名猜寄存器语义；以源码及配套 HWH 为准。

## 3. 数据格式与计算接口

INT8 以 16×16 阵列和运行时块计数组织矩阵运算，Softmax/GELU 的缩放由寄存器配置。默认 USE_POW2_SOFTMAX=0。ISCAS 串行/并行实现是候选对照，不属于默认综合路径。

BF16 生产参数 M=4、K=4、N=768。模式覆盖 GEMM bypass、Softmax、LayerNorm、RMSNorm、SiLU、sigmoid GELU、affine 归一化、masked Softmax 和 SwiGLU。既有板测活动宽度为 128，填充到固定硬件帧。BF16 是原始 uint16 编码，不可用 NumPy float16 代替。

AXI4-Stream 按 valid/ready 握手，末拍通过 TLAST 标识。输入分段可能额外引入 TLAST，必须由核协议支持。INT8 DMA 长度字段为 16 位，单次上限 65535 字节；5 位块计数、缓存容量和对齐另行限制矩阵尺寸。详细限制与当前驱动覆盖见 known_issues.md。

## 4. 验证方法

测试同时保留数学参考 F、格式/算法参考 Q 与 RTL 捕获 R，分别统计 Q-F、R-F 和 R-Q。Q 与 R 一致只证明相应参考下的一致性，不自动证明任务精度。NaN、未知值、丢失/多余输出和协议失败均保留。

INT8 独立测试使用 10 ns 时钟，覆盖 100 组 Softmax、3840 个标量 GELU 编码、16 组矩阵乘法以及 SIMD 背压探测。baseline 的 Q 是格式参考，尚无对应内部 Exp/Ln 电路的完整位精确模型。

BF16 共 194 组：130 组基础、60 组单行集成、4 组四行补测。判据包含输出数量/顺序、有限值、TLAST、握手保持及数值误差。相对 L2 阈值为 0.05，近零参考另用预设绝对误差阈值。已有结果为 179 组通过、15 组失败，具体失败逐项记录在 known_issues.md 和 bf16_failed_cases.csv。

20 张图均以真实 RTL 捕获为来源，局部放大保持数值坐标。全量用例和异常索引保留在 CSV，延时记录独立于精度图。

## 5. 实现资源与时序

|实现|LUT|FF|DSP|BRAM36|WNS / ns|WHS / ns|
|---|---:|---:|---:|---:|---:|---:|
|INT8|14525|14270|205|77.5|0.286|0.019|
|BF16|27220|28870|199|14.5|0.023|0.023|

数据来自 build/reports 中的既有完整实现报告，DRC 错误均为 0，告警仍保留。两个实现分别占用器件，资源不能相加后解释为能够同时装入 Z2。两者的计算结构和测试任务不同，该表不是同任务优化前后的对比实验。

## 6. 板端结果与测量口径

board/bf16/results/bench_log.txt 为根目录配套产物的实际记录。该固定输入下十种模式通过脚本判据。CPU 为同板 ARM NumPy，重复计算排除 A/B 首次上传、包含结果 DMA。示例：GEMM+Softmax 的 CPU/FPGA 平均延时分别为 4536.22/1145.43 μs，比例 3.960；SwiGLU 为 6829.15/1701.08 μs，比例 4.015。

首次传输延时为 2064.04 μs，辅助帧一次性上传为 771.40 μs。该口径不是纯 PL 计算周期，也不是完整模型加速比。重建产物和 INT8 端到端流水线仍缺少对应的新板端回归，现有独立算子通过不能代替整系统通过。

## 7. 工程取舍与可复用能力

INT8 优先采用整数运算和显式缩放，BF16 扩展数据范围与算子模式。当前证据不足以给出同任务精度/性能优劣或优化前后收益，未编造缺失的基线数据。

构建由 Tcl 建立 PS/PL、DMA、地址和 IP，避免依赖 GUI 缓存。算子独立测试用于定位计算与协议问题，系统板测另行记录。通用 PYNQ Skill 抽取 Overlay 校验、接口契约、缓存/搬运、数值/性能及资源时序工具，验证范围与边界见 ../skill/pynq-workflow/validation/readme.md。

## 8. 复现与当前边界

从根目录 readme.md 开始，按 build/readme.md 建工程，按 sim 中各精度说明重跑仿真和图表，最后按 board 说明上传配套产物。测试原始数据、捕获、波形、图表及来源哈希随包保留。

现有工程存在首帧非有限值、空拍和背压等未解决问题；完整模型、功耗、任务精度和通用技能跨板实测没有完成。功能问题和覆盖缺口见 known_issues.md。大模型协作的需求、回答选段和纠错依据见 ai_collaboration.md。

测试输入、JSON/HEX/TXT/NPZ 数值参考和参考 CSV 均位于根目录 data；图片位于 picture，实际 RTL 捕获位于 sim 的 raw/results。来源和比较关系由 data/readme.md 说明。
