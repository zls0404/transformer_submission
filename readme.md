# 基于 PYNQ-Z2 的 Transformer 核心算子加速系统

目标板卡为 PYNQ-Z2，器件 xc7z020clg400-1，PL 配置时钟 100 MHz。工程提供 INT8 和 BF16 两个独立构建目标，分别加载对应 Overlay。当前实现覆盖算子及其组合，不包含单比特流精度切换和完整 Transformer 网络部署。

|目录|内容|
|---|---|
|src/int8、src/bf16|计算 RTL、IP 配置、AXI 封装及 PS 侧 Python|
|sim/int8、sim/bf16|测试平台、预设输入、参考结果、RTL 捕获、波形和分析脚本|
|build|从源码建立工程的 Tcl、主机入口及综合实现报告|
|board|配套 bit/hwh、板端程序及实测日志|
|data|测试输入、数值参考、可读参考 CSV 和板测参考数据|
|picture|20 张验证图，含高清 PNG、SVG、PDF 和浏览入口|
|skill|通用 PYNQ 技能、接口契约、执行/检查脚本与验证记录|
|report|设计说明、验证状态、已知问题和大模型协作记录|

## 建立工程

使用 Vivado 2026.1，解压到较短的英文路径。在工程根目录执行：

```powershell
./build/run_build.ps1 -Precision int8 -Stage project
./build/run_build.ps1 -Precision bf16 -Stage project
```

Vivado 安装位置不同时，通过 -VivadoExe 指定 vivado.bat。完整构建使用 -Stage bitstream，仅综合使用 -Stage synth。生成工程为 build/generated/<precision>/<precision>_z2.xpr；新导出的配套文件位于 board/<precision>/rebuilt。

在 Vivado Tcl Console 中也可设置 `set ::target_precision int8` 或 `bf16`，再 `source build/create_project.tcl`。运行时须关闭其他工程。更多参数见 [构建说明](build/readme.md)。

## 验证与运行

主机分析依赖可运行 `python -m pip install -r sim/int8/operator_validation/requirements.txt -r sim/bf16/operator_validation/requirements.txt` 安装。板端 PYNQ 环境使用对应板卡镜像。

- [INT8 仿真](sim/int8/operator_validation/readme.md)：矩阵乘法、三种 Softmax、标量 GELU 和 SIMD 背压探测。
- [BF16 仿真](sim/bf16/operator_validation/readme.md)：五种基础模式、十种 GEMM/后处理模式及四行补测。
- [INT8 上板](board/int8/readme.md)、[BF16 上板](board/bf16/readme.md)：文件配套与运行口径。
- [验证图表](picture/index.html)：原值三曲线、局部放大、误差及失败标记。
- [通用技能](skill/readme.md)：独立于计算 IP 的 Overlay、DMA、数值与实现报告检查。

现有测试保留失败。INT8 SIMD GELU 背压探测记录 4 次保持违例；BF16 194 组中 179 组通过、15 组未通过。完整范围见 [工程状态](report/project_status.md) 和 [已知问题](report/known_issues.md)。

BF16 results/bench_log.txt 对应 board/bf16 根目录的既有板测产物，不能套用到 rebuilt 中的产物。随包提供的重建产物没有新的同等板端回归记录。

## 报告与文件核验

[设计说明](report/design_report.md) 给出系统结构、接口、数值口径和实现取舍。[协作记录](report/ai_collaboration.md) 保留实际需求与自我纠错选段。build/package_manifest.json 登记交付文件的大小和 SHA-256；构建缓存、编译目录、GUI 临时工程及无用生成副本不属于交付源码。

文件完整性可运行 `python -B build/verify_package.py` 检查。该命令同时展示保留的功能失败数量，文件核验通过不等于功能全部通过。
