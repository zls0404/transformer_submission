# 设计源码

int8/ip_repo 与 bf16/ip_repo 为自定义计算 IP；各自 ps 目录为板端 Python 程序。build 中的 Tcl 从这些源码建立工程，board 中的程序是方便独立上传的部署副本。

sim/bf16/operator_validation/rtl 保存仿真对应的验证快照，文件哈希登记在该目录 original_sources_sha256.json。修改计算 RTL 后需要重新同步、仿真和构建，已有捕获不能自动代表修改后的电路。
