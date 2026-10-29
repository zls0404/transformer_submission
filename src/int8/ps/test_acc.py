from mm import TransformerAccelerator
import numpy as np


def main():
    # Load FPGA overlay.
    # The .bit and .hwh files must have the same base name:
    # sys_soc.bit and sys_soc.hwh
    acc = TransformerAccelerator("sys_soc.bit")

    # Matrix sizes:
    # feature: IN_ROWS x IN_COLS
    # weight : IN_COLS x OUT_COLS
    # result : IN_ROWS x OUT_COLS
    #
    # IN_COLS and OUT_COLS must be multiples of 16.
    IN_ROWS = 8
    IN_COLS = 32
    OUT_COLS = 32

    acc.configure(IN_ROWS, IN_COLS, OUT_COLS)

    # Fixed random seed, so every run uses the same input data.
    rng = np.random.default_rng(0)

    feature = rng.integers(
        -128,
        128,
        size=(IN_ROWS, IN_COLS),
        dtype=np.int8,
    )

    weight = rng.integers(
        -128,
        128,
        size=(IN_COLS, OUT_COLS),
        dtype=np.int8,
    )

    result = acc.run(feature, weight)

    print("feature shape:", feature.shape)
    print("weight shape :", weight.shape)
    print("result shape :", result.shape)
    print("result dtype :", result.dtype)
    print("fifo_overflow:", acc.fifo_overflowed())

    print("\nfeature:")
    print(feature)

    print("\nweight:")
    print(weight)

    print("\nresult:")
    print(result)


if __name__ == "__main__":
    main()
