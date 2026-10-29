`timescale 1ns/1ps
// Weight-stationary PE. BF16 operands are widened exactly to FP32.
// Separate FP32 multiply and add (not fused); one token per clock.
// set_w must occur before the first token; never overwrite an active tile.
module bf16_pe #(parameter integer MUL_LATENCY=6, ADD_LATENCY=11) (
    input wire clk, rst_n, set_w, valid_in,
    input wire [15:0] x_in, w_in,
    input wire [31:0] psum_in,
    output wire valid_out,
    output reg [15:0] x_out,
    output wire [31:0] psum_out
);
    reg [15:0] weight_reg;
    wire [31:0] product, delayed_psum;
    wire product_valid, sum_valid, token_valid;
    always @(posedge clk) begin
        if (!rst_n) begin weight_reg<=0; x_out<=0; end
        else begin
            if (set_w) weight_reg<=w_in;
            x_out<=x_in;
        end
    end
    pe_delay #(.WIDTH(32), .DEPTH(MUL_LATENCY)) u_psum_delay
        (clk, rst_n, psum_in, delayed_psum);
    // IPs have no reset. This parallel token pipeline suppresses pre-reset
    // results until all arithmetic for a new token has completed.
    pe_delay #(.WIDTH(1), .DEPTH(MUL_LATENCY+ADD_LATENCY)) u_token_delay
        (clk, rst_n, valid_in & rst_n, token_valid);
    floating_mul u_mul (
        .aclk(clk),
        .s_axis_a_tvalid(valid_in & rst_n), .s_axis_a_tdata({x_in,16'b0}),
        .s_axis_b_tvalid(valid_in & rst_n), .s_axis_b_tdata({weight_reg,16'b0}),
        .m_axis_result_tvalid(product_valid), .m_axis_result_tdata(product)
    );
    floating_add u_add (
        .aclk(clk),
        .s_axis_a_tvalid(product_valid & rst_n), .s_axis_a_tdata(product),
        .s_axis_b_tvalid(product_valid & rst_n), .s_axis_b_tdata(delayed_psum),
        .m_axis_result_tvalid(sum_valid), .m_axis_result_tdata(psum_out)
    );
    assign valid_out = sum_valid & token_valid & rst_n;
endmodule
