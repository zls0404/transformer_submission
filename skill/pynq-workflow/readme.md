# PYNQ 工程构建与验证技能包

本目录提供接口契约、离线校验工具、板端事务封装和故障定位记录。适用于基于 PYNQ 的流式计算、图像/信号处理、向量运算及寄存器控制。板卡、IP 名称、寄存器和格式由使用者的工程定义，工具不引用 Transformer 专用名称。

## 能力和边界

|能力|适用场景与用法|失效条件|已有验证|
|---|---|---|---|
|Overlay 核对|inspect 检查 BIT/HWH 目标、完整性及配套哈希|不支持原始 BIN、部分重配置、非 HWH 元数据；无哈希不能证明同构建|真实 INT8/BF16 文件离线检查；错误板型与哈希负例|
|接口契约|check 验证寄存器范围、buffer 类型/大小、DMA 能力|不能自动证明启动、TLAST 或算法语义|单输入回环、双输入加法模拟案例；超长、SG、错序索引负例|
|板端事务|Notebook 调用 run_transaction，有序 MMIO 和搬运|全 Overlay、32 位 MMIO、simple AXI DMA；总线挂死不由 Python 超时解决|模拟设备的缓存、顺序、短帧、超时和停机失败测试；真实板测待补|
|黄金参考|compare 支持浮点、定点整数和 BF16 原始编码|只做逐元素比较，任务精度另测；阈值需声明|INT8 GELU 编码一致性、BF16 既有 NaN 失败检出及构造负例|
|延时统计|stats 报告 P50/P95/P99/max 和样本数|无计时范围或非有限样本时拒绝；样本太少不能支撑尾延时|保留长尾的测试；合成样本不称为硬件性能|
|资源时序|reports 检查器件、资源、setup/hold/pulse width、无时钟寄存器与 DRC|只识别已列出的英文 Vivado 文本格式；缺字段失败；不代替功能验证|INT8/BF16 真实实现报告及错误报告负例|
|工作流与排错|按 references 模板整理接口、分析报告、定位问题|缺少语义时不能猜地址、阈值和复位策略|来源、试用结果见 references/failures.md 与 validation|

“模拟”指软件后端，未连接板卡。完整范围见[验证记录](validation/readme.md)。

## 依赖

离线工具仅用 Python 标准库，Python 3.9 及以上，无需联网、PYNQ、NumPy 或管理员权限。支持 Windows/Linux；已验证平台在验证记录中列出。

板端入口需对应板卡的 PYNQ、NumPy、连续内存和硬件访问权限。API 依据 PYNQ v3.0.1 编写；新封装未在物理板卡上验证，换版本后先做最小回环和恢复测试。

## 离线试用

在本目录执行，输出目录使用尚不存在的路径：

```text
python scripts/test_skill.py --json unit_results.json
python scripts/make_demo.py --output demo_run
python scripts/pynq_tool.py check demo_run/loopback/contract.json --out loopback_check.json
python scripts/pynq_tool.py compare --actual demo_run/loopback/result/y.csv --actual-encoding integer --reference assets/data/loopback_expected.csv --reference-encoding integer --atol 0 --rtol 0 --out loopback_compare.json
```

demo_run 中的 BIT/HWH 是构造文件，不是可上板电路。make_demo 只用模拟后端；物理入口拒绝微小模拟 payload。生成数据与技能源码分开保存。

## 用于自己的工程

1. 从同一次构建导出同名前缀的 bit/hwh，保存到短英文路径。
2. 执行核对命令，再依据 RTL 修改 assets/contracts 中的案例，填写自己的输入、形状、dtype、IP、寄存器、步骤和超时。
3. 确认同次导出后，在 artifacts.sha256 登记文件哈希；采集哈希本身不是同构建证明。
4. 运行 check；处理错误后，在板端 Notebook 按 references/runtime.md 调用封装。
5. 比较真实输出，保留原始样本、环境和失败，再统计性能。

bind_contract.py 可将模板绑定到已有导出及输入目录，自动登记哈希并使用相对路径，不改原文件。例如回环案例：

```text
python scripts/bind_contract.py assets/contracts/loopback.json --artifact-root path/to/overlay_output --input-root assets/data --out case/contract.json
python scripts/pynq_tool.py check case/contract.json --out case/check.json
```

它绑定选定文件，不证明导出来源。移动案例时需一并保留其相对路径引用的文件；Windows 下绑定目录需位于同一盘。

```text
python scripts/pynq_tool.py inspect --bit path/to/design.bit --hwh path/to/design.hwh --part xc7z020clg400-1 --out pair_check.json
python scripts/pynq_tool.py check path/to/contract.json --artifact-root path/to/artifacts --out contract_check.json
python scripts/pynq_tool.py compare --actual output.csv --reference reference.csv --atol 0.0001 --rtol 0.01 --out accuracy.json
python scripts/pynq_tool.py stats latency.csv --column elapsed_us --unit us --scope "register start to output completion, includes DMA" --out latency.json
python scripts/pynq_tool.py reports --timing timing_summary.rpt --utilization impl_utilization.rpt --drc drc.rpt --part xc7z020clg400-1 --out implementation.json
```

示例阈值只展示参数写法，不能直接用于算法验收。返回码：0 为该项检查通过，1 为完成比较但未通过，2 为输入或格式错误。板端 passed 只表示事务及字节数，不表示数值正确。

## 迁移

换题目时重写契约、输入和参考；帧语义改变后重测启动顺序与 TLAST。换板卡时重新配置实际器件、板级预设、时钟和约束，构建该板 Overlay，再核对地址宽度、DMA 与 PYNQ API。识别出另一器件不等于跨板部署成功。

本目录可单独复制使用，不需要当前工程的 src、build 或绝对路径。validation 的工程记录用于追溯，不是工具依赖。

## 独立硬件案例

assets/create_loopback.tcl 可从零建立一个不同于 Transformer 的 DMA 回环工程。仅支持 Zynq-7000，必须提供目标板的 PS7 预设 Tcl，预设作用于名为 ps7 的单元。它不自带跨板通用 DDR/MIO 参数。

```text
vivado -mode batch -source assets/create_loopback.tcl -tclargs xc7z020clg400-1 path/to/board_ps7.tcl path/to/new_project path/to/overlay_output 100 bitstream
```

使用尚不存在的 project/export 目录；最后参数可改为 project，只建工程。bitstream 模式从同一运行导出 loopback.bit/hwh 和实现报告。构建、板端回环及跨板迁移三种结论分别记录。完整步骤见 [reuse.md](references/reuse.md)，实测记录模板为 assets/reuse_record.json。

## 智能体入口

提交目录使用小写 skill.md。智能体要求标准 SKILL.md 名称时，用安装脚本生成单独副本，不改提交目录：

```text
python scripts/install_skill.py --destination path/to/agent-skills/pynq-workflow
```

目标必须不存在，不替换已有技能或修改全局配置。手动使用时可直接读取 skill.md。

## 文件

skill.md 为入口；scripts 为执行/校验工具；assets 为契约、输入与记录模板；references 为条件化说明；validation 为真实验证记录和待补板测。
