`timescale 1ns/1ps
// Fixed wall-clock delay, including valid bubbles. DEPTH=0 is a wire.
module pe_delay #(parameter integer WIDTH=16, DEPTH=1) (
    input wire clk, rst_n,
    input wire [WIDTH-1:0] din,
    output wire [WIDTH-1:0] dout
);
    generate if (DEPTH == 0) begin : direct
        assign dout = din;
    end else begin : delayed
        reg [WIDTH-1:0] pipe [0:DEPTH-1];
        integer i;
        always @(posedge clk) begin
            if (!rst_n) begin
                for (i=0;i<DEPTH;i=i+1) pipe[i] <= 0;
            end else begin
                pipe[0] <= din;
                for (i=1;i<DEPTH;i=i+1) pipe[i] <= pipe[i-1];
            end
        end
        assign dout = pipe[DEPTH-1];
    end endgenerate
endmodule
