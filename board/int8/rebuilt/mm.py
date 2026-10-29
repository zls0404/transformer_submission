"""PYNQ INT8 加速器驱动。默认参数：阵列 16×16，Softmax 输入 Q6、输出 Q7，GELU Q7。寄存器地址与当前 Z2 工程保持一致。"""
import time

import numpy as np
from pynq import Overlay, allocate

A_SIZE = 16       # systolic array width -- fixed by the synthesized RTL, do not change here
DATA_WIDTH = 8    # int8 features/weights/output
NUM_GELU = 4      # GELU output lanes -- out_cols must be a multiple of this

# transformer_block_axi.v's register map (byte offsets)
REG_MM_SHIFT             = 0x00
REG_MM_F_LENGTH          = 0x04
REG_MM_F_WIDTH_BLOCK_NUM = 0x08
REG_MM_W_WIDTH_BLOCK_NUM = 0x0C
REG_SOFTMAX_SCALE_IN     = 0x10
REG_SOFTMAX_SCALE_OUT    = 0x14
REG_GELU_SCALE           = 0x18
REG_STATUS              = 0x1C  # bit0 = softmax_to_gelu_fifo_overflow (read-only)

# Default calibration values for the packaged RTL.
# End-to-end application accuracy requires a separate board-level regression.
# softmax_scale_out and gelu_scale MUST be equal for the pipeline to be
# numerically meaningful (transformer_block_top.v's own requirement).
DEFAULT_SHIFT = 9
DEFAULT_SOFTMAX_SCALE_IN = 6
DEFAULT_SOFTMAX_SCALE_OUT = 7
DEFAULT_GELU_SCALE = 7

_DMA_WAIT_TIMEOUT_S = 10.0


class TransformerAccelerator:
    """Thin driver around one transformer_block_axi_top instance and its 3 AXI DMA channels."""

    def __init__(self, bitfile="design.bit"):
        self.ol = Overlay(bitfile)
        self.ctrl = self._resolve_ip("transformer_block_ax_0")
        self.feature_dma = self.ol.axi_dma_0  # MM2S -> s0_axis (feature/activations)
        self.weight_dma = self.ol.axi_dma_1   # MM2S -> s1_axis (weights)
        self.result_dma = self.ol.axi_dma_2   # S2MM <- m0_axis (GELU output)
        self.in_rows = self.in_cols = self.out_cols = None

    def _resolve_ip(self, prefix):
        """Look up an IP by instance-name prefix in ol.ip_dict and return the
        live driver object, regardless of whether PYNQ exposed it under the
        plain instance name or '<instance>/<axi_interface_name>' (observed:
        transformer_block_axi_top_0's control interface shows up as
        'transformer_block_axi_top_0/s00_axi', named after its AXI-Lite
        interface rather than the block instance, because that's what the
        .hwh actually associates the address segment with)."""
        matches = [k for k in self.ol.ip_dict if k == prefix or k.startswith(prefix + "/")]
        if not matches:
            raise RuntimeError(f"No IP matching '{prefix}' in this overlay -- "
                                f"check ol.ip_dict.keys(): {list(self.ol.ip_dict.keys())}")
        obj = self.ol
        for part in matches[0].split("/"):
            obj = getattr(obj, part)
        return obj

    def configure(self, in_rows, in_cols, out_cols,
                  shift=DEFAULT_SHIFT,
                  softmax_scale_in=DEFAULT_SOFTMAX_SCALE_IN,
                  softmax_scale_out=DEFAULT_SOFTMAX_SCALE_OUT,
                  gelu_scale=DEFAULT_GELU_SCALE):
        if in_cols % A_SIZE != 0:
            raise ValueError(f"in_cols ({in_cols}) must be a multiple of A_SIZE ({A_SIZE})")
        if out_cols % A_SIZE != 0:
            raise ValueError(f"out_cols ({out_cols}) must be a multiple of A_SIZE ({A_SIZE})")
        if softmax_scale_out != gelu_scale:
            raise ValueError("softmax_scale_out and gelu_scale must be equal "
                              "(transformer_block_top.v requirement)")

        self.in_rows, self.in_cols, self.out_cols = in_rows, in_cols, out_cols
        self.ctrl.write(REG_MM_SHIFT, shift & 0x3FF)
        self.ctrl.write(REG_MM_F_LENGTH, in_rows)
        self.ctrl.write(REG_MM_F_WIDTH_BLOCK_NUM, in_cols // A_SIZE)
        self.ctrl.write(REG_MM_W_WIDTH_BLOCK_NUM, out_cols // A_SIZE)
        self.ctrl.write(REG_SOFTMAX_SCALE_IN, softmax_scale_in & 0x1F)
        self.ctrl.write(REG_SOFTMAX_SCALE_OUT, softmax_scale_out & 0xF)
        self.ctrl.write(REG_GELU_SCALE, gelu_scale & 0xF)

    def fifo_overflowed(self):
        return bool(self.ctrl.read(REG_STATUS) & 0x1)

    def run(self, feature, weight):
        """feature: (in_rows, in_cols) int8 ndarray. weight: (in_cols, out_cols) int8 ndarray.
        Returns the (in_rows, out_cols) int8 result of gelu(softmax(feature @ weight >> shift))."""
        in_rows, in_cols = feature.shape
        w_in_cols, out_cols = weight.shape
        if in_cols != w_in_cols:
            raise ValueError(f"feature cols ({in_cols}) != weight rows ({w_in_cols})")
        if (in_rows, in_cols, out_cols) != (self.in_rows, self.in_cols, self.out_cols):
            raise ValueError("shape doesn't match the last configure() call -- call configure() first")

        feature_buf = allocate(shape=(in_rows, in_cols), dtype=np.int8)
        weight_buf = allocate(shape=(in_cols, out_cols), dtype=np.int8)
        result_buf = allocate(shape=(in_rows, out_cols), dtype=np.int8)
        try:
            feature_buf[:] = feature
            weight_buf[:] = weight

            # Arm the receive channel before the two send channels start
            # streaming, matching apps/Matrix.cpp's ordering.
            self.result_dma.recvchannel.transfer(result_buf)
            self.weight_dma.sendchannel.transfer(weight_buf)
            self.feature_dma.sendchannel.transfer(feature_buf)

            self._wait(self.feature_dma.sendchannel, "feature send")
            self._wait(self.weight_dma.sendchannel, "weight send")
            self._wait(self.result_dma.recvchannel, "result receive")

            if self.fifo_overflowed():
                print("WARNING: softmax_to_gelu_fifo_overflow was set -- "
                      "increase GELU_FIFO_DEPTH or shrink out_cols and re-synthesize")

            return result_buf.copy()
        finally:
            feature_buf.freebuffer()
            weight_buf.freebuffer()
            result_buf.freebuffer()

    @staticmethod
    def _wait(channel, label, timeout_s=_DMA_WAIT_TIMEOUT_S):
        deadline = time.time() + timeout_s
        while not channel.idle:
            if time.time() > deadline:
                raise TimeoutError(f"{label} DMA channel did not go idle within {timeout_s}s")
            time.sleep(0.001)
