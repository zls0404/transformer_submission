"""ISCAS Softmax 候选实现的板端比较脚本。当前构建默认使用 baseline Softmax，运行此脚本前需核对 IP 参数 USE_POW2_SOFTMAX；默认工程的结果不能按 ISCAS 定点模型验收。"""
import argparse
import csv
from pathlib import Path

import numpy as np

from mm import (
    TransformerAccelerator,
    DEFAULT_SHIFT,
    DEFAULT_SOFTMAX_SCALE_IN,
    DEFAULT_SOFTMAX_SCALE_OUT,
    DEFAULT_GELU_SCALE,
)
from golden_model import mm_soft, softmax_ref, gelu_ref, compare_to_hardware


def nearest_log2(value):
    if value <= 1:
        return 0
    floor_log2 = int(value.bit_length() - 1)
    if floor_log2 == 0:
        return 1 if value >= 2 else 0
    threshold = (1 << floor_log2) + (1 << (floor_log2 - 1))
    return floor_log2 + 1 if value >= threshold else floor_log2


def approx_pow_iscas_q14(x_q10):
    # Mirrors Softmax_iscas2023_parallel.approx_pow_iscas_q14().
    scaled = x_q10 + (x_q10 >> 1)
    abs_scaled = -scaled if scaled < 0 else scaled
    int_part = abs_scaled >> 10
    frac_q10 = abs_scaled & 0x3FF
    mant_q14 = 16384 - (frac_q10 << 3)
    if int_part >= 14:
        return 0
    return int(mant_q14 >> int_part)


def normalize_pow2(pow_q14, denom_log2, scale_out):
    shift_amt = denom_log2 - scale_out
    if shift_amt > 0:
        value = (pow_q14 + (1 << (shift_amt - 1))) >> shift_amt
    elif shift_amt == 0:
        value = pow_q14
    else:
        value = pow_q14 << (-shift_amt)
    return int(min(127, max(0, value)))


def iscas_softmax_int(row, scale_in, scale_out):
    """Algorithm-2 softmax adapter used by current ISCAS RTL.

    Input row is int8 from MM. Output is the same int8/q7-ish value that the
    softmax block sends into GELU.
    """
    row = row.astype(np.int16)
    row_max = int(np.max(row))

    pows = []
    for x in row:
        diff = int(x) - row_max
        if scale_in == -1:
            x_q10 = (diff << 11) - 1024
        elif scale_in < 10:
            x_q10 = (diff << (10 - scale_in)) - 1024
        else:
            x_q10 = diff - 1024
        pows.append(approx_pow_iscas_q14(x_q10))

    denom_log2 = nearest_log2(int(np.sum(pows)))
    return np.array(
        [normalize_pow2(p, denom_log2, scale_out) for p in pows],
        dtype=np.int8,
    )


def transformer_golden_iscas(feature, weight, shift, softmax_scale_in,
                             softmax_scale_out):
    """MM -> ISCAS Algorithm-2 softmax -> ideal GELU reference."""
    z = mm_soft(feature, weight, shift)
    sm_int = np.empty_like(z, dtype=np.int8)
    for r in range(z.shape[0]):
        sm_int[r] = iscas_softmax_int(
            z[r],
            softmax_scale_in,
            softmax_scale_out,
        )
    sm_real = sm_int.astype(np.float64) * (2.0 ** -softmax_scale_out)
    return gelu_ref(sm_real), sm_int


def transformer_golden_true(feature, weight, shift, softmax_scale_in):
    """MM -> high precision softmax -> ideal GELU reference."""
    z = mm_soft(feature, weight, shift)
    row_real = z.astype(np.float64) * (2.0 ** -softmax_scale_in)
    out = np.empty_like(row_real)
    for r in range(row_real.shape[0]):
        out[r] = gelu_ref(softmax_ref(row_real[r]))
    return out


def true_softmax_matrix(mm_int, scale_in):
    row_real = mm_int.astype(np.float64) * (2.0 ** -scale_in)
    out = np.empty_like(row_real)
    for r in range(row_real.shape[0]):
        out[r] = softmax_ref(row_real[r])
    return out


def dump_debug_csv(path, mm_int, hw, iscas_sm_int, true_sm_prob,
                   iscas_real, true_real):
    prob_scale = float(2 ** DEFAULT_SOFTMAX_SCALE_OUT)
    gelu_scale = float(2 ** DEFAULT_GELU_SCALE)
    with open(str(path), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "row",
            "col",
            "softmax_input_mm_int8",
            "softmax_input_real",
            "standard_softmax_prob",
            "standard_softmax_q7_floor",
            "iscas_softmax_int",
            "iscas_softmax_prob",
            "hw_gelu_int8",
            "hw_gelu_real",
            "standard_gelu_real",
            "iscas_gelu_golden_real",
            "err_hw_vs_standard_gelu",
            "err_hw_vs_iscas_gelu",
            "err_iscas_softmax_vs_standard_prob",
        ])
        for r in range(mm_int.shape[0]):
            for c in range(mm_int.shape[1]):
                hw_real = float(hw[r, c]) / gelu_scale
                true_q7 = int(min(127, max(0, np.floor(true_sm_prob[r, c] * prob_scale))))
                iscas_prob = float(iscas_sm_int[r, c]) / prob_scale
                writer.writerow([
                    r,
                    c,
                    int(mm_int[r, c]),
                    "{:.10f}".format(float(mm_int[r, c]) * (2.0 ** -DEFAULT_SOFTMAX_SCALE_IN)),
                    "{:.10f}".format(float(true_sm_prob[r, c])),
                    true_q7,
                    int(iscas_sm_int[r, c]),
                    "{:.10f}".format(iscas_prob),
                    int(hw[r, c]),
                    "{:.10f}".format(hw_real),
                    "{:.10f}".format(float(true_real[r, c])),
                    "{:.10f}".format(float(iscas_real[r, c])),
                    "{:.10f}".format(hw_real - float(true_real[r, c])),
                    "{:.10f}".format(hw_real - float(iscas_real[r, c])),
                    "{:.10f}".format(iscas_prob - float(true_sm_prob[r, c])),
                ])


def print_debug_row(row_id, limit, mm_int, hw, iscas_sm_int, true_sm_prob,
                    iscas_real, true_real):
    if row_id < 0 or row_id >= mm_int.shape[0]:
        print("debug row {} is out of range 0..{}".format(row_id, mm_int.shape[0] - 1))
        return

    prob_scale = float(2 ** DEFAULT_SOFTMAX_SCALE_OUT)
    gelu_scale = float(2 ** DEFAULT_GELU_SCALE)
    n = min(limit, mm_int.shape[1])
    print("Debug row {}, first {} points:".format(row_id, n))
    print("col  mm_i8  std_sm     iscas_sm   hw_gelu    std_gelu   iscas_gelu err_hw_iscas")
    for c in range(n):
        hw_real = float(hw[row_id, c]) / gelu_scale
        iscas_prob = float(iscas_sm_int[row_id, c]) / prob_scale
        err_hw_iscas = hw_real - float(iscas_real[row_id, c])
        print(
            "{:3d} {:6d} {:9.6f} {:9.6f} {:9.6f} {:9.6f} {:10.6f} {:12.6f}".format(
                c,
                int(mm_int[row_id, c]),
                float(true_sm_prob[row_id, c]),
                iscas_prob,
                hw_real,
                float(true_real[row_id, c]),
                float(iscas_real[row_id, c]),
                err_hw_iscas,
            )
        )


def print_result(title, result):
    print(title)
    print("  passed:        {}".format(result["passed"]))
    print("  errors:        {} / {}".format(
        result["num_errors"],
        result["num_elements"],
    ))
    print("  max_abs_diff:  {:.8f}".format(result["max_abs_diff"]))
    print("  tolerance:     {:.8f}".format(result["tolerance"]))


def run_case(acc, rows, in_cols, out_cols, seed, tol_lsb,
             dump_dir=None, print_row=None, print_limit=32):
    rng = np.random.default_rng(seed)
    feature = rng.integers(-128, 128, size=(rows, in_cols), dtype=np.int8)
    weight = rng.integers(-128, 128, size=(in_cols, out_cols), dtype=np.int8)

    acc.configure(
        rows,
        in_cols,
        out_cols,
        shift=DEFAULT_SHIFT,
        softmax_scale_in=DEFAULT_SOFTMAX_SCALE_IN,
        softmax_scale_out=DEFAULT_SOFTMAX_SCALE_OUT,
        gelu_scale=DEFAULT_GELU_SCALE,
    )

    hw = acc.run(feature, weight)
    mm_int = mm_soft(feature, weight, DEFAULT_SHIFT)
    true_sm_prob = true_softmax_matrix(mm_int, DEFAULT_SOFTMAX_SCALE_IN)
    iscas_real, iscas_sm_int = transformer_golden_iscas(
        feature,
        weight,
        DEFAULT_SHIFT,
        DEFAULT_SOFTMAX_SCALE_IN,
        DEFAULT_SOFTMAX_SCALE_OUT,
    )
    true_real = transformer_golden_true(
        feature,
        weight,
        DEFAULT_SHIFT,
        DEFAULT_SOFTMAX_SCALE_IN,
    )

    iscas_result = compare_to_hardware(
        hw,
        iscas_real,
        DEFAULT_GELU_SCALE,
        tol_lsb=tol_lsb,
    )
    true_result = compare_to_hardware(
        hw,
        true_real,
        DEFAULT_GELU_SCALE,
        tol_lsb=tol_lsb,
    )

    approx_diff = iscas_real - true_real

    print("=" * 70)
    print("case rows={}, in_cols={}, out_cols={}, seed={}".format(
        rows,
        in_cols,
        out_cols,
        seed,
    ))
    print("fifo_overflow: {}".format(acc.fifo_overflowed()))
    print_result("HW vs ISCAS Algorithm2 golden:", iscas_result)
    print_result("HW vs high precision softmax golden:", true_result)
    print("ISCAS Algorithm2 vs high precision softmax:")
    print("  mae_prob:      {:.8f}".format(float(np.mean(np.abs(approx_diff)))))
    print("  rmse_prob:     {:.8f}".format(float(np.sqrt(np.mean(approx_diff ** 2)))))
    print("  max_abs_prob:  {:.8f}".format(float(np.max(np.abs(approx_diff)))))
    print("  softmax_sum:   min={} max={}".format(
        int(np.min(np.sum(iscas_sm_int.astype(np.int16), axis=1))),
        int(np.max(np.sum(iscas_sm_int.astype(np.int16), axis=1))),
    ))

    if print_row is not None:
        print_debug_row(
            print_row,
            print_limit,
            mm_int,
            hw,
            iscas_sm_int,
            true_sm_prob,
            iscas_real,
            true_real,
        )

    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)
        csv_path = dump_dir / "dump_rows{}_in{}_out{}_seed{}.csv".format(
            rows,
            in_cols,
            out_cols,
            seed,
        )
        dump_debug_csv(
            csv_path,
            mm_int,
            hw,
            iscas_sm_int,
            true_sm_prob,
            iscas_real,
            true_real,
        )
        print("debug CSV written: {}".format(csv_path))

    if not iscas_result["passed"]:
        print("first bad indices for HW vs ISCAS:")
        for idx in iscas_result["bad_indices"][:10]:
            r, c = idx
            hw_real = float(hw[r, c]) * (2.0 ** -DEFAULT_GELU_SCALE)
            diff = hw_real - iscas_real[r, c]
            print(
                "  [{}, {}] hw_int8={}, hw_real={:.8f}, "
                "iscas_golden={:.8f}, diff={:.8f}".format(
                    r,
                    c,
                    int(hw[r, c]),
                    hw_real,
                    iscas_real[r, c],
                    diff,
                )
            )

    return iscas_result, true_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bitfile", default="sys_soc.bit")
    parser.add_argument("--tol-lsb", type=float, default=6.0)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--dump-csv", default=None,
                        help="Directory to write per-point CSV debug dumps.")
    parser.add_argument("--print-row", type=int, default=None,
                        help="Print one row of per-point data to terminal.")
    parser.add_argument("--print-limit", type=int, default=32,
                        help="Number of columns to print when --print-row is used.")
    parser.add_argument(
        "--include-small-edge",
        action="store_true",
        help="Also run small 2/4-block cases that are known to expose MM edge-case issues.",
    )
    args = parser.parse_args()

    acc = TransformerAccelerator(args.bitfile)
    dump_dir = Path(args.dump_csv) if args.dump_csv else None

    # Use block counts that are representative of the intended ViT run.
    # Very small 2/4-block shapes can expose an existing MM edge-case and are
    # not a clean softmax/activation correctness test for this accelerator.
    cases = [
        (8, 192, 192, 0),
        (32, 192, 192, 100),
    ]
    if not args.quick:
        cases.extend([
            (197, 192, 192, 200),
            (32, 192, 320, 300),
        ])
    if args.include_small_edge:
        for seed in range(5):
            cases.append((8, 32, 32, seed))
        cases.append((32, 64, 64, 100))

    iscas_pass = 0
    true_pass = 0
    for rows, in_cols, out_cols, seed in cases:
        iscas_result, true_result = run_case(
            acc,
            rows,
            in_cols,
            out_cols,
            seed,
            args.tol_lsb,
            dump_dir=dump_dir,
            print_row=args.print_row,
            print_limit=args.print_limit,
        )
        iscas_pass += int(iscas_result["passed"])
        true_pass += int(true_result["passed"])

    print("=" * 70)
    print("SUMMARY")
    print("HW vs ISCAS Algorithm2 golden passed: {} / {}".format(
        iscas_pass,
        len(cases),
    ))
    print("HW vs high precision softmax passed: {} / {}".format(
        true_pass,
        len(cases),
    ))


if __name__ == "__main__":
    main()
