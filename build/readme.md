# 构建说明

工具版本为 Vivado 2026.1。run_build.ps1 的 Precision 选择 int8/bf16，Stage 选择 project/synth/bitstream；VivadoExe 可指定实际安装路径。Tcl 从自身位置解析源码路径，无需原作者的工程目录。

```text
vivado -mode batch -source build/create_project.tcl -tclargs int8
vivado -mode batch -source build/create_project.tcl -tclargs bf16
vivado -mode batch -source build/build.tcl -tclargs int8 bitstream
vivado -mode batch -source build/build.tcl -tclargs bf16 bitstream
```

生成工程位于 generated/<precision>，综合实现报告写入 reports/<precision>/rebuild，产物导出到 ../board/<precision>/rebuilt。bitstream 阶段检查 setup、hold 和 DRC 错误后再替换导出文件；静态报告不代表功能或板端验证。

INT8 默认 USE_POW2_SOFTMAX=0，实际使用 baseline Softmax。ISCAS 两种版本用于候选算法对照。两个目标使用 PYNQ 官方 Z2 PS7 预设，来源见 ps7_provenance.md；各自 BD 保留其 DMA 宽度、地址和参数。

reports/int8/rebuild 保存 INT8 的完整实现报告，reports/bf16/previous_package_rebuild 保存 BF16 的既有完整实现报告。BF16 报告目录的历史名称表示来源，不表示重新完成了板端回归。2026-10-26 的工程重建检查单独记录在 ../report/verification。

Windows 下应使用短英文路径。构建过程中生成的 generated、IP 缓存、.Xil 与仿真编译目录可重新生成，不应作为复现源码提交。
