# PS7 配置来源

两个构建目标使用 PYNQ 官方仓库 v3.0.1 的 Pynq-Z2 硬件脚本中的 PS7 参数，原脚本版权为 Xilinx 2022，许可证标识 BSD-3-Clause。HP0～HP2、GP0 和 PL 100 MHz 在各自 BD 脚本中配置。

来源：https://github.com/Xilinx/PYNQ/blob/v3.0.1/boards/Pynq-Z2/petalinux_bsp/hardware_project/pynqz2.tcl

原 INT8 BD 的 PCW_PACKAGE_NAME 为 ffg900，新构建为 clg400。DDR 总线宽度不能凭封装字段推断为适配错误，官方 Z2 配置本身使用 16 Bit 参数；该参数未擅自改为 32 Bit。
