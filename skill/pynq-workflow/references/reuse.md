# 独立回环与迁移验证

先在电脑完成离线检查和构建，再在已获授权的板端运行。以下相对路径以技能包根目录为工作目录；reuse 为新实验目录，不属于技能源码。

## 电脑端准备

准备实际目标板的 PS7 预设 Tcl，作用于名为 ps7 的单元。模板只覆盖 Zynq-7000；更换板卡必须使用该板预设、器件和约束，不能只改器件字符串。

```text
vivado -mode batch -source assets/create_loopback.tcl -tclargs xc7z020clg400-1 path/to/board_ps7.tcl reuse/project reuse/overlay 100 bitstream
```

将 assets/data/loopback_input.csv、loopback_expected.csv 复制到 reuse/input，输入内容不改。绑定同次导出的回环文件：

```text
python scripts/bind_contract.py assets/contracts/loopback.json --artifact-root reuse/overlay --input-root reuse/input --out reuse/contract.json
python scripts/pynq_tool.py check reuse/contract.json --out reuse/check.json
```

核对 check 和实现报告，保存工具版本。绑定后的相对路径以 contract.json 为基准；上传整个 reuse 时保留 overlay、input 和契约关系。板端不需要 project 构建缓存，可只上传 overlay 中的 bit/hwh 与必要报告。另上传完整技能目录，保持 scripts 内文件相邻。

## 板端运行

在 Notebook 中按实际位置加入 scripts，使用新输出目录：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('pynq-workflow/scripts').resolve()))
from run_contract import run_transaction
result = run_transaction('reuse/contract.json', output_dir='reuse/runs/run_001')
print(result)
```

绑定契约省略 artifact_root，文件从契约位置解析。发生 QuarantinedDMA 时按 runtime.md 保留异常对象和进程，禁止释放尚被访问的内存。事务通过后仍需逐元素比较，在电脑或有对应 Python 的板端执行：

```text
python scripts/pynq_tool.py compare --actual reuse/runs/run_001/y.csv --actual-encoding integer --reference reuse/input/loopback_expected.csv --reference-encoding integer --atol 0 --rtol 0 --out reuse/accuracy.json
```

检查四元素、顺序、零误差及硬件执行标记，保存原始 CSV、run.json、accuracy.json 和契约。模拟后端只能登记为模拟结果。

## 迁移记录

复制 assets/reuse_record.json 到实验目录填写板卡、工具、首次部署起止时间、人工修改、运行结果、失败修正和证据路径。部署耗时从拿到清洁案例到首次真实输出通过比较为止；另列下载、安装和构建时间。不能把既有缓存的运行时间写成从零部署时间。

换应用时保留执行器，修改契约、硬件、输入与参考。双输入向量加法模板只有协议示例和模拟验证，没有附带加法电路。换板时重新构建并真实运行；没有其他板卡时保留待验证状态。
