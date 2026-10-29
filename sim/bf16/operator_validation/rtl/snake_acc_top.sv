`timescale 1ns/1ps
// Integrated BF16 GEMM -> original Snake nonlinear datapath.
// A[M,K], B[K,768] are loaded row-major (low 16 bits = one BF16).
// The fixed N=768 preserves the upstream normalization constants/framing.
// Each Kx4 weight tile is loaded once per output group. Row buffers convert
// intermittent PE tiles into 192 uninterrupted four-lane Snake beats.
// Extended ops: 8 affine LayerNorm, 9 affine RMSNorm, 10 masked Softmax,
// 11 SwiGLU. After loading A/B, write aux_load and send gamma[N], beta[N],
// mask[N] (BF16 0/1), then W_up[K*N] over the existing B stream.
// No PS/DDR controller is required for this operator-level streaming top.
module snake_acc_top #(parameter integer M=2, K=4) (
    input wire ap_clk, ap_resetn,
    input wire start,
    input wire [3:0] op,
    input wire [15:0] s_axis_a_tdata,
    input wire s_axis_a_tvalid,
    output wire s_axis_a_tready,
    input wire [15:0] s_axis_b_tdata,
    input wire s_axis_b_tvalid,
    output wire s_axis_b_tready,
    input wire aux_load,
    output wire a_loaded, b_loaded, aux_loaded,
    output wire [63:0] m_axis_tdata,
    output wire m_axis_tvalid, m_axis_tlast,
    input wire m_axis_tready,
    output reg busy, done, error,
    // Observability: one pulse per four MM outputs, before BF16 rounding.
    output wire mm_tvalid,
    output wire [127:0] mm_fp32,
    output wire [63:0] mm_bf16
);
    localparam integer N=768, BEATS=N/4, AUX_WORDS=(K+3)*N;
    localparam [3:0] IDLE=0, LOAD_TILE=1, ISSUE=2, WAIT_MM=3,
        RESET_SNAKE=4, ARM_SNAKE=5, FEED_SNAKE=6, WAIT_SNAKE=7,
        NEXT_ROW=8, DRAIN=9;
    reg [3:0] state, op_reg;
    reg aux_loading, proj_up, snake_phase;
    reg [15:0] a_mem [0:M*K-1];
    // One synchronous BRAM bank per PE weight: preserve the original tile
    // read latency without a 16-port, 49152-bit register-file implementation.
    localparam integer BW=$clog2(BEATS), KW=(K>1 ? $clog2(K) : 1);
    reg [KW-1:0] b_write_row;
    reg [BW-1:0] b_write_tile;
    reg [1:0] b_write_lane;
    reg [KW-1:0] up_write_row;
    reg [BW-1:0] up_write_tile;
    reg [1:0] up_write_lane;
    reg [63:0] row_mem [0:BEATS-1];
    reg [63:0] up_row_mem [0:BEATS-1];
    reg [63:0] silu_row_mem [0:BEATS-1];
    reg [63:0] result_mem [0:M*BEATS-1];
    reg [15:0] gamma_mem [0:N-1];
    reg [15:0] beta_mem [0:N-1];
    reg [15:0] mask_mem [0:N-1];
    integer a_count,b_count,aux_count,row_idx,tile_idx,feed_idx,recv_count;
    integer produced,consumed,timer,affine_count_row,affine_mul_count;
    reg [K*16-1:0] x_tile;
    reg [K*4*16-1:0] w_tile;
    wire [3:0] snake_op = (op_reg==8) ? 4'd1 : (op_reg==9) ? 4'd2 :
                          (op_reg==10) ? 4'd0 :
                          (op_reg==11) ? (snake_phase ? 4'd6 : 4'd3) : op_reg;
    wire [BW-1:0] safe_feed_idx = (feed_idx<BEATS) ? feed_idx[BW-1:0] : {BW{1'b0}};
    wire [BW-1:0] safe_recv_idx = (recv_count<BEATS) ? recv_count[BW-1:0] : {BW{1'b0}};
    wire [BW-1:0] safe_mul_idx = (affine_mul_count<BEATS) ? affine_mul_count[BW-1:0] : {BW{1'b0}};
    wire [3:0] pe_valid;
    wire pe_set_w=(state==ISSUE);
    wire pe_input_valid=(state==WAIT_MM && timer==0);
    assign mm_tvalid=(state==WAIT_MM) && (&pe_valid);
    assign a_loaded=(a_count==M*K);
    assign b_loaded=(b_count==K*N);
    assign aux_loaded=(aux_count==AUX_WORDS);
    assign s_axis_a_tready=ap_resetn && !busy && !a_loaded;
    assign s_axis_b_tready=ap_resetn && !busy && ((!b_loaded) || (aux_loading && !aux_loaded));
    assign m_axis_tvalid=ap_resetn && (consumed<produced);
    assign m_axis_tdata=result_mem[consumed < M*BEATS ? consumed : 0];
    // One DMA transfer spans all M rows; assert TLAST only on the final beat.
    assign m_axis_tlast=m_axis_tvalid && (consumed==M*BEATS-1);

    // The DMA order remains B[row][column], with column = tile*4 + lane.
    // Only pointer/control registers reset; resetting the data would prevent
    // BRAM inference. No bank is read until all K*768 inputs have arrived.
    genvar bank_row, bank_lane;
    generate for(bank_row=0;bank_row<K;bank_row=bank_row+1) begin: weight_rows
        for(bank_lane=0;bank_lane<4;bank_lane=bank_lane+1) begin: weight_lanes
            (* ram_style="block" *) reg [15:0] weights [0:BEATS-1];
            (* ram_style="block" *) reg [15:0] up_weights [0:BEATS-1];
            always @(posedge ap_clk) begin
                if(ap_resetn && s_axis_b_tvalid && s_axis_b_tready &&
                   !b_loaded && b_write_row==bank_row && b_write_lane==bank_lane)
                    weights[b_write_tile] <= s_axis_b_tdata;
                if(ap_resetn && s_axis_b_tvalid && s_axis_b_tready && aux_loading &&
                   aux_count>=3*N && aux_count<AUX_WORDS &&
                   up_write_row==bank_row && up_write_lane==bank_lane)
                    up_weights[up_write_tile] <= s_axis_b_tdata;
                if(ap_resetn && state==LOAD_TILE)
                    w_tile[(bank_row*4+bank_lane)*16+:16] <= proj_up ? up_weights[tile_idx[BW-1:0]] : weights[tile_idx[BW-1:0]];
            end
        end
    end endgenerate

    always @(posedge ap_clk) begin
        if(ap_resetn && s_axis_b_tvalid && s_axis_b_tready && aux_loading) begin
            if(aux_count<N) gamma_mem[aux_count] <= s_axis_b_tdata;
            else if(aux_count<2*N) beta_mem[aux_count-N] <= s_axis_b_tdata;
            else if(aux_count<3*N) mask_mem[aux_count-2*N] <= s_axis_b_tdata;
        end
    end

    bf16_pe_array #(.ROWS(K),.COLS(4)) u_bf16_pe_array (
        .clk(ap_clk),.rst_n(ap_resetn),.set_w(pe_set_w),
        .valid_in(pe_input_valid),.x_packed(x_tile),.w_packed(w_tile),
        .psum_in(128'b0),.x_out(),.psum_out(mm_fp32),.valid_out(pe_valid)
    );
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1) begin: convert
        fp32_to_bf16_rne u_mm_round(mm_fp32[lane*32+:32],mm_bf16[lane*16+:16]);
    end endgenerate

    wire snake_resetn=ap_resetn && (state==ARM_SNAKE || state==FEED_SNAKE || state==WAIT_SNAKE);
    wire stage_start=snake_resetn;
    wire snake_input_valid=(state==FEED_SNAKE);
    wire [127:0] fifo1_din,fifo1_dout,fifo2_din,fifo2_dout,snake_result;
    wire fifo1_wr,fifo1_rd,fifo2_wr,fifo2_rd,fifo1_fault,fifo2_fault,snake_valid;
    wire [63:0] result_bf16;
    wire [63:0] snake_feed_a,snake_feed_b;
    genvar mask_lane;
    generate for(mask_lane=0;mask_lane<4;mask_lane=mask_lane+1) begin: mask_lanes
        assign snake_feed_a[mask_lane*16+:16] =
            (op_reg==10 && mask_mem[safe_feed_idx*4+mask_lane]==16'h0000) ? 16'hff80 :
            ((op_reg==11 && snake_phase) ? silu_row_mem[safe_feed_idx][mask_lane*16+:16] :
                                            row_mem[safe_feed_idx][mask_lane*16+:16]);
        assign snake_feed_b[mask_lane*16+:16] = up_row_mem[safe_feed_idx][mask_lane*16+:16];
    end endgenerate
    GLUT_SNAKE_array u_nonlinear_acc (
        .clk(ap_clk),.rst_n(snake_resetn),.stage_start(stage_start),.configs(snake_op),
        .input_atvalid(snake_input_valid),.input_atdata(snake_feed_a),
        .input_btvalid(snake_input_valid && op_reg==11 && snake_phase),.input_btdata(snake_feed_b),
        .fifo1_din(fifo1_din),.fifo1_wr_en(fifo1_wr),.fifo1_dout(fifo1_dout),.fifo1_rd_en(fifo1_rd),
        .fifo2_din(fifo2_din),.fifo2_wr_en(fifo2_wr),.fifo2_dout(fifo2_dout),.fifo2_rd_en(fifo2_rd),
        .result_tvalid(snake_valid),.result_tdata(snake_result)
    );
    snake_frame_fifo u_fifo1(ap_clk,snake_resetn,fifo1_wr,fifo1_rd,fifo1_din,fifo1_dout,fifo1_fault);
    snake_frame_fifo u_fifo2(ap_clk,snake_resetn,fifo2_wr,fifo2_rd,fifo2_din,fifo2_dout,fifo2_fault);
    generate for(lane=0;lane<4;lane=lane+1) begin: result_convert
        fp32_to_bf16_rne u_round(snake_result[lane*32+:32],result_bf16[lane*16+:16]);
    end endgenerate

    wire [3:0] affine_mul_valid, affine_add_valid;
    wire [127:0] affine_mul_data, affine_add_data;
    wire [63:0] affine_output_bf16;
    genvar affine_lane;
    generate for(affine_lane=0;affine_lane<4;affine_lane=affine_lane+1) begin: affine_lanes
        floating_mul u_affine_mul (
            .aclk(ap_clk),.s_axis_a_tvalid(snake_valid),.s_axis_a_tdata(snake_result[affine_lane*32+:32]),
            .s_axis_b_tvalid(snake_valid),.s_axis_b_tdata({gamma_mem[safe_recv_idx*4+affine_lane],16'b0}),
            .m_axis_result_tvalid(affine_mul_valid[affine_lane]),.m_axis_result_tdata(affine_mul_data[affine_lane*32+:32]));
        floating_add u_affine_add (
            .aclk(ap_clk),.s_axis_a_tvalid(affine_mul_valid[affine_lane]),.s_axis_a_tdata(affine_mul_data[affine_lane*32+:32]),
            .s_axis_b_tvalid(affine_mul_valid[affine_lane]),.s_axis_b_tdata({beta_mem[safe_mul_idx*4+affine_lane],16'b0}),
            .m_axis_result_tvalid(affine_add_valid[affine_lane]),.m_axis_result_tdata(affine_add_data[affine_lane*32+:32]));
        fp32_to_bf16_rne u_affine_round(affine_add_data[affine_lane*32+:32],affine_output_bf16[affine_lane*16+:16]);
    end endgenerate
    wire affine_output_valid=&affine_add_valid;
    always @(posedge ap_clk) begin
        if(!ap_resetn) affine_mul_count<=0;
        else if(state==WAIT_MM && mm_tvalid && tile_idx==BEATS-1) affine_mul_count<=0;
        else if(&affine_mul_valid) affine_mul_count<=affine_mul_count+1;
    end

    integer r,c;
    always @(posedge ap_clk) begin
        if (!ap_resetn) begin
            state<=IDLE; op_reg<=0; busy<=0; done<=0; error<=0;
            a_count<=0; b_count<=0; aux_count<=0; aux_loading<=0; proj_up<=0; snake_phase<=0;
            row_idx<=0; tile_idx<=0;
            feed_idx<=0; recv_count<=0; produced<=0; consumed<=0;
            timer<=0; x_tile<=0; affine_count_row<=0;
            b_write_row<=0; b_write_tile<=0; b_write_lane<=0;
            up_write_row<=0; up_write_tile<=0; up_write_lane<=0;
        end else begin
            done<=0;
            if (s_axis_a_tvalid && s_axis_a_tready) begin
                a_mem[a_count]<=s_axis_a_tdata; a_count<=a_count+1;
            end
            if (s_axis_b_tvalid && s_axis_b_tready) begin
                if(!b_loaded) begin
                    b_count<=b_count+1;
                    if(b_write_lane==3) begin
                        b_write_lane<=0;
                        if(b_write_tile==BEATS-1) begin
                            b_write_tile<=0;
                            b_write_row<=b_write_row+1'b1;
                        end else b_write_tile<=b_write_tile+1'b1;
                    end else b_write_lane<=b_write_lane+1'b1;
                end else if(aux_loading) begin
                    aux_count<=aux_count+1;
                    if(aux_count==AUX_WORDS-1) aux_loading<=0;
                    if(aux_count>=3*N) begin
                        if(up_write_lane==3) begin
                            up_write_lane<=0;
                            if(up_write_tile==BEATS-1) begin
                                up_write_tile<=0; up_write_row<=up_write_row+1'b1;
                            end else up_write_tile<=up_write_tile+1'b1;
                        end else up_write_lane<=up_write_lane+1'b1;
                    end
                end
            end
            if(aux_load && b_loaded && !busy && !aux_loaded) begin
                aux_loading<=1; aux_count<=0; up_write_row<=0; up_write_tile<=0; up_write_lane<=0;
            end
            if (m_axis_tvalid && m_axis_tready) consumed<=consumed+1;
            if (snake_resetn && (fifo1_fault || fifo2_fault)) error<=1;
            if (snake_resetn && snake_valid) begin
                if (recv_count<BEATS) begin
                    if(op_reg==11 && !snake_phase) silu_row_mem[recv_count]<=result_bf16;
                    else if(op_reg!=8 && op_reg!=9) begin
                        result_mem[produced]<=result_bf16;
                        produced<=produced+1;
                    end
                    recv_count<=recv_count+1;
                end else error<=1;
            end
            if(affine_output_valid && op_reg>=8 && op_reg<=9) begin
                result_mem[produced]<=affine_output_bf16;
                produced<=produced+1;
                affine_count_row<=affine_count_row+1;
            end
            case(state)
                IDLE: if(start) begin
                    if (!a_loaded || !b_loaded || !(op<=4 || op==7 || (op>=8 && op<=11)) ||
                        ((op>=8 && op<=11) && !aux_loaded)) error<=1;
                    else begin
                        busy<=1; error<=0; op_reg<=op; row_idx<=0; tile_idx<=0;
                        produced<=0; consumed<=0; proj_up<=0; snake_phase<=0;
                        affine_count_row<=0; state<=LOAD_TILE;
                    end
                end
                LOAD_TILE: begin
                    for(r=0;r<K;r=r+1) begin
                        x_tile[r*16+:16]<=a_mem[row_idx*K+r];
                    end
                    state<=ISSUE;
                end
                ISSUE: begin state<=WAIT_MM; timer<=0; end
                WAIT_MM: begin
                    timer<=timer+1;
                    if(mm_tvalid) begin
                        if(proj_up) up_row_mem[tile_idx]<=mm_bf16;
                        else row_mem[tile_idx]<=mm_bf16;
                        if(op_reg==7) begin
                            result_mem[produced]<=mm_bf16; produced<=produced+1;
                        end
                        if(tile_idx==BEATS-1) begin
                            timer<=0; feed_idx<=0; recv_count<=0; affine_count_row<=0;
                            if(op_reg==11 && !proj_up) begin
                                proj_up<=1; tile_idx<=0; state<=LOAD_TILE;
                            end else if(op_reg==7) begin proj_up<=0; state<=NEXT_ROW; end
                            else begin proj_up<=0; snake_phase<=0; state<=RESET_SNAKE; end
                        end else begin tile_idx<=tile_idx+1; state<=LOAD_TILE; end
                    end else if(timer> K*17+128) begin error<=1; busy<=0; state<=IDLE; end
                end
                // Drain non-resettable floating IP pipelines before enabling
                // the next frame. Reset local Snake control and FIFO pointers.
                RESET_SNAKE: if(timer==255) begin timer<=0; state<=ARM_SNAKE; end
                             else timer<=timer+1;
                ARM_SNAKE: if(timer==15) begin timer<=0; state<=FEED_SNAKE; end
                           else timer<=timer+1;
                FEED_SNAKE: if(feed_idx==BEATS-1) begin state<=WAIT_SNAKE; timer<=0; end
                            else feed_idx<=feed_idx+1;
                WAIT_SNAKE: begin
                    timer<=timer+1;
                    if(recv_count==BEATS &&
                       (!(op_reg==8 || op_reg==9) || affine_count_row==BEATS)) begin
                        if(op_reg==11 && !snake_phase) begin
                            snake_phase<=1; timer<=0; feed_idx<=0; recv_count<=0;
                            state<=RESET_SNAKE;
                        end else begin snake_phase<=0; state<=NEXT_ROW; end
                    end
                    else if(timer==4095) begin error<=1; busy<=0; state<=IDLE; end
                end
                NEXT_ROW: if(row_idx==M-1) state<=DRAIN;
                          else begin row_idx<=row_idx+1; tile_idx<=0; proj_up<=0; snake_phase<=0; state<=LOAD_TILE; end
                DRAIN: if(consumed==M*BEATS) begin done<=1; busy<=0; state<=IDLE; end
                default: begin error<=1; busy<=0; state<=IDLE; end
            endcase
        end
    end
endmodule
