# INT8 板端文件

rebuilt/sys_soc.bit 与 sys_soc.hwh 是配套的 Z2 重建产物；同目录 Python 程序与 ../../src/int8/ps 保持一致。文件对应关系由 ../../build/package_manifest.json 登记。

在板端将配套 bit/hwh 和 mm.py、golden_model.py、test_acc.py、validate_acc.py 放入同一目录，按 test_acc.py 中的入口运行。驱动输入为二维 INT8，矩阵维度、DMA 长度与硬件缓存限制见 ../../report/known_issues.md。

该产物没有完整的新板端回归。独立算子仿真不代替 MM、Softmax、GELU、AXI-Lite 和 DMA 的系统联调。validate_acc_iscas.py 面向候选 Softmax，不能将其参考结果当作默认 baseline 的精度结论。

vit_numpy.py、vit_benchmark.py 和 export_vit_weights.py 是模型侧辅助程序。工程未附模型权重、完整输入或全网络 FPGA 部署结果。不得将这些脚本的存在视为完整模型已跑通。
