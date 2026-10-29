# PYNQ 工程构建与验证技能

本目录提供可单独复制使用的 PYNQ 技能包。它包含 Overlay 核对、接口契约、简单 AXI DMA 事务、数值与性能分析、资源时序检查、案例和故障记录。工具不依赖本队 Transformer IP 名称或固定地址。

- [使用说明](pynq-workflow/readme.md)：适用范围、依赖、命令和失效条件。
- [智能体入口](pynq-workflow/skill.md)：工作流与工程约束。
- [验证记录](pynq-workflow/validation/readme.md)：17 项测试、独立试用、构建结果及待补板测。
- [独立回环与迁移步骤](pynq-workflow/references/reuse.md)：从构建、绑定到上板比较及记录。

文件对应关系：scripts 放执行和校验脚本，assets 放契约/数据/记录模板，references 放使用说明和排错依据，validation 放实际验证证据。提交文件统一小写；需智能体标准 SKILL.md 时，按说明生成独立安装副本，不改提交目录。

已完成回环和向量加法的软件模拟复用、独立 DMA 回环工程的真实 Vivado 构建，以及既有 INT8/BF16 产物和捕获的离线复核。没有完成新封装的真实板测或跨板运行。保留失败和告警，不把构建成功等同于硬件功能通过。
