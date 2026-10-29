"""CPU 参考计算：整数矩阵乘法、浮点 Softmax 和 tanh GELU。该文件用于原上板脚本的容差比较；它不是整个定点流水线的逐位参考。独立算子的逐位参考见 sim/int8/operator_validation/scripts/reference.py。"""
import numpy as np


def mm_soft(feature: np.ndarray, weight: np.ndarray, shift: int) -> np.ndarray:
    """feature: (rows, in_cols) int8. weight: (in_cols, out_cols) int8.
    Returns (rows, out_cols) int8: round(feature @ weight / 2**shift), saturated."""
    acc = feature.astype(np.int64) @ weight.astype(np.int64)
    if shift > 0:
        acc = (acc + (1 << (shift - 1))) >> shift
    return np.clip(acc, -128, 127).astype(np.int8)


def softmax_ref(row: np.ndarray) -> np.ndarray:
    """row: 1-D float64 array. Returns a 1-D float64 array summing to 1."""
    smax = max(0.0, float(np.max(row)))
    exp = np.exp(row - smax)
    return exp / np.sum(exp)


def gelu_ref(x):
    """Tanh-approximation GELU, elementwise. x: float or ndarray."""
    c1 = np.sqrt(2.0 / np.pi)
    c2 = 0.044715
    return 0.5 * x * (1.0 + np.tanh(c1 * (x + c2 * x ** 3)))


def transformer_golden(feature: np.ndarray, weight: np.ndarray, shift: int,
                        softmax_scale_in: int) -> np.ndarray:
    """Real-valued (float64) reference for feature @ weight -> per-row softmax
    -> GELU, chained exactly as transformer_block_tb.sv's initial block does.
    Shape: (rows, out_cols), same as the hardware's dequantized output."""
    z = mm_soft(feature, weight, shift)  # (rows, out_cols) int8
    row_real = z.astype(np.float64) * (2.0 ** -softmax_scale_in)
    out = np.empty_like(row_real)
    for r in range(row_real.shape[0]):
        out[r] = gelu_ref(softmax_ref(row_real[r]))
    return out


def compare_to_hardware(hw_result: np.ndarray, golden_real: np.ndarray,
                         gelu_scale: int, tol_lsb: float = 6.0) -> dict:
    """hw_result: the int8 ndarray TransformerAccelerator.run() returned.
    golden_real: transformer_golden(...)'s output for the same inputs/config.
    Same pass/fail rule as transformer_block_tb.sv's final check."""
    hw_real = hw_result.astype(np.float64) * (2.0 ** -gelu_scale)
    tol = tol_lsb * (2.0 ** -gelu_scale)
    diff = hw_real - golden_real
    bad = np.abs(diff) > tol
    return {
        "passed": not bool(np.any(bad)),
        "num_errors": int(np.count_nonzero(bad)),
        "num_elements": int(diff.size),
        "max_abs_diff": float(np.max(np.abs(diff))),
        "tolerance": tol,
        "bad_indices": np.argwhere(bad),
    }
