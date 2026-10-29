# -*- coding: gbk -*-
import numpy as np

from mm import (
    TransformerAccelerator,
    DEFAULT_SHIFT,
    DEFAULT_SOFTMAX_SCALE_IN,
    DEFAULT_GELU_SCALE,
  )
from golden_model import transformer_golden, compare_to_hardware


def run_case(acc, rows, in_cols, out_cols, seed=0):
    rng = np.random.default_rng(seed)

    feature = rng.integers(-128, 128, size=(rows, in_cols), dtype=np.int8)
    weight = rng.integers(-128, 128, size=(in_cols, out_cols), dtype=np.int8)

    acc.configure(rows, in_cols, out_cols)

    hw = acc.run(feature, weight)
    golden = transformer_golden(
        feature,
        weight,
        DEFAULT_SHIFT,
        DEFAULT_SOFTMAX_SCALE_IN,
    )

    result = compare_to_hardware(
        hw,
        golden,
        DEFAULT_GELU_SCALE,
        tol_lsb=6.0,
    )

    print("=" * 70)
    print(f"case rows={rows}, in_cols={in_cols}, out_cols={out_cols}, seed={seed}")
    print(f"fifo_overflow: {acc.fifo_overflowed()}")
    print(f"passed:        {result['passed']}")
    print(f"errors:        {result['num_errors']} / {result['num_elements']}")
    print(f"max_abs_diff:  {result['max_abs_diff']:.8f}")
    print(f"tolerance:     {result['tolerance']:.8f}")

    if not result["passed"]:
        print("first bad indices:")
        for idx in result["bad_indices"][:10]:
            r, c = idx
            hw_real = float(hw[r, c]) * (2.0 ** -DEFAULT_GELU_SCALE)
            print(
                f"  [{r}, {c}] hw_int8={int(hw[r, c])}, "
                f"hw_real={hw_real:.8f}, golden={golden[r, c]:.8f}, "
                f"diff={hw_real - golden[r, c]:.8f}"
            )


def main():
    acc = TransformerAccelerator("sys_soc.bit")

    # 小规模，先验证功能正确性
    for seed in range(5):
        run_case(acc, rows=8, in_cols=32, out_cols=32, seed=seed)

    # 中等规模，观察是否开始 overflow
    run_case(acc, rows=32, in_cols=64, out_cols=64, seed=100)

    # 大规模接近 benchmark，当前大概率会 overflow
    run_case(acc, rows=197, in_cols=192, out_cols=192, seed=200)


if __name__ == "__main__":
    main()
