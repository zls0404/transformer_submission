# 数值、性能与实现报告

## 数值

先检查帧结构，再算误差。actual/reference 元素数相同、索引连续；不裁多余输出、不补缺失输出、不删除异常组。不用广播或 zip 截断掩盖结构错误。

float 读取十进制 value；integer 解码 code×2^(-fraction_bits)；bf16 解码 uint16 原始位。十六进制带 0x 前缀；BF16 与 FP16 不同。

compare 判据为 `abs(actual-reference) <= atol + rtol*abs(reference)`，给出 MAE、RMSE、最大绝对误差、相对 L2。参考全零且误差非零时相对 L2 未定义，用 null；任何 NaN/Inf 都失败，保留索引，聚合误差不写成零。

三值比较分别运行 Q-F、R-F、R-Q。F 为明确的数学目标；Q 注明是逐位算法模型还是格式量化；R 为真实捕获。Q-R 一致不等于数学精度合格，格式参考不一致也不自动等于 RTL 错误。

阈值在测试前由应用需求确定，记录绝对、相对和近零处理。GELU 需说明 erf/tanh/sigmoid 等实现。图中保留原坐标，放大只改变坐标范围，不平移曲线，重合如实标注。

## 性能

CSV 每行保存原始样本，不混单位。声明起终点、输入规格、精度、CPU/板卡、PL 时钟、软件版本、预热和重复次数、是否含 Overlay 加载、输入和输出 DMA。

stats 按 `(n-1)*q` 线性插值，报告 count、mean、总体 std、P50/P95/P99/max。少于100样本提示尾延时证据不足，不丢高值。预热排除规则预先约定，预热数据另存。

transaction_us 包括有序 MMIO/DMA 与主机轮询，不含下载、分配、CSV 读写；total_host_us 包括本次封装从加载开始的主机时间。二者都不是纯 PL 周期；纯计算需硬件计数器、读回同步与溢出处理。

比较需相同输入、尺寸、精度目标和计时范围。ARM NumPy 与桌面 CPU、首次上传与复用输入、完整模型与单算子，不能混算加速比。条件不同则分列。

## Vivado

reports 面向英文文本，已对本工程 2026.1 7-series 格式验证。资源行支持 Slice/CLB LUTs、Slice/CLB Registers、Block RAM Tile、DSPs。其他器件/版本格式需复测；缺字段失败，不能按0填。

核对器件、setup/hold/pulse width slack 和失败数、无时钟寄存器、资源上限、DRC Error。Warning/Critical Warning 分列。通过静态检查不代表复位、TLAST、背压、缓存或数学函数正确。

assets/measurement_context.json 用于补充环境；未采集字段保留 null。原始数据登记哈希，模拟、RTL 与板端结果分列，模拟延时不作为性能成绩。
