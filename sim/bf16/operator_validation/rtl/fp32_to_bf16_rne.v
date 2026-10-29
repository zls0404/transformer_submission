`timescale 1ns / 1ps

// IEEE-754 single precision to BF16, round-to-nearest-even.
module fp32_to_bf16_rne (
    input  wire [31:0] fp32,
    output wire [15:0] bf16
);
    wire [15:0] upper = fp32[31:16];
    wire        round_up = fp32[15] & (|fp32[14:0] | fp32[16]);
    wire [16:0] rounded = {1'b0, upper} + round_up;
    wire        is_nan = (&fp32[30:23]) & (|fp32[22:0]);

    assign bf16 = is_nan ? {fp32[31], 8'hff, 7'h7f} : rounded[15:0];
endmodule
