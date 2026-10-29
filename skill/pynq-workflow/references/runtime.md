# 板端运行与 DMA

先运行 inspect、check，核对目标、配套哈希、输入与长度。物理入口使用 PYNQ Overlay、MMIO、allocate，直接控制 simple AXI DMA，不调用驱动里可能无界等待的 start/wait/stop。

每次调用均下载完整 Overlay。该封装不适合保留 PL 状态、共享 DMA、环形采集、部分重配置或资源已被其他程序占用的场景。超时后不能直接再次调用来“恢复”。

## Notebook 调用

在板端 Notebook 中按实际上传位置填写路径：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("pynq-workflow/scripts").resolve()))
from run_contract import run_transaction, QuarantinedDMA

pending_dma = None
try:
    result = run_transaction(
        "my_overlay/contract.json",
        output_dir="runs/run_001",
    )
except QuarantinedDMA as error:
    pending_dma = error
    print(error)
else:
    print(result)
```

输出目录必须是新目录。绑定契约按自身位置解析相对路径；未绑定契约需显式指定实际 artifact_root。下载、MMIO 和 DMA 属于硬件操作，任务授权包含上板执行时才调用；文件检查用离线工具。

## 缓存与顺序

输入使用 allocate 得到的连续缓冲区，写入后 sync_to_device。输出初始化后也同步，防止脏缓存行覆盖 DMA 结果；接收完成且字节数一致后 sync_from_device。普通 NumPy 数组、任意切片和临时对象不能代替缓冲区所有者。

并发阶段先接收后发送，共用截止时间。轮询检查 DMA 错误位，完成后读取实际字节数，短帧失败。记录原始输出、环境、输入/产物哈希与步骤时间。

固定 32 位 MMIO；MM2S 控制/状态/地址/长度偏移为 0x00/0x04/0x18/0x1c/0x28，S2MM 加 0x30。不能套用到不同类型 DMA。

## 失败与所有权

异常（含 KeyboardInterrupt/SystemExit）后保存状态，清 run/stop，有界等待 HALTED。全部确认停机才释放；否则抛出 QuarantinedDMA 并保留缓冲区。保持 Notebook、pending_dma 和进程，不 freebuffer、不重用这些内存、不退出 Python。

确认停机后，普通中断继续向调用者抛出。停机阶段再次中断则保守地隔离缓冲区。输入在加载前只读一次，报告登记该快照的哈希。

板级恢复必须先确认 DMA/PL 不再访问内存，才能释放保留对象。等待时间长不等于已停机。该封装不定义全局 PL 复位、PS 重启或外设安全状态。

Python 超时只覆盖能返回的 MMIO 轮询，不能中断挂死的 AXI 总线，也不能保证 Overlay 下载、内核或分配在时限内返回。这些故障需板级看门狗或受控复位。本封装暂无物理板级恢复实测。

## API 来源

- [PYNQ DMA](https://pynq.readthedocs.io/en/latest/pynq_libraries/dma.html)：流式帧结束与使用方式。
- [PYNQ v3.0.1 DMA 实现](https://github.com/Xilinx/PYNQ/blob/v3.0.1/pynq/lib/dma.py)：简单模式寄存器、错误位和完成字节数。
- [PynqBuffer](https://pynq.readthedocs.io/en/latest/pynq_package/pynq.buffer.html)：连续内存、同步和释放。

API 对照不等于物理板测；证据类别见 validation。
