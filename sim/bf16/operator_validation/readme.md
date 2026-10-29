# BF16 算子测试

测试范围包括五种共享非线性阵列模式、十种 GEMM/后处理模式和四组 M=4 分帧检查。原始结果共 194 组，其中 179 组通过、15 组未通过。判据与完整结果在 report/validation_report.md 和两个 case_metrics.csv 中。

rtl 与 ip 是本次结果对应的验证快照。综合使用包根目录 src/bf16/ip_repo；修改计算 RTL 后需同步验证快照并重新运行，不能沿用旧捕获。

## 运行

Python 依赖见 requirements.txt。在 PowerShell 中执行 scripts/run_all.ps1，或按脚本参数指定 PythonExe 和 VivadoRoot。各模式可分别用 scripts/run_validation.py、scripts/run_integrated.py 运行；它们会建立所需编译目录。

图表保存在包根目录 picture/bf16。执行 scripts/plot_paper.py 可根据现有捕获重画，不需要连接板子。图中 NaN 和失败用例均保留，延时见报告表格。

仿真工程不预先打包。需要 GUI 工程时，在空的 Vivado 会话中 source scripts/create_all_projects.tcl，脚本会在 gui 中建立各算子工程。波形保存在 results 各模式目录，文件名为 validation.wdb；打开 WDB 后可 source scripts/view_waves.tcl 添加常用信号。

本测试没有 PS、DDR 和 DMA。M=1 的测试用于隔离单行算子，M=4 补测只覆盖表中四种模式。完整模型推理、全部模式的生产参数覆盖和新比特流上板复测尚未完成。

测试输入和参考数组统一位于包根目录 data/bf16；逐元素参考 CSV 位于 data/bf16/reference。结果和波形仍保存在本测试目录的 results。
