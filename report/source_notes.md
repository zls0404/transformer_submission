# 来源与依赖说明

计算 RTL 和 PS 侧程序来源于提供的 INT8/BF16 工程；导入身份和源码哈希保存在 build/imported_sources.json。文件保留原注释及版权头，计算逻辑未在本轮清理中修改。

PS7 预设提取自 PYNQ v3.0.1 的 Pynq-Z2 硬件 Tcl，来源及原有 BSD-3-Clause 标识见 build/ps7_provenance.md。浮点 IP 的 XCI 与仿真接口由 Vivado 2026.1 生成，原有厂商声明保留；仿真使用 Vivado 自带预编译库。

主机分析依赖 NumPy、Matplotlib、Pillow；BF16 报告生成脚本另使用 python-docx。版本下限见各 sim 目录 requirements.txt。提交包不内置 Python 依赖、Vivado 安装程序或预编译运行库。

原工程未提供覆盖全部文件的统一开源许可声明，未替第三方文件新增统一授权。公开仓库地址与整体许可证不属于本包已经提供的材料。
