`timescale 1ns/1ps
// accelerator-master PE_array topology adapted to floating-point pipelines.
// One input token describes K=ROWS activations, and produces COLS outputs.
// Weights: w_packed[(row*COLS+col)*16+:16]. Tokens may contain bubbles.
// Row skew = row*(MUL_LATENCY+ADD_LATENCY); column deskew = COLS-1-col.
module bf16_pe_array #(
    parameter integer ROWS=4, COLS=4, MUL_LATENCY=6, ADD_LATENCY=11
) (
    input wire clk, rst_n, set_w, valid_in,
    input wire [ROWS*16-1:0] x_packed,
    input wire [ROWS*COLS*16-1:0] w_packed,
    input wire [COLS*32-1:0] psum_in,
    output wire [ROWS*16-1:0] x_out,
    output wire [COLS*32-1:0] psum_out,
    output wire [COLS-1:0] valid_out
);
    localparam integer MAC_LATENCY=MUL_LATENCY+ADD_LATENCY;
    wire [COLS*32-1:0] psum_pipe [0:ROWS];
    wire [COLS-1:0] row_valid [0:ROWS-1];
    genvar r,c;
    generate
        for(c=0;c<COLS;c=c+1) begin: top_skew
            pe_delay #(.WIDTH(32),.DEPTH(c)) u_psum_skew
                (clk,rst_n,psum_in[c*32+:32],psum_pipe[0][c*32+:32]);
        end
        for(r=0;r<ROWS;r=r+1) begin: gen_row
            wire [16:0] delayed_x;
            pe_delay #(.WIDTH(17),.DEPTH(r*MAC_LATENCY)) u_row_skew
                (clk,rst_n,{valid_in,x_packed[r*16+:16]},delayed_x);
            bf16_pe_line #(.COLS(COLS),.MUL_LATENCY(MUL_LATENCY),
                           .ADD_LATENCY(ADD_LATENCY)) u_line (
                .clk(clk),.rst_n(rst_n),.set_w(set_w),.valid_in(delayed_x[16]),
                .x_in(delayed_x[15:0]),.w_packed(w_packed[r*COLS*16+:COLS*16]),
                .psum_in(psum_pipe[r]),.x_out(x_out[r*16+:16]),
                .psum_out(psum_pipe[r+1]),.valid_out(row_valid[r])
            );
        end
        for(c=0;c<COLS;c=c+1) begin: bottom_deskew
            wire [32:0] aligned;
            pe_delay #(.WIDTH(33),.DEPTH(COLS-1-c)) u_align
                (clk,rst_n,{row_valid[ROWS-1][c],psum_pipe[ROWS][c*32+:32]},aligned);
            assign valid_out[c]=aligned[32];
            assign psum_out[c*32+:32]=aligned[31:0];
        end
    endgenerate
endmodule
