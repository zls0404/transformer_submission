# 测试输入与数值参考

本目录实际保存测试输入和数值参考。图片位于 ../picture；仿真实际输出 R 位于 ../sim 的 raw/results。参考结果是预期数值，不是图片。

|目录或文件|实际内容|用途|
|---|---|---|
|int8/softmax_cases.json、softmax_vectors.txt|100 组输入、缩放与参考编码|驱动 Softmax 仿真；区分 baseline 格式参考和 ISCAS 算法参考|
|int8/gelu_cases.json、gelu_vectors.txt|15 种缩放，每种 256 个 INT8 编码|标量 GELU 输入及精确编码参考|
|int8/mm_cases.json、mm_vectors.txt、mm_reference.npz|16 组矩阵输入、规格、浮点及量化结果|驱动矩阵乘法并逐元素比较|
|int8/reference/|Softmax、GELU、GEMM 三份可直接查看的参考 CSV|列出期望编码/数值与原始用例号|
|bf16/inputs.hex、gaps.hex、cases.json、input_vectors.csv|26 组基础输入和空拍标记|五种基础算子的共用输入|
|bf16/reference_data.npz|原始输入、BF16 输入和各算子的 F/Q 数组|基础算子数值参考|
|bf16/integrated/|A/B/辅助帧输入、用例和十种模式的 F/Q 数组|GEMM 与后处理模式测试|
|bf16/reference/|五种基础、十种集成模式的逐元素参考 CSV|可直接查看 F、Q 和预期 BF16 编码|
|board/bf16/|板测输入、软件期望输出及既有实测摘要|按保存脚本和种子重建参考；实测摘要从已有板端日志提取|
|provenance/int8_original_bd_config.json|原始板级配置快照|仅追溯来源，不作为当前 Z2 构建配置导入|
|input_manifest.json|19 个原始输入/参考文件的路径与 SHA-256|确认集中存放没有改变数据|
|reference_catalog.json|参考 CSV 行数、来源、类型和 SHA-256|区分软件期望与实测摘要|

## 参考值与实际结果的区别

F 为数学浮点参考，Q 为指定格式或算法下的数值参考，R 为实际 RTL 捕获。参考 CSV 主要列 F/Q 与预期编码，R 保存在 sim 的原始结果中。图片展示这些数据的比较，不替代数值文件。

INT8 baseline Softmax 的 Q 是格式参考，不能视为内部 Exp/Ln 电路的完整位精确模型。ISCAS、标量 GELU 和矩阵乘法使用各自声明的编码参考。BF16 的 Q 按已声明的接口边界舍入，不逐级模拟全部内部浮点运算。

BF16 pipeline 参考数组保存六组、四行的数学期望；实际 RTL 验证仍只有六组单行和四种模式的一组四行补测。存在参考数值不表示所有对应硬件配置都已测试。

## 板端参考

board/bf16/inputs.npz 与 references.npz 是从保存的 benchmark 脚本及固定种子重建的软件数据。expected_op_*.csv 同样是软件期望，不是新采集的 FPGA 输出。bench_summary.csv 的检查状态和延时来自 ../board/bf16/results/bench_log.txt，对应该目录根部的旧配套 bit/hwh。原始日志不包含全部逐元素硬件输出数组，未伪造补齐。

生成过程不连接板卡，输入前缀已与日志核对，来源哈希见 board/bf16/metadata.json。新增物理板测仍需单独执行。

## 查看与再生成

打开 int8/reference 或 bf16/reference 中的 CSV 即可查看参考数值。完整输入与参考数组继续使用原 JSON、HEX、TXT、NPZ 格式，19 个文件内容保持不变。

在工程根目录执行 `python -B build/export_reference_data.py` 可重新导出参考 CSV 和板测软件参考，不修改计算 RTL，不访问硬件。依赖 NumPy。原始测试向量生成入口仍在 sim/bf16/operator_validation/scripts 中，输出位置已统一到本目录。

Skill 的独立演示小样本仍随技能保存在 ../skill/pynq-workflow/assets/data，以便技能目录单独分发；主工程输入与参考已保存于本目录。
