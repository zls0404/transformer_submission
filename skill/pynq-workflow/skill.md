---
name: pynq-workflow
description: Build, validate and troubleshoot PYNQ overlays, interface contracts, simple AXI DMA transfers and reproducible measurements on Zynq boards. Use for PS/PL integration and test evidence; supply each design's board, IP names, registers and framing explicitly.
---

# PYNQ 工程构建与验证

将算法接口、Overlay 和板端调用对应起来，输出可追溯的测试证据。换题目时修改接口契约和黄金参考；换板卡时重新构建该板的 Overlay、核对 PYNQ 环境，再做板测。不要把一块板的 PS7、时钟、引脚或比特流直接套到另一块板。

## 从哪一步开始

- 核对提交文件、板型或 IP：运行 scripts/pynq_tool.py inspect；先读[接口契约](references/contract.md)。
- 编写主机调用、检查 DMA 卡住：读[运行与 DMA](references/runtime.md)，按契约使用 scripts/run_contract.py。
- 核对精度、延时或资源：读[测量口径](references/measurement.md)，使用 compare、stats、reports 子命令。
- 根据现象定位问题：查[故障与来源](references/failures.md)，只打开与当前症状有关的记录。
- 需要从任务描述整理接口或分析报告：使用[工作流模板](references/workflows.md)。

完整命令、依赖和验证结果见本目录[readme.md](readme.md)。脚本不依赖当前 Transformer 工程名、固定物理地址或绝对路径。

## 保留的工程约束

1. 先确认用户任务是离线检查、构建还是上板执行。检查和规划不下载 Overlay，不扫描寄存器，不自动连接 SSH。用户要求上板运行时，在已有授权范围内执行对应步骤；缺少板型或关键协议时只补问缺失项。
2. 从同一次构建导出 bit、hwh，保存哈希。文件同名、器件相同只能排除部分错误，不能证明两者来自同一构建。硬件运行入口要求契约中的配套哈希。
3. 从 HWH 和 RTL/接口说明确认 IP 层次名、寄存器地址、读写副作用、编码、字节数、TLAST、启动顺序和完成条件。不要从已有 Python 文件名猜实际综合路径，也不要只凭 register_map 名称推断控制位。
4. 用 check 做静态检查；通过后仍需验证 PL 功能。DMA 长度、位宽、对齐或容量不满足时明确报错。只有硬件协议允许额外 TLAST 且经过测试时才能分段传输。
5. 每个 DMA 并发阶段先布置接收，再发输入；若设计需先加载权重，按协议拆成独立步骤。检查缓存同步、完成字节数、超时和缓冲区所有权。执行器只支持简单 AXI DMA，不支持 SG、Micro DMA、VDMA 或 CDMA。
6. 超时后保存状态，停止当前通道并有界等待 HALTED。未确认停机时保留异常对象和缓冲区，保持 Python 进程，不释放、不重用，不自动重启板卡或重新加载 PL。恢复由板级设计决定。
7. 数值结论同时检查元素数、顺序和非有限值。NaN、未知值、多余或丢失输出不能被过滤为“精度通过”。区分量化算法参考与理想格式参考；阈值来自数值规格，不因失败自行放宽。
8. 分开记录 Overlay 加载、首次上传、重复计算、结果 DMA、主机开销与纯 PL 周期。报告 P50/P95/P99/max，保留全部样本和预先声明的预热规则。条件不同的数据不能直接算加速比。

## 完成时交付

给出适用范围、契约/命令、工具版本、输入与产物哈希、原始捕获、检查结果、失败条件和下一步。区分离线检查、模拟后端、RTL 仿真和真实上板四类证据。没有真实板测时不能写成“跨板复用成功”。

已有工程沿用其构建 Tcl；独立回环可用 assets/create_loopback.tcl 配合实际板级预设建立。其他计算电路由具体工程提供，不将独立 Overlay 合并为单一双精度电路。首次运行及迁移见[复用验证步骤](references/reuse.md)。
