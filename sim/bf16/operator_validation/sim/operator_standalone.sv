`timescale 1ns/1ps
// Test-only adapter around the UNMODIFIED shared Snake operator array.
// No matrix multiplier, PS, DMA, or AXI-Lite controller is instantiated.
// Input: four BF16 values per beat, lane 0 in bits [15:0].
// Output: original FP32 result plus the original integration's BF16 rounding.
// This interface has no ready/last: a nominal frame is 192 continuous beats.
module operator_standalone (
    input wire clk, rst_n,
    input wire [3:0] op,
    input wire in_valid,
    input wire [63:0] in_bf16,
    output wire out_valid,
    output wire [127:0] out_fp32,
    output wire [63:0] out_bf16,
    output wire fifo1_fault, fifo2_fault
);
    wire [127:0] f1_din, f1_dout, f2_din, f2_dout;
    wire f1_wr, f1_rd, f2_wr, f2_rd;
    GLUT_SNAKE_array core (
        .clk(clk), .rst_n(rst_n), .stage_start(rst_n), .configs(op),
        .input_atvalid(in_valid), .input_atdata(in_bf16),
        .input_btvalid(1'b0), .input_btdata(64'b0),
        .fifo1_din(f1_din), .fifo1_wr_en(f1_wr),
        .fifo1_dout(f1_dout), .fifo1_rd_en(f1_rd),
        .fifo2_din(f2_din), .fifo2_wr_en(f2_wr),
        .fifo2_dout(f2_dout), .fifo2_rd_en(f2_rd),
        .result_tvalid(out_valid), .result_tdata(out_fp32)
    );
    snake_frame_fifo fifo1(clk, rst_n, f1_wr, f1_rd, f1_din, f1_dout, fifo1_fault);
    snake_frame_fifo fifo2(clk, rst_n, f2_wr, f2_rd, f2_din, f2_dout, fifo2_fault);
    genvar lane;
    generate for (lane=0; lane<4; lane=lane+1) begin : rounding
        fp32_to_bf16_rne round_result(out_fp32[lane*32+:32], out_bf16[lane*16+:16]);
    end endgenerate
endmodule
