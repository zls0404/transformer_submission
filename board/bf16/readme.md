# BF16 板端文件

本目录根部 design_1.bit 与 design_1.hwh 对应 results/bench_log.txt 中的既有上板记录。rebuilt 中为重新构建的另一组配套文件，尚无同等板端回归。bit/hwh 必须使用同一组。

将所选配套 bit/hwh 和 bench_snake_report.py 放到 PYNQ-Z2 同一目录，在具备 PYNQ 硬件访问权限的 Python 环境运行：

```text
sudo -E python3 -u bench_snake_report.py
```

测试活动输入为 (4,4)×(4,128)，填充至固定硬件输出 (4,768)。重复运算比较不含 A/B 首次上传，包含结果 DMA；CPU 基线为同板 ARM NumPy。脚本记录主机观测延时，不是纯 PL 周期或完整模型加速比。

原日志中十种模式在该输入和预设相对 L2≤0.05 的口径下通过。其他输入、控制复位、首帧和空拍边界仍以 ../../report/known_issues.md 为准。
