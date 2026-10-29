# INT8 算子测试

本目录测试当前源码中的 MM_ultra、baseline Softmax、ISCAS 串行/并行候选版本、标量 GELU 和四通道 GELU 封装。时钟周期为 10 ns。测试不经过 PS、DDR 或 DMA。

## 运行

在 PowerShell 中执行 scripts/run_tests.ps1。默认使用 D:/vivado/2026.1/Vivado/bin，可用 VivadoBin 参数修改。该脚本重新生成 raw 中的捕获和波形，不会改动 RTL。

Python 安装 requirements.txt 中的依赖后，执行 `python scripts/analyze_plot.py`，重新计算误差并输出到包根目录 picture/int8。参考函数在 scripts/reference.py；包根目录 data/int8 中保留测试开始前确定的输入和参考结果。

## 测试内容

|对象|条件|检查内容|
|---|---|---|
|三种 Softmax|100 组，N=32/64/128/192/320，输入 Q6，输出 Q7|输出数量、TLAST、未知值、误差及延时|
|标量 GELU|Q0～Q14，每种遍历 -128～127|全部 3,840 个编码与定点模型比较|
|MM_ultra|16 组，M=4～32，K=16～64，N=16～64|逐元素舍入/饱和、输出顺序、数量、TLAST；后 8 组有输入空拍和输出背压|
|四通道 GELU|32 个输入拍，输出暂停 8 周期|输出在 valid=1、ready=0 后能否保持|

矩阵乘法配置按数值变化采样，因此测试先用零配置等待，再切换到本组参数。输出数据按握手采样。标量 GELU 无 ready/valid 接口，用 8 级有效标记对齐输出，首输入采样至首结果为 7 个周期差。

baseline Softmax 的 Q 是量化输入经理想 Softmax 后舍入到 INT8 的格式参考，不是其 Exp/Ln 近似电路的逐位模型。该对象只判定分帧、数量和未知值检查；数值误差单独报告，暂未制定模型精度验收阈值。ISCAS、GELU 和矩阵乘法使用各自定点参考做逐元素比较。

## 查看结果

raw 保存实际仿真捕获和四个 WDB 波形；report/case_metrics.csv 保存逐组结果和延时。图表入口为 ../../../../picture/int8/index.html。失败项见包根目录 report/known_issues.md。

在 Vivado Tcl Console 中，使用 `open_wave_database` 打开 raw 中对应的 .wdb，再执行 `add_wave -r /*`。编译目录 build/xsim 可以重新生成，不属于提交文件。
