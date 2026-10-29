`timescale 1ns / 1ps
// ===========================================================================
// Softmax_iscas2023.v -- ISCAS 2023 approximate Softmax reproduction
//
// Based on Algorithm 2 from:
//   "Hardware-efficient Softmax Approximation for Self-Attention Networks"
//   N. A. Koca, A. T. Do, C.-H. Chang, IEEE ISCAS 2023.
//
// The paper approximates Softmax by:
//   1) max-normalizing and adding 1 to the maximum,
//   2) replacing log2(e) with 1.5, implemented as x + x/2,
//   3) approximating 2^v with 1 + v/2 for the fractional part,
//   4) rounding the denominator sum to the nearest power of two,
//   5) replacing division with a right shift.
//
// This module keeps the same port contract and 3-pass replay schedule as the
// existing Softmax.v/Softmax_control.v so it can be selected in the same
// testbench and accelerator wrapper.
// ===========================================================================
module Softmax_iscas2023(
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
reg signed [19:0] x_sub_S9Q10;
reg signed [19:0] x_sub_S9Q10_delay1;
reg signed [19:0] x_sub_S9Q10_delay2;
reg signed [19:0] x_sub_S9Q10_delay3;
reg signed [19:0] x_sub_S9Q10_delay4;
reg signed [19:0] x_sub_S9Q10_delay5;
reg signed [19:0] x_sub_S9Q10_delay6;
reg [25:0] pow_sum_U12Q14;
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

reg [13:0] pow_sum_pipe1;
reg [13:0] pow_sum_pipe2;
reg [13:0] pow_sum_pipe3;
reg [13:0] pow_out_pipe1;
reg [13:0] pow_out_pipe2;
reg [13:0] pow_out_pipe3;

wire [1:0] stage;
wire signed [8:0] x_max_9b;
wire [13:0] pow_sum_U0Q14;
wire [13:0] pow_out_U0Q14;
wire [7:0] norm_out;

assign stage = cnt <= (length - 1) ? 2'd1 :
               (cnt <= (lengthX2 - 1) ? 2'd2 : 2'd3);
assign x_max_9b = data_in - data_in_max;
assign valid_out = (stage_delay10 == 3 && valid_in_delay10) ? 1'b1 : 1'b0;
assign out_last = (stage_delay10 == 3) & (stage_delay9 == 1);
assign pow_sum_U0Q14 = approx_pow_iscas_q14(x_sub_S9Q10_delay1);
assign pow_out_U0Q14 = approx_pow_iscas_q14(x_sub_S9Q10_delay6);
assign norm_out = normalize_pow2(pow_out_pipe3, denom_log2_hold, scale_out_delay9);

function [13:0] approx_pow_iscas_q14;
    input signed [19:0] x_S9Q10;
    reg signed [21:0] scaled_S11Q10;
    reg [21:0] abs_scaled_U11Q10;
    reg [11:0] int_part;
    reg [9:0] frac_Q10;
    reg [14:0] mant_Q14;
    reg [14:0] shifted_Q14;
    begin
        // Algorithm 2 line 6: mul = sub * 1.5 = sub + sub/2.
        scaled_S11Q10 = $signed(x_S9Q10) + ($signed(x_S9Q10) >>> 1);
        abs_scaled_U11Q10 = scaled_S11Q10[21] ? (~scaled_S11Q10 + 1'b1) : scaled_S11Q10;
        int_part = abs_scaled_U11Q10[21:10];
        frac_Q10 = abs_scaled_U11Q10[9:0];

        // Algorithm 2 line 7: 2^v ~= 1 + v/2 for v in [-1,0].
        // With abs fractional part f in [0,1), this is 1 - f/2.
        mant_Q14 = 15'd16384 - {2'b00, frac_Q10, 3'b000};

        if (int_part >= 12'd14)
            approx_pow_iscas_q14 = 14'd0;
        else begin
            shifted_Q14 = mant_Q14 >> int_part[3:0];
            approx_pow_iscas_q14 = shifted_Q14[14] ? 14'h3FFF : shifted_Q14[13:0];
        end
    end
endfunction

function [4:0] nearest_log2_26;
    input [25:0] value;
    integer idx;
    reg [4:0] floor_log2;
    reg [25:0] threshold;
    begin
        floor_log2 = 5'd0;
        for (idx = 0; idx < 26; idx = idx + 1) begin
            if (value[idx])
                floor_log2 = idx;
        end

        if (value <= 26'd1) begin
            nearest_log2_26 = 5'd0;
        end
        else if (floor_log2 == 5'd25) begin
            nearest_log2_26 = 5'd25;
        end
        else if (floor_log2 == 0) begin
            nearest_log2_26 = (value >= 26'd2) ? 5'd1 : 5'd0;
        end
        else begin
            // midpoint between 2^k and 2^(k+1) is 1.5*2^k.
            threshold = (26'd1 << floor_log2) + (26'd1 << (floor_log2 - 1'b1));
            nearest_log2_26 = (value >= threshold) ? (floor_log2 + 1'b1) : floor_log2;
        end
    end
endfunction

function [7:0] normalize_pow2;
    input [13:0] pow_q14;
    input [4:0] denom_log2;
    input [3:0] out_scale;
    reg signed [6:0] shift_amt;
    reg [27:0] scaled;
    begin
        // pow_q14 / 2^denom_log2 * 2^out_scale.
        shift_amt = $signed({2'b00, denom_log2}) - $signed({3'b000, out_scale});
        if (shift_amt > 0)
            scaled = ({14'd0, pow_q14} + (28'd1 << (shift_amt[4:0] - 1'b1))) >> shift_amt[4:0];
        else if (shift_amt == 0)
            scaled = {14'd0, pow_q14};
        else
            scaled = {14'd0, pow_q14} << ((~shift_amt + 7'd1) & 7'h1F);

        normalize_pow2 = (|scaled[27:7]) ? 8'h7F : {1'b0, scaled[6:0]};
    end
endfunction

always @(*) begin
    if (scale_in == -1)
        x_sub_S9Q10 = ($signed(x_max_9b) <<< 11) - 20'sd1024;
    else if (scale_in < 10)
        x_sub_S9Q10 = ($signed(x_max_9b) <<< (5'd10 - scale_in[3:0])) - 20'sd1024;
    else
        x_sub_S9Q10 = $signed(x_max_9b) - 20'sd1024;
end

always @(posedge clk) begin
    data_out <= norm_out;
    length <= length_input;
end

always @(posedge clk) begin
    pow_sum_pipe1 <= pow_sum_U0Q14;
    pow_sum_pipe2 <= pow_sum_pipe1;
    pow_sum_pipe3 <= pow_sum_pipe2;
    pow_out_pipe1 <= pow_out_U0Q14;
    pow_out_pipe2 <= pow_out_pipe1;
    pow_out_pipe3 <= pow_out_pipe2;
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
    x_sub_S9Q10_delay1 <= x_sub_S9Q10;
    x_sub_S9Q10_delay2 <= x_sub_S9Q10_delay1;
    x_sub_S9Q10_delay3 <= x_sub_S9Q10_delay2;
    x_sub_S9Q10_delay4 <= x_sub_S9Q10_delay3;
    x_sub_S9Q10_delay5 <= x_sub_S9Q10_delay4;
    x_sub_S9Q10_delay6 <= x_sub_S9Q10_delay5;
end

always @(posedge clk) begin
    if (~rst_n)
        pow_sum_U12Q14 <= 0;
    else if (stage_delay4 == 2 && valid_in_delay4)
        pow_sum_U12Q14 <= pow_sum_U12Q14 + {12'd0, pow_sum_pipe3};
    else if (stage_delay4 == 1)
        pow_sum_U12Q14 <= 0;
end

always @(posedge clk) begin
    if (~rst_n)
        denom_log2_hold <= 5'd0;
    else if (stage_delay4 == 3 && stage_delay5 == 2)
        denom_log2_hold <= nearest_log2_26(pow_sum_U12Q14);
end

endmodule

// ===========================================================================
// Standalone controller version with LANES-way internal parallelism.
//
// External interface stays serial and compatible with Softmax_control's top_*:
// one int8 element is accepted per cycle and one int8 element is emitted per
// cycle. Internally, however, the Algorithm-2 pow/sum pass processes LANES
// elements per cycle. With LANES=4, a length-192 row changes from roughly
// 3*192 cycles to about 192 + 192/4 + 192 cycles, so latency drops without
// changing the surrounding scalar testbench.
// ===========================================================================
module Softmax_iscas2023_parallel #(
    parameter integer LANES = 4,
    parameter integer MAX_LENGTH = 1024
)(
    input                   clk,
    input                   rst_n,

    input [9:0]             length_input,
    input signed [4:0]      scale_in_input,
    input [3:0]             scale_out_input,

    input signed [7:0]      top_data_in,
    input                   top_valid_in,
    output                  top_ready_in,
    input                   top_last_in,

    output reg [7:0]        top_data_out,
    output reg              top_valid_out,
    output reg              top_last_out
);

localparam [1:0] S_FILL = 2'd0;
localparam [1:0] S_POW  = 2'd1;
localparam [1:0] S_POW_STORE = 2'd2;
localparam [1:0] S_OUT  = 2'd3;

reg [1:0] state;
reg [9:0] length;
reg signed [4:0] scale_in;
reg [3:0] scale_out;
reg [9:0] in_count;
reg [9:0] proc_index;
reg [9:0] out_count;
reg signed [7:0] row_max;
reg [25:0] pow_sum_U12Q14;
reg [4:0] denom_log2_hold;

reg signed [7:0] row_buf [0:MAX_LENGTH-1];
reg [13:0] pow_buf [0:MAX_LENGTH-1];

assign top_ready_in = (state == S_FILL) && (in_count < length_input);

integer calc_lane;
integer calc_addr;
integer store_lane;
integer store_addr;
reg [9:0] lane_addr_reg [0:LANES-1];
reg [13:0] lane_pow_reg [0:LANES-1];
reg [25:0] store_sum;

function [13:0] approx_pow_iscas_q14;
    input signed [19:0] x_S9Q10;
    reg signed [21:0] scaled_S11Q10;
    reg [21:0] abs_scaled_U11Q10;
    reg [11:0] int_part;
    reg [9:0] frac_Q10;
    reg [14:0] mant_Q14;
    reg [14:0] shifted_Q14;
    begin
        scaled_S11Q10 = $signed(x_S9Q10) + ($signed(x_S9Q10) >>> 1);
        abs_scaled_U11Q10 = scaled_S11Q10[21] ? (~scaled_S11Q10 + 1'b1) : scaled_S11Q10;
        int_part = abs_scaled_U11Q10[21:10];
        frac_Q10 = abs_scaled_U11Q10[9:0];
        mant_Q14 = 15'd16384 - {2'b00, frac_Q10, 3'b000};

        if (int_part >= 12'd14)
            approx_pow_iscas_q14 = 14'd0;
        else begin
            shifted_Q14 = mant_Q14 >> int_part[3:0];
            approx_pow_iscas_q14 = shifted_Q14[14] ? 14'h3FFF : shifted_Q14[13:0];
        end
    end
endfunction

function signed [19:0] make_sub_q10;
    input signed [7:0] x;
    input signed [7:0] max_x;
    input signed [4:0] in_scale;
    reg signed [8:0] diff;
    begin
        diff = x - max_x;
        if (in_scale == -1)
            make_sub_q10 = ($signed(diff) <<< 11) - 20'sd1024;
        else if (in_scale < 10)
            make_sub_q10 = ($signed(diff) <<< (5'd10 - in_scale[3:0])) - 20'sd1024;
        else
            make_sub_q10 = $signed(diff) - 20'sd1024;
    end
endfunction

function [4:0] nearest_log2_26;
    input [25:0] value;
    integer idx;
    reg [4:0] floor_log2;
    reg [25:0] threshold;
    begin
        floor_log2 = 5'd0;
        for (idx = 0; idx < 26; idx = idx + 1) begin
            if (value[idx])
                floor_log2 = idx;
        end

        if (value <= 26'd1) begin
            nearest_log2_26 = 5'd0;
        end
        else if (floor_log2 == 5'd25) begin
            nearest_log2_26 = 5'd25;
        end
        else if (floor_log2 == 0) begin
            nearest_log2_26 = (value >= 26'd2) ? 5'd1 : 5'd0;
        end
        else begin
            threshold = (26'd1 << floor_log2) + (26'd1 << (floor_log2 - 1'b1));
            nearest_log2_26 = (value >= threshold) ? (floor_log2 + 1'b1) : floor_log2;
        end
    end
endfunction

function [7:0] normalize_pow2;
    input [13:0] pow_q14;
    input [4:0] denom_log2;
    input [3:0] out_scale;
    reg signed [6:0] shift_amt;
    reg [27:0] scaled;
    begin
        shift_amt = $signed({2'b00, denom_log2}) - $signed({3'b000, out_scale});
        if (shift_amt > 0)
            scaled = ({14'd0, pow_q14} + (28'd1 << (shift_amt[4:0] - 1'b1))) >> shift_amt[4:0];
        else if (shift_amt == 0)
            scaled = {14'd0, pow_q14};
        else
            scaled = {14'd0, pow_q14} << ((~shift_amt + 7'd1) & 7'h1F);

        normalize_pow2 = (|scaled[27:7]) ? 8'h7F : {1'b0, scaled[6:0]};
    end
endfunction

always @(posedge clk) begin
    if (~rst_n) begin
        state <= S_FILL;
        length <= 10'd0;
        scale_in <= 5'sd0;
        scale_out <= 4'd0;
        in_count <= 10'd0;
        proc_index <= 10'd0;
        out_count <= 10'd0;
        row_max <= -8'sd128;
        pow_sum_U12Q14 <= 26'd0;
        denom_log2_hold <= 5'd0;
        top_data_out <= 8'd0;
        top_valid_out <= 1'b0;
        top_last_out <= 1'b0;
        for (store_lane = 0; store_lane < LANES; store_lane = store_lane + 1) begin
            lane_addr_reg[store_lane] <= 10'd0;
            lane_pow_reg[store_lane] <= 14'd0;
        end
    end
    else begin
        top_valid_out <= 1'b0;
        top_last_out <= 1'b0;

        case (state)
            S_FILL: begin
                if (in_count == 0) begin
                    length <= length_input;
                    scale_in <= scale_in_input;
                    scale_out <= scale_out_input;
                end

                if (top_valid_in && top_ready_in) begin
                    row_buf[in_count] <= top_data_in;
                    if (in_count == 0)
                        row_max <= top_data_in;
                    else if (top_data_in > row_max)
                        row_max <= top_data_in;

                    if (top_last_in || in_count == length_input - 1'b1) begin
                        in_count <= 10'd0;
                        proc_index <= 10'd0;
                        pow_sum_U12Q14 <= 26'd0;
                        state <= S_POW;
                    end
                    else begin
                        in_count <= in_count + 1'b1;
                    end
                end
            end

            S_POW: begin
                // Register one LANES-wide Algorithm-2 pow group per cycle.
                for (calc_lane = 0; calc_lane < LANES; calc_lane = calc_lane + 1) begin
                    calc_addr = proc_index + calc_lane;
                    lane_addr_reg[calc_lane] <= calc_addr[9:0];
                    if (calc_addr < length)
                        lane_pow_reg[calc_lane] <= approx_pow_iscas_q14(make_sub_q10(row_buf[calc_addr], row_max, scale_in));
                    else
                        lane_pow_reg[calc_lane] <= 14'd0;
                end
                state <= S_POW_STORE;
            end

            S_POW_STORE: begin
                store_sum = 26'd0;
                for (store_lane = 0; store_lane < LANES; store_lane = store_lane + 1) begin
                    store_addr = lane_addr_reg[store_lane];
                    if (store_addr < length)
                        pow_buf[store_addr] <= lane_pow_reg[store_lane];
                    store_sum = store_sum + {12'd0, lane_pow_reg[store_lane]};
                end
                pow_sum_U12Q14 <= pow_sum_U12Q14 + store_sum;

                if (proc_index + LANES >= length) begin
                    denom_log2_hold <= nearest_log2_26(pow_sum_U12Q14 + store_sum);
                    out_count <= 10'd0;
                    state <= S_OUT;
                end
                else begin
                    proc_index <= proc_index + LANES;
                    state <= S_POW;
                end
            end

            S_OUT: begin
                top_data_out <= normalize_pow2(pow_buf[out_count], denom_log2_hold, scale_out);
                top_valid_out <= 1'b1;
                top_last_out <= (out_count == length - 1'b1);

                if (out_count == length - 1'b1) begin
                    out_count <= 10'd0;
                    row_max <= -8'sd128;
                    state <= S_FILL;
                end
                else begin
                    out_count <= out_count + 1'b1;
                end
            end
        endcase
    end
end

endmodule
