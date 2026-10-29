`timescale 1ns/1ps
// Horizontal activation forwarding takes one cycle per column, just as in
// accelerator-master/sourcecode/core/PE_line.v. Each PE has its OWN weight.
module bf16_pe_line #(
    parameter integer COLS=4, MUL_LATENCY=6, ADD_LATENCY=11
) (
    input wire clk, rst_n, set_w, valid_in,
    input wire [15:0] x_in,
    input wire [COLS*16-1:0] w_packed,
    input wire [COLS*32-1:0] psum_in,
    output wire [15:0] x_out,
    output wire [COLS*32-1:0] psum_out,
    output wire [COLS-1:0] valid_out
);
    wire [15:0] x_link [0:COLS];
    wire [COLS:0] x_valid;
    assign x_link[0]=x_in;
    assign x_out=x_link[COLS];
    assign x_valid[0]=valid_in;
    genvar c;
    generate for(c=0;c<COLS;c=c+1) begin: gen_pe
        pe_delay #(.WIDTH(1),.DEPTH(1)) u_x_valid
            (clk,rst_n,x_valid[c],x_valid[c+1]);
        bf16_pe #(.MUL_LATENCY(MUL_LATENCY),.ADD_LATENCY(ADD_LATENCY)) u_pe (
            .clk(clk),.rst_n(rst_n),.set_w(set_w),.valid_in(x_valid[c]),
            .x_in(x_link[c]),.w_in(w_packed[c*16+:16]),
            .psum_in(psum_in[c*32+:32]),
            .valid_out(valid_out[c]),.x_out(x_link[c+1]),
            .psum_out(psum_out[c*32+:32])
        );
    end endgenerate
endmodule
