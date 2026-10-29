`timescale 1ns/1ps
// Standard synchronous-read FIFO: dout updates one cycle after rd_en.
// Matches GLUT_SNAKE_array's fifo*_rden_reg_delay1 convention. Resettable
// pointers allow independent frames without relying on power-up IP state.
module snake_frame_fifo #(parameter integer DEPTH=512) (
    input wire clk, rst_n, wr_en, rd_en,
    input wire [127:0] din,
    output reg [127:0] dout,
    output reg fault
);
    localparam integer AW=$clog2(DEPTH);
    reg [127:0] mem [0:DEPTH-1];
    reg [AW-1:0] wp,rp;
    reg [AW:0] count;
    always @(posedge clk) begin
        if (!rst_n) begin wp<=0; rp<=0; count<=0; dout<=0; fault<=0; end
        else begin
            if (wr_en && (count < DEPTH || rd_en)) begin
                mem[wp]<=din; wp<=wp+1'b1;
            end
            if (rd_en && count!=0) begin dout<=mem[rp]; rp<=rp+1'b1; end
            case ({wr_en,rd_en})
                2'b10: if (count<DEPTH) count<=count+1'b1;
                2'b01: if (count!=0) count<=count-1'b1;
                default: count<=count;
            endcase
            if ((rd_en && count==0) || (wr_en && !rd_en && count==DEPTH)) fault<=1;
        end
    end
endmodule
