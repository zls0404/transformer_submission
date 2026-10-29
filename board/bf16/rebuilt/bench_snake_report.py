"""Detailed PL functionality and CPU/FPGA latency report for project_4.

Copy this script beside design_1.bit and design_1.hwh on PYNQ, then run:
    sudo -E python3 -u bench_snake_report.py

Active input: (4, 4) @ (4, 128), zero-padded to the existing (4, 768)
hardware frame. Includes the original Snake ops and extensions 8-11.
"""

from pathlib import Path
import time

import numpy as np


ROOT = Path(__file__).resolve().parent
BITFILE = ROOT / "design_1.bit"
HWHFILE = ROOT / "design_1.hwh"
M, K, N = 4, 4, 768
ACTIVE_N = 128  # medium workload; do not change fixed hardware M/K/N above
OUTPUT_WORDS = M * N // 4  # four BF16 elements in every 64-bit beat
AUX_WORDS = (K + 3) * N
RUNS = 30
SEED = 2026
OPS = {
    0: "GEMM + Snake Softmax",
    1: "GEMM + Snake LayerNorm",
    2: "GEMM + Snake RMSNorm",
    3: "GEMM + Snake SiLU",
    4: "GEMM + Snake sigmoid GELU",
    7: "BF16 GEMM bypass",
    8: "GEMM + LayerNorm affine",
    9: "GEMM + RMSNorm affine",
    10: "GEMM + masked Softmax",
    11: "SwiGLU (two GEMMs)",
}
REL_L2_LIMIT = 0.05  # application-level tolerance, not an upstream guarantee


def f32_to_bf16(x):
    """IEEE BF16 round-to-nearest-even, matching fp32_to_bf16_rne.v."""
    x = np.asarray(x, dtype=np.float32)
    bits = x.view(np.uint32)
    rounded = bits + np.uint32(0x7FFF) + ((bits >> 16) & 1)
    result = (rounded >> 16).astype(np.uint16)
    is_nan = ((bits & 0x7F800000) == 0x7F800000) & ((bits & 0x007FFFFF) != 0)
    return np.where(is_nan, ((bits >> 16) & 0x8000) | 0x7FFF, result).astype(np.uint16)


def bf16_to_f32(x):
    return (np.asarray(x, dtype=np.uint16).astype(np.uint32) << 16).view(np.float32)


def make_inputs():
    if not 1 <= ACTIVE_N <= N:
        raise ValueError("ACTIVE_N must be between 1 and %d" % N)
    rng = np.random.default_rng(SEED)
    a = rng.uniform(-0.5, 0.75, (M, K)).astype(np.float32)
    b = np.zeros((K, N), dtype=np.float32)
    b[:, :ACTIVE_N] = rng.uniform(-0.2, 0.3, (K, ACTIVE_N))
    return f32_to_bf16(a), f32_to_bf16(b)


def read_status(ctrl):
    raw = int(ctrl.read(0x04))
    return {
        "raw": raw,
        "busy": raw & 1,
        "done": (raw >> 1) & 1,
        "error": (raw >> 2) & 1,
        "A_loaded": (raw >> 3) & 1,
        "B_loaded": (raw >> 4) & 1,
        "aux_loaded": (raw >> 5) & 1,
    }


def assert_ready(ctrl, label):
    s = read_status(ctrl)
    if s["busy"] or s["error"] or not s["A_loaded"] or not s["B_loaded"]:
        raise RuntimeError("%s: bad PL status 0x%08X %s" % (label, s["raw"], s))
    return s


def to_matrix(out_buf):
    # little-endian ARM: each uint64 word contains BF16 lanes [3:0].
    return bf16_to_f32(np.asarray(out_buf).view(np.uint16)).reshape(M, N)


def run_first(ctrl, da, db, dout, a_buf, b_buf, out_buf, op):
    """Initial A/B DMA loading + operation; return total elapsed seconds."""
    a_buf.flush()
    b_buf.flush()
    out_buf[:] = 0
    out_buf.flush()
    t0 = time.perf_counter()
    dout.recvchannel.transfer(out_buf)
    da.sendchannel.transfer(a_buf)
    db.sendchannel.transfer(b_buf)
    da.sendchannel.wait()
    db.sendchannel.wait()
    assert_ready(ctrl, "input DMA complete")
    ctrl.write(0x00, (int(op) << 4) | 1)
    dout.recvchannel.wait()
    out_buf.invalidate()
    assert_ready(ctrl, "first operation complete")
    return time.perf_counter() - t0


def run_loaded(ctrl, dout, out_buf, op):
    """Run with A/B already latched in the PL accelerator."""
    out_buf[:] = 0
    out_buf.flush()
    t0 = time.perf_counter()
    dout.recvchannel.transfer(out_buf)
    ctrl.write(0x00, (int(op) << 4) | 1)
    dout.recvchannel.wait()
    out_buf.invalidate()
    status = assert_ready(ctrl, "op %d complete" % op)
    if op >= 8 and not status["aux_loaded"]:
        raise RuntimeError("op %d completed without its auxiliary frame" % op)
    return time.perf_counter() - t0


def cpu_reference(op, mm_bf16):
    """CPU references for upstream Snake operator semantics, then BF16 round."""
    x = np.asarray(mm_bf16, dtype=np.float32)
    if op == 0:
        z = x - np.max(x, axis=1, keepdims=True)
        y = np.exp(z)
        y = y / np.sum(y, axis=1, keepdims=True)
    elif op == 1:
        mean = np.mean(x, axis=1, keepdims=True)
        var = np.mean((x - mean) ** 2, axis=1, keepdims=True)
        y = (x - mean) / np.sqrt(var + 1.0e-5)
    elif op == 2:
        msq = np.mean(x ** 2, axis=1, keepdims=True)
        y = x / np.sqrt(msq + 1.0e-5)
    elif op == 3:
        y = x / (1.0 + np.exp(-x))
    elif op == 4:
        # Gluttonous_array.v uses -0x3FD9D2C7 as the exp multiplier.
        coefficient = np.asarray([0x3FD9D2C7], dtype=np.uint32).view(np.float32)[0]
        y = x / (1.0 + np.exp(-coefficient * x))
    elif op == 7:
        y = x
    else:
        raise ValueError("unsupported op %d" % op)
    return bf16_to_f32(f32_to_bf16(y))


def github_gelu_reference(x):
    """Upstream python/general.py uses GELU approximate='tanh'."""
    x = np.asarray(x, dtype=np.float32)
    y = 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * x ** 3)))
    return bf16_to_f32(f32_to_bf16(y))


def cpu_pipeline(op, a, b):
    mm = cpu_reference(7, np.matmul(a, b).astype(np.float32))
    return mm if op == 7 else cpu_reference(op, mm)


def extended_reference(op, mm_bf16, mm_up_bf16, gamma, beta, mask):
    """CPU reference matching the BF16 boundaries in the extended RTL."""
    x = np.asarray(mm_bf16, dtype=np.float32)
    if op in (8, 9):
        if op == 8:
            mean = np.mean(x, axis=1, keepdims=True)
            var = np.mean((x - mean) ** 2, axis=1, keepdims=True)
            normalized = (x - mean) / np.sqrt(var + 1.0e-5)
        else:
            msq = np.mean(x ** 2, axis=1, keepdims=True)
            normalized = x / np.sqrt(msq + 1.0e-5)
        y = normalized * gamma[None, :] + beta[None, :]
    elif op == 10:
        z = np.where(mask[None, :], x, -np.inf)
        z -= np.max(z, axis=1, keepdims=True)
        exp_z = np.exp(z)
        y = exp_z / np.sum(exp_z, axis=1, keepdims=True)
    elif op == 11:
        silu = x / (1.0 + np.exp(-x))
        silu = bf16_to_f32(f32_to_bf16(silu))
        y = silu * mm_up_bf16
    else:
        raise ValueError("unsupported extended op %d" % op)
    return bf16_to_f32(f32_to_bf16(y))


def cpu_extended_pipeline(op, a, b, w_up, gamma, beta, mask):
    mm = cpu_reference(7, np.matmul(a, b).astype(np.float32))
    mm_up = cpu_reference(7, np.matmul(a, w_up).astype(np.float32)) if op == 11 else None
    return extended_reference(op, mm, mm_up, gamma, beta, mask)


def measure(function, count, returned_seconds=False):
    function()  # warm-up
    vals = []
    for _ in range(count):
        t0 = time.perf_counter()
        elapsed = function()
        vals.append(elapsed if returned_seconds else time.perf_counter() - t0)
    us = np.asarray(vals, dtype=np.float64) * 1e6
    return {
        "min": float(np.min(us)),
        "mean": float(np.mean(us)),
        "max": float(np.max(us)),
        "std": float(np.std(us)),
        "p50": float(np.percentile(us, 50)),
        "p95": float(np.percentile(us, 95)),
    }


def report_stats(name, s):
    print("  %-34s min %9.2f | mean %9.2f | max %9.2f us" %
          (name, s["min"], s["mean"], s["max"]))
    print("  %-34s std %9.2f | p50  %9.2f | p95 %9.2f us" %
          ("", s["std"], s["p50"], s["p95"]))


def err_summary(actual, reference):
    diff = np.abs(actual.astype(np.float64) - reference.astype(np.float64))
    denom = np.linalg.norm(reference.astype(np.float64).ravel()) + 1e-12
    rel_l2 = np.linalg.norm(diff.ravel()) / denom
    return float(diff.max()), float(diff.mean()), float(rel_l2)


def main():
    from pynq import Overlay, allocate

    print("=" * 86)
    print("project_4 / Snake accelerator: functional and latency report")
    print("=" * 86)
    print("Board files : %s ; %s" % (BITFILE, HWHFILE))
    print("Active GEMM : (%d x %d) @ (%d x %d) -> (%d x %d)" %
          (M, K, K, ACTIVE_N, M, ACTIVE_N))
    print("HW workload : M=%d, K=%d, N=%d; BF16; output %d bytes" %
          (M, K, N, OUTPUT_WORDS * 8))
    print("Padding     : B columns %d..%d are zero; hardware still processes all columns." %
          (ACTIVE_N, N - 1))
    print("Normalization uses all 768 columns; masked Softmax uses the valid mask.")
    print("Benchmark   : %d runs per operation; random seed %d" % (RUNS, SEED))
    for op, label in OPS.items():
        print("  op=%d -> %s" % (op, label))

    if not BITFILE.is_file():
        raise FileNotFoundError("Missing bitstream: %s" % BITFILE)
    if not HWHFILE.is_file():
        raise FileNotFoundError("Missing HWH metadata: %s" % HWHFILE)

    print("\n[1] Loading bitstream and discovering PL IP...")
    ol = Overlay(str(BITFILE), download=True)
    names = ("snake_acc_axi_0", "dma_a", "dma_b", "dma_out")
    absent = [name for name in names if not hasattr(ol, name)]
    if absent:
        raise RuntimeError("HWH is missing PL objects: " + ", ".join(absent))
    ctrl = ol.snake_acc_axi_0
    da, db, dout = ol.dma_a, ol.dma_b, ol.dma_out
    print("  Discovered :", ", ".join(names))
    print("  Status     :", read_status(ctrl))

    a_words, b_words = (x.reshape(-1) for x in make_inputs())
    a_cpu = bf16_to_f32(a_words).reshape(M, K)
    b_cpu = bf16_to_f32(b_words).reshape(K, N)

    ext_rng = np.random.default_rng(SEED + 1)
    w_up_fp = np.zeros((K, N), dtype=np.float32)
    w_up_fp[:, :ACTIVE_N] = ext_rng.uniform(-0.2, 0.3, (K, ACTIVE_N))
    w_up_words = f32_to_bf16(w_up_fp).reshape(-1)
    gamma_words = f32_to_bf16(ext_rng.uniform(0.75, 1.25, N))
    beta_words = f32_to_bf16(ext_rng.uniform(-0.1, 0.1, N))
    mask_bool = np.zeros(N, dtype=bool)
    mask_bool[:ACTIVE_N] = True
    mask_bool[:ACTIVE_N:5] = False
    mask_words = f32_to_bf16(mask_bool.astype(np.float32))
    aux_words = np.concatenate((gamma_words, beta_words, mask_words, w_up_words))
    if aux_words.size != AUX_WORDS:
        raise AssertionError("auxiliary frame length mismatch")
    w_up_cpu = bf16_to_f32(w_up_words).reshape(K, N)
    gamma_cpu, beta_cpu = bf16_to_f32(gamma_words), bf16_to_f32(beta_words)

    a_buf = allocate((M * K,), dtype=np.uint16)
    b_buf = allocate((K * N,), dtype=np.uint16)
    aux_buf = allocate((AUX_WORDS,), dtype=np.uint16)
    out_buf = allocate((OUTPUT_WORDS,), dtype=np.uint64)
    a_buf[:] = a_words
    b_buf[:] = b_words
    aux_buf[:] = aux_words
    try:
        print("\n[2] Input and transfer sizes")
        print("  A: %d BF16 = %d bytes; B: %d BF16 = %d bytes" %
              (a_buf.size, a_buf.nbytes, b_buf.size, b_buf.nbytes))
        print("  output: %d x 64-bit beats = %d bytes" %
              (out_buf.size, out_buf.nbytes))
        print("  auxiliary: %d BF16 = %d bytes (gamma, beta, mask, W_up)" %
              (aux_buf.size, aux_buf.nbytes))
        print("  A first values: %s" % ["%04X" % int(v) for v in a_words[:8]])
        print("  B first values: %s" % ["%04X" % int(v) for v in b_words[:8]])
        print("  A decoded BF16:\n", a_cpu)
        print("  B active block (first 8 of %d columns):\n" % ACTIVE_N, b_cpu[:, :8])

        print("\n[3] Verify matrix multiplication and all Snake operations")
        t_first = run_first(ctrl, da, db, dout, a_buf, b_buf, out_buf, 7)
        mm_hw = to_matrix(out_buf)
        mm_cpu = cpu_pipeline(7, a_cpu, b_cpu)
        mm_max, mm_mean, mm_l2 = err_summary(mm_hw, mm_cpu)
        print("  Initial A/B load + GEMM + output DMA: %.2f us" % (t_first * 1e6))
        print("  GEMM max_abs=%g mean_abs=%g relative_L2=%g" % (mm_max, mm_mean, mm_l2))
        print("  GEMM CPU active output (first 8 columns):\n", mm_cpu[:, :8])
        print("  GEMM FPGA active output (first 8 columns):\n", mm_hw[:, :8])
        if not np.all(np.isfinite(mm_hw)) or not np.allclose(mm_hw, mm_cpu, rtol=0.02, atol=0.002):
            raise AssertionError("GEMM does not match BF16 CPU reference")
        print("  GEMM check: PASS")

        # Each operation reruns the integrated PE first, then the selected Snake
        # function. A/B are resident in the accelerator and do not need re-DMA.
        fpga_times = {}
        cpu_times = {}
        checks = {7: True}
        for op in (0, 1, 2, 3, 4):
            run_loaded(ctrl, dout, out_buf, op)
            got = to_matrix(out_buf).copy()
            expected = cpu_reference(op, mm_cpu)
            max_abs, mean_abs, rel_l2 = err_summary(got, expected)
            active_errors = err_summary(got[:, :ACTIVE_N], expected[:, :ACTIVE_N])
            passed = bool(np.all(np.isfinite(got)) and rel_l2 <= REL_L2_LIMIT and
                          active_errors[2] <= REL_L2_LIMIT)
            fpga_times[op] = measure(lambda op=op: run_loaded(ctrl, dout, out_buf, op),
                                     RUNS, returned_seconds=True)
            # End-to-end CPU reference includes its own GEMM on every sample,
            # matching the integrated PL operation (GEMM plus Snake function).
            cpu_times[op] = measure(lambda op=op: cpu_pipeline(op, a_cpu, b_cpu), RUNS)
            print("\n  op=%d %s" % (op, OPS[op]))
            print("    output range [%.7g, %.7g], mean %.7g, std %.7g" %
                  (float(got.min()), float(got.max()), float(got.mean()), float(got.std())))
            print("    CPU-reference error: max_abs=%g mean_abs=%g relative_L2=%g" %
                  (max_abs, mean_abs, rel_l2))
            print("    Active %d-column error: max_abs=%g mean_abs=%g relative_L2=%g" %
                  ((ACTIVE_N,) + active_errors))
            print("    CPU row 0, first 8 active values :", expected[0, :8])
            print("    FPGA row 0, first 8 active values:", got[0, :8])
            if op == 0:
                print("    Softmax row sums: %s" %
                      ["%.7f" % float(v) for v in got.sum(axis=1)])
                if (float(got.min()) < -0.02 or float(got.max()) > 1.02 or
                        not np.allclose(got.sum(axis=1), 1.0, atol=0.08, rtol=0)):
                    passed = False
                print("    Active columns' probability mass:", got[:, :ACTIVE_N].sum(axis=1))
                print("    Active probability mass need not equal 1; zero logits still contribute.")
            if op == 4:
                print("    Extra comparison vs upstream tanh GELU: max_abs=%g mean_abs=%g relative_L2=%g" %
                      err_summary(got, github_gelu_reference(mm_cpu)))
                print("    Numerical check and CPU timing use the RTL sigmoid GELU definition.")
            checks[op] = passed
            print("    Numerical check (finite, full/active relative L2 <= %.3f): %s" %
                  (REL_L2_LIMIT, "PASS" if passed else "FAIL"))

        print("\n[4] Load extension parameters and verify ops 8-11")
        aux_buf.flush()
        t_aux0 = time.perf_counter()
        ctrl.write(0x08, 1)
        db.sendchannel.transfer(aux_buf)
        db.sendchannel.wait()
        aux_buf.invalidate()
        t_aux = time.perf_counter() - t_aux0
        aux_status = assert_ready(ctrl, "auxiliary frame DMA complete")
        if not aux_status["aux_loaded"]:
            raise RuntimeError("auxiliary DMA completed without aux_loaded status")
        print("  Loaded %d BF16 auxiliary words (%d bytes) in %.2f us" %
              (aux_buf.size, aux_buf.nbytes, t_aux * 1e6))
        print("  Masked Softmax valid columns: %d of %d" %
              (int(np.count_nonzero(mask_bool)), N))

        mm_up_cpu = cpu_pipeline(7, a_cpu, w_up_cpu)
        for op in (8, 9, 10, 11):
            run_loaded(ctrl, dout, out_buf, op)
            got = to_matrix(out_buf).copy()
            expected = extended_reference(op, mm_cpu, mm_up_cpu,
                                          gamma_cpu, beta_cpu, mask_bool)
            max_abs, mean_abs, rel_l2 = err_summary(got, expected)
            active_errors = err_summary(got[:, :ACTIVE_N], expected[:, :ACTIVE_N])
            passed = bool(np.all(np.isfinite(got)) and rel_l2 <= REL_L2_LIMIT and
                          active_errors[2] <= REL_L2_LIMIT)
            if op == 10:
                masked_max = float(np.max(np.abs(got[:, ~mask_bool])))
                row_sums = got.sum(axis=1)
                passed = passed and masked_max <= 2.0e-3 and np.allclose(
                    row_sums, 1.0, atol=0.03, rtol=0)
                print("    masked_max_abs=%.6g row_sums=%s" %
                      (masked_max, ["%.7f" % float(v) for v in row_sums]))
            if op == 11:
                print("    Reference: two BF16 GEMMs, BF16 SiLU intermediate, then product")

            fpga_times[op] = measure(lambda op=op: run_loaded(ctrl, dout, out_buf, op),
                                     RUNS, returned_seconds=True)
            cpu_times[op] = measure(
                lambda op=op: cpu_extended_pipeline(
                    op, a_cpu, b_cpu, w_up_cpu, gamma_cpu, beta_cpu, mask_bool), RUNS)
            checks[op] = passed
            print("  op=%d %-28s max_abs=%9.4g mean_abs=%9.4g rel_L2=%8.5f %s" %
                  (op, OPS[op], max_abs, mean_abs, rel_l2,
                   "PASS" if passed else "FAIL"))
            print("    Active %d-column rel_L2=%.6g; output range [%.7g, %.7g]" %
                  (ACTIVE_N, active_errors[2], float(got.min()), float(got.max())))

        print("\n[5] Repeated-run latency statistics (%d samples, warmed up)" % RUNS)
        print("  FPGA scope: receive-DMA submission + AXI-Lite start + PL computation +")
        print("              output DMA/cache invalidation + completion/status checks.")
        print("              Output clear/flush and A/B upload are excluded from these samples.")
        print("  CPU scope : NumPy float32 GEMM + selected function + BF16 rounding on ARM.")
        print("              CPU and FPGA both process the full padded (%d, %d, %d) workload." % (M, K, N))
        print("              This is not a latency measurement of an unpadded 128-column core.")
        print("  Note      : ops 0-4, 8-10 include one GEMM; op 11 includes two GEMMs.")
        print("  Extension parameter DMA is reported separately, outside repeated samples.")
        for op in (7, 0, 1, 2, 3, 4, 8, 9, 10, 11):
            if op == 7:
                # Matrix multiply only, measured with the same output DMA path.
                fpga_times[op] = measure(lambda: run_loaded(ctrl, dout, out_buf, 7),
                                         RUNS, returned_seconds=True)
                cpu_times[op] = measure(lambda: cpu_pipeline(7, a_cpu, b_cpu), RUNS)
            print("\n  op=%d %s" % (op, OPS[op]))
            report_stats("FPGA end-to-end", fpga_times[op])
            report_stats("CPU full software pipeline", cpu_times[op])
            print("  %-34s %8.3fx (CPU mean / FPGA mean)" %
                  ("Mean latency ratio", cpu_times[op]["mean"] / fpga_times[op]["mean"]))

        print("\n[6] Summary and interpretation")
        print("  %-30s %10s %12s %12s %10s" %
              ("Operation", "Check", "CPU mean/us", "FPGA mean/us", "CPU/FPGA"))
        for op in (7, 0, 1, 2, 3, 4, 8, 9, 10, 11):
            print("  %-30s %10s %12.2f %12.2f %9.3fx" %
                  (OPS[op], "PASS" if checks[op] else "FAIL", cpu_times[op]["mean"],
                   fpga_times[op]["mean"], cpu_times[op]["mean"] / fpga_times[op]["mean"]))
        print("  First-transfer latency (includes A/B DMA): %.2f us" % (t_first * 1e6))
        print("  Extension auxiliary-frame upload (one-time): %.2f us" % (t_aux * 1e6))
        print("  Repeated operation latencies exclude A/B upload, but include output DMA.")
        print("  CPU comparison is software NumPy on the same ARM board, not desktop CPU.")
        print("  Ratio > 1 means FPGA is faster; ratio < 1 means CPU is faster.")
        print("  These are host-observed latencies, not isolated PL compute cycles.")
        print("  Numerical relative-L2 limit %.3f is this script's chosen acceptance limit." % REL_L2_LIMIT)
        print("  The padded workload and Python/DMA overhead can favor the CPU at this size.")
        print("  All operations completed; final status:", read_status(ctrl))
        failed = [str(op) for op, ok in checks.items() if not ok]
        print("  OVERALL: %s" % ("FAIL (op=" + ",".join(failed) + ")" if failed else "PASS"))
        print("=" * 86)
        if failed:
            raise AssertionError("Numerical validation failed for op=" + ",".join(failed))
    finally:
        a_buf.freebuffer()
        b_buf.freebuffer()
        aux_buf.freebuffer()
        out_buf.freebuffer()


if __name__ == "__main__":
    main()
