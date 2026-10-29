# 接口契约

契约是 JSON 数据，不执行 Python 表达式、Shell 命令或回调。修改数值和名称可用于其他核心，步骤语义仍以该核心接口说明为准。

|字段|含义|
|---|---|
|schema_version|当前为 1|
|name|测试名称|
|target_part|实际器件，含封装和 HWH 可提供的速度等级|
|artifacts.bit / hwh|相对于 artifact-root 的路径；未指定时相对于契约位置|
|artifacts.sha256|bit、hwh 的 SHA-256；离线检查可缺省，物理执行必填|
|buffers|按名字定义 shape、dtype、direction，输入还需 file；可绑定输入 CSV 的 sha256|
|registers|按名字定义 ip、offset、access；offset 为 IP 内字节偏移，32 位对齐|
|steps|有序 write、read、poll、dma 步骤|

整数输入 CSV 为 index,code，浮点为 index,value。index 从 0 连续递增，拒绝重号、缺号、重排和空表。BF16 搬运使用 uint16 原始编码，不把 float16 当作 BF16。

dtype 支持 int8/uint8/int16/uint16/int32/uint32/float32/float64；shape 为 1～4 个正整数。超界输入报错，不隐式回绕。

## 步骤

write 指定 register、uint32 value；read 指定 register；poll 指定 register、mask、equals、timeout_s，判断 `(value & mask) == equals`。poll、dma 必须显式给出 (0,3600] 秒超时。

DMA 的 transfers 每项含 ip、direction（send/recv）、buffer。每个并发阶段同一通道只用一次，每个 buffer 在一次事务中只搬运一次。多次加载用不同 buffer 名，保留所有权边界。

并发阶段内先启动全部接收，再启动发送。只有可同时就绪的流才放在同一组。若需要先上传权重并等待，再配置，再上传特征，应拆开步骤，不能靠通用执行器猜依赖。

HWH 必须能唯一识别该 IP 的寄存器窗口。缺失或多义时直接拒绝，不能猜一个大窗口。

read/poll 可能有副作用，特别是 clear-on-read 的 done。只声明必要读取，不自动扫描寄存器。完整字段含义以 RTL、HLS 控制协议和实际 register_map 为准。

## 字节、对齐和分帧

字节数为 shape×dtype 字节数。核对 HWH 的 SG、Micro DMA、通道启用、长度位宽、MM AXI 宽度、DRE、地址位宽。BTT 上限使用 `(1 << width) - 1`；16 位字段不能写入 65536。

DRE 未启用时，地址按该方向 MM AXI 数据宽度对齐；物理地址加长度不能超出 DMA 地址范围。长度通过不代表算法缓存足够，行列计数、tile 和缓存深度需按核规格另查。

TLAST 应对应帧末尾，尾拍需正确 TKEEP。未经验证的分段传输可能引入额外 TLAST，让地址归零或计算提前启动。

输入在加载硬件之前只读入一次，报告登记实际使用快照的 SHA-256 和字节数。绑定后输入哈希不匹配时拒绝执行。

assets/contracts/loopback.json 与 vector_add.json 展示不同应用共用执行器。回环硬件由 create_loopback.tcl 加目标板预设构建；向量加法电路由使用者提供。
