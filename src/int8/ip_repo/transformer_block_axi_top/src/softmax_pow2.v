`timescale 1ns / 1ps
// ===========================================================================
// Softmax_pow2.v -- power-of-two denominator approximate Softmax
//
// Drop-in alternative for Softmax.v. It keeps the same 3-pass contract used by
// Softmax_control.v, but replaces the final ln(sum)+exp(x-ln(sum)) path with a
// cheaper power-of-two denominator:
//
//   y_i ~= exp(x_i - max) / 2^ceil(log2(sum_j exp(x_j - max)))
//
// This follows the common E2Softmax-style hardware idea: replace the costly
// normalization divide with a leading-one detector and shift. Accuracy is lower
// than the baseline Softmax.v, but the datapath removes Ln_module and the
// second exponential's log-sum dependency, making it useful as a reproducible
// hardware approximation experiment.
//
// Interface and timing intentionally mirror Softmax.v so the control wrapper
// can select this module with a parameter.
// ===========================================================================
module Softmax_pow2(
    input                   clk,
    input                   rst_n,

    input [9:0]             length_input,
    input [10:0]            lengthX2,
    input [11:0]            lengthX3,
    input signed [4:0]      scale_in,
    input [3:0]             scale_out,
    input signed [7:0]      data_in,
    input                   valid_in,

    output reg [7:0]        data_out,
    output                  valid_out,
    output                  out_last
);

(*MAX_FANOUT = 25 *) reg [9:0] length;
reg valid_in_delay1;
reg valid_in_delay2;
reg valid_in_delay3;
reg valid_in_delay4;
reg valid_in_delay5;
reg valid_in_delay6;
reg valid_in_delay7;
reg valid_in_delay8;
reg valid_in_delay9;
reg valid_in_delay10;
reg [15:0] cnt;
reg signed [7:0] data_in_max;
reg signed [19:0] x_max_S9Q10;
reg signed [19:0] x_max_S9Q10_delay1;
reg signed [19:0] x_max_S9Q10_delay2;
reg signed [19:0] x_max_S9Q10_delay3;
reg signed [19:0] x_max_S9Q10_delay4;
reg signed [19:0] x_max_S9Q10_delay5;
reg signed [19:0] x_max_S9Q10_delay6;
reg [21:0] e_sum_U10Q12;
reg [4:0] denom_log2_hold;
reg [1:0] stage_delay1;
reg [1:0] stage_delay2;
reg [1:0] stage_delay3;
reg [1:0] stage_delay4;
reg [1:0] stage_delay5;
reg [1:0] stage_delay6;
reg [1:0] stage_delay7;
reg [1:0] stage_delay8;
reg [1:0] stage_delay9;
reg [1:0] stage_delay10;
reg [3:0] scale_out_delay1;
reg [3:0] scale_out_delay2;
reg [3:0] scale_out_delay3;
reg [3:0] scale_out_delay4;
reg [3:0] scale_out_delay5;
reg [3:0] scale_out_delay6;
reg [3:0] scale_out_delay7;
reg [3:0] scale_out_delay8;
reg [3:0] scale_out_delay9;

wire [1:0] stage;
wire signed [8:0] x_max_9b;
wire [11:0] exp_U0Q12;
wire [13:0] exp_U0Q14_out;
wire [7:0] pow2_out;

assign stage = cnt <= (length - 1) ? 2'd1 :
               (cnt <= (lengthX2 - 1) ? 2'd2 : 2'd3);
assign x_max_9b = data_in - data_in_max;
assign valid_out = (stage_delay10 == 3 && valid_in_delay10) ? 1'b1 : 1'b0;
assign out_last = (stage_delay10 == 3) & (stage_delay9 == 1);

function [4:0] ceil_log2_22;
    input [21:0] value;
    reg [21:0] v_minus_1;
    begin
        if (value <= 22'd1) begin
            ceil_log2_22 = 5'd0;
        end
        else begin
            v_minus_1 = value - 22'd1;
            if      (v_minus_1[21]) ceil_log2_22 = 5'd22;
            else if (v_minus_1[20]) ceil_log2_22 = 5'd21;
            else if (v_minus_1[19]) ceil_log2_22 = 5'd20;
            else if (v_minus_1[18]) ceil_log2_22 = 5'd19;
            else if (v_minus_1[17]) ceil_log2_22 = 5'd18;
            else if (v_minus_1[16]) ceil_log2_22 = 5'd17;
            else if (v_minus_1[15]) ceil_log2_22 = 5'd16;
            else if (v_minus_1[14]) ceil_log2_22 = 5'd15;
            else if (v_minus_1[13]) ceil_log2_22 = 5'd14;
            else if (v_minus_1[12]) ceil_log2_22 = 5'd13;
            else if (v_minus_1[11]) ceil_log2_22 = 5'd12;
            else if (v_minus_1[10]) ceil_log2_22 = 5'd11;
            else if (v_minus_1[9])  ceil_log2_22 = 5'd10;
            else if (v_minus_1[8])  ceil_log2_22 = 5'd9;
            else if (v_minus_1[7])  ceil_log2_22 = 5'd8;
            else if (v_minus_1[6])  ceil_log2_22 = 5'd7;
            else if (v_minus_1[5])  ceil_log2_22 = 5'd6;
            else if (v_minus_1[4])  ceil_log2_22 = 5'd5;
            else if (v_minus_1[3])  ceil_log2_22 = 5'd4;
            else if (v_minus_1[2])  ceil_log2_22 = 5'd3;
            else if (v_minus_1[1])  ceil_log2_22 = 5'd2;
            else                    ceil_log2_22 = 5'd1;
        end
    end
endfunction

function [7:0] normalize_pow2;
    input [13:0] exp_q14;
    input [4:0] sum_log2;
    input [3:0] out_scale;
    reg signed [6:0] shift_amt;
    reg [27:0] scaled;
    begin
        // exp_q14 / sum_q12 * 2^out_scale ~= exp_q14 >> (log2(sum_q12)+2-out_scale)
        shift_amt = $signed({2'b00, sum_log2}) + 7'sd2 - $signed({3'b000, out_scale});
        if (shift_amt > 0)
            scaled = ({14'd0, exp_q14} + (28'd1 << (shift_amt[4:0] - 1'b1))) >> shift_amt[4:0];
        else if (shift_amt == 0)
            scaled = {14'd0, exp_q14};
        else
            scaled = {14'd0, exp_q14} << ((~shift_amt + 7'd1) & 7'h1F);

        normalize_pow2 = (|scaled[27:7]) ? 8'h7F : {1'b0, scaled[6:0]};
    end
endfunction

assign pow2_out = normalize_pow2(exp_U0Q14_out, denom_log2_hold, scale_out_delay9);

always @(*) begin
    if (scale_in == -1)
        x_max_S9Q10 = $signed(x_max_9b) <<< 11;
    else if (scale_in < 10)
        x_max_S9Q10 = $signed(x_max_9b) <<< (5'd10 - scale_in[3:0]);
    else
        x_max_S9Q10 = x_max_9b;
end

always @(posedge clk) begin
    data_out <= pow2_out;
    length <= length_input;
end

always @(posedge clk) begin
    stage_delay1 <= stage;
    stage_delay2 <= stage_delay1;
    stage_delay3 <= stage_delay2;
    stage_delay4 <= stage_delay3;
    stage_delay5 <= stage_delay4;
    stage_delay6 <= stage_delay5;
    stage_delay7 <= stage_delay6;
    stage_delay8 <= stage_delay7;
    stage_delay9 <= stage_delay8;
    stage_delay10 <= stage_delay9;
end

always @(posedge clk) begin
    scale_out_delay1 <= scale_out;
    scale_out_delay2 <= scale_out_delay1;
    scale_out_delay3 <= scale_out_delay2;
    scale_out_delay4 <= scale_out_delay3;
    scale_out_delay5 <= scale_out_delay4;
    scale_out_delay6 <= scale_out_delay5;
    scale_out_delay7 <= scale_out_delay6;
    scale_out_delay8 <= scale_out_delay7;
    scale_out_delay9 <= scale_out_delay8;
end

always @(posedge clk) begin
    valid_in_delay1 <= valid_in;
    valid_in_delay2 <= valid_in_delay1;
    valid_in_delay3 <= valid_in_delay2;
    valid_in_delay4 <= valid_in_delay3;
    valid_in_delay5 <= valid_in_delay4;
    valid_in_delay6 <= valid_in_delay5;
    valid_in_delay7 <= valid_in_delay6;
    valid_in_delay8 <= valid_in_delay7;
    valid_in_delay9 <= valid_in_delay8;
    valid_in_delay10 <= valid_in_delay9;
end

initial begin
    cnt = 0;
end

always @(posedge clk) begin
    if (~rst_n)
        cnt <= 0;
    else begin
        if (cnt == 0 && valid_in)
            cnt <= 1;
        else if (cnt == 0)
            cnt <= cnt;
        else if (cnt == lengthX3 - 1)
            cnt <= 0;
        else if (valid_in)
            cnt <= cnt + 1;
        else
            cnt <= cnt;
    end
end

always @(posedge clk) begin
    if (~rst_n)
        data_in_max <= 8'b1111_1111;
    else if (cnt == lengthX3 - 1)
        data_in_max <= 8'b1111_1111;
    else if (valid_in && stage == 1)
        data_in_max <= (data_in_max > data_in) ? data_in_max : data_in;
end

always @(posedge clk) begin
    x_max_S9Q10_delay1 <= x_max_S9Q10;
    x_max_S9Q10_delay2 <= x_max_S9Q10_delay1;
    x_max_S9Q10_delay3 <= x_max_S9Q10_delay2;
    x_max_S9Q10_delay4 <= x_max_S9Q10_delay3;
    x_max_S9Q10_delay5 <= x_max_S9Q10_delay4;
    x_max_S9Q10_delay6 <= x_max_S9Q10_delay5;
end

always @(posedge clk) begin
    if (~rst_n)
        e_sum_U10Q12 <= 0;
    else if (stage_delay4 == 2 && valid_in_delay4)
        e_sum_U10Q12 <= e_sum_U10Q12 + {10'd0, exp_U0Q12};
    else if (stage_delay4 == 1)
        e_sum_U10Q12 <= 0;
end

always @(posedge clk) begin
    if (~rst_n)
        denom_log2_hold <= 5'd0;
    else if (stage_delay4 == 3 && stage_delay5 == 2)
        denom_log2_hold <= ceil_log2_22(e_sum_U10Q12);
end

wire [24:0] exp_U0Q25;
assign exp_U0Q12 = exp_U0Q25[24:13];

Exp_module u_Exp_module_sum(
    .clk(clk),
    .x_S9Q10(x_max_S9Q10_delay1),
    .y_U0Q25_reg1(exp_U0Q25)
);

wire [24:0] exp_U0Q25_out;
assign exp_U0Q14_out = exp_U0Q25_out[24:11];

Exp_module u_Exp_module_out(
    .clk(clk),
    .x_S9Q10(x_max_S9Q10_delay6),
    .y_U0Q25_reg1(exp_U0Q25_out)
);

endmodule
