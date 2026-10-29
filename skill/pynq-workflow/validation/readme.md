# 验证记录

记录日期：2026-10-24。工具在 Windows 11、Python 3.12.14 和 Vivado 2026.1 下验证。没有连接物理板卡，没有将新运行封装部署到 PYNQ 镜像。以下各项分别说明验证对象和结论范围。

|项目|实际结果|记录及边界|
|---|---|---|
|执行器与负例|17/17，通过|unit_results.json；缓存、接收顺序、短帧、超时、停机失败、输入范围、哈希、非有限值、报告缺字段等；均为离线/模拟测试|
|独立试用复核|7 组通过；原 17 项再次通过|independent/results.json；由另一测试上下文独立运行，重点复核中断、寄存器边界和输入快照；并非物理板测|
|单独复制使用|14 条验证命令符合预期返回码|clean_environment.json；新建无 pip 的 venv，使用 -I -S -B。技能代码可脱离主工程运行，工程检查文件作为外部输入；不是全新操作系统或 PYNQ 镜像部署|
|不同应用|回环、双输入向量加法均四元素零误差|mock_reuse_results.json、independent/results.json；共用执行器、不同契约；BIT/HWH 和硬件行为为构造/模拟|
|独立硬件构建|Z2、100 MHz，生成比特流，资源和时序检查通过|loopback_build/、loopback_implementation.json；由 assets/create_loopback.tcl 建立真实 DMA 回环工程，使用主工程已有官方 Z2 PS7 预设；没有实际上板|
|既有 Overlay|INT8/BF16 文件的器件、元数据、哈希核对通过|int8_overlay.json、bf16_overlay.json；来源路径及哈希见 project_observations.json；并未重新运行原计算电路|
|既有实现报告|INT8/BF16 资源、setup、hold、pulse width 与 DRC 错误检查通过|int8_implementation.json、bf16_implementation.json；BF16 使用既有完整构建报告|
|真实数值捕获复核|INT8 GELU 3840 个编码一致|int8_gelu_codes.json；15 种缩放的编码比较，不能视为共享同一实数缩放|
|已知失败检出|BF16 首组 Softmax 捕获比较未通过，保留非有限值索引|bf16_nonfinite_detection.json；比较失败是预期检出结果，不能写成 BF16 功能全部通过|
|长尾统计|保留最大值，生成百分位|synthetic_latency.json；1、1、1、1、1000 为合成样本，不是硬件延时|
|技能格式|安装副本通过格式校验，证据和中文内容完整保留|skill_format.json、installation.json；提交目录保持小写，安装脚本在独立目标生成 SKILL.md；已有目标拒绝覆盖|

独立回环实现使用 LUT 3026、FF 3854、BRAM36 3、DSP 0。WNS 1.970 ns、WHS 0.009 ns、WPWS 3.750 ns；DRC 错误 0，告警 16、建议 4。告警保留在原报告，不能将错误为零理解为无告警。

## 修正记录

第一次独立试用发现三个缺口，原始边界结果保存在 independent/initial_boundary_results.json，修正后结果保存在 independent/results.json。

1. 接收启动后 KeyboardInterrupt 绕过清理。现在先尝试有界停机，确认停机才释放；未确认则隔离并持有内存。正常中断继续向调用者抛出，清理时再次中断也不能误判停机。
2. HWH 缺少寄存器窗口时可能接受过大偏移。现在缺失或多义窗口直接拒绝；4092 的最后四字节可接受，4096 越界拒绝。
3. 输入哈希与实际载入内容没有完整绑定。现在输入只读入一次，在硬件加载之前验证并记录快照；绑定后修改输入在加载前拒绝。

定向复核结果和当时源码哈希分别见 independent/results.json、source_hashes.json。安装器随后保留验证目录并单独检查，见 installation.json。协作记录在工程 report/ai_collaboration.md。公开复现实验从 scripts/test_skill.py 和 scripts/make_demo.py 开始，它们不依赖历史临时目录。

## 待补验证

- 在真实 PYNQ 环境运行新封装：正确帧、非对齐/超长拒绝、缓存、字节数、短帧及可控停机。不要用总线挂死替代可恢复故障注入。
- 用独立回环模板完成真实上板，保存输入、输出和零误差比较，再换另一应用。步骤见 references/reuse.md。
- 另一块板卡需重新提供板级预设和约束，从构建开始验证，记录适配改动、部署时间及恢复。当前另一器件标识的解析测试不算跨板运行。
- 对实际 Python/PYNQ/Vivado 版本复测；本次未验证 Linux 主机、Python 3.9 和全部 PYNQ 版本。

assets/reuse_record.json 的空值供后续实测填写。没有测量的数据保持空值。跨题目模拟、独立硬件构建和跨板实测不能互相替代。
