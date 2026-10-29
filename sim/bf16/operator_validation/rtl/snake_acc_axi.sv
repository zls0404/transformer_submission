`timescale 1ns/1ps
// Extended wrapper. 0x00 starts an op; 0x04 is status; writing bit0 to
// 0x08 opens one auxiliary-frame load on s_axis_b.
module snake_acc_axi #(parameter integer M=4, K=4) (
 input wire aclk, aresetn,
 input wire [5:0] s_axi_awaddr, input wire [2:0] s_axi_awprot,
 input wire s_axi_awvalid, output wire s_axi_awready,
 input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb, input wire s_axi_wvalid, output wire s_axi_wready,
 output wire [1:0] s_axi_bresp, output wire s_axi_bvalid, input wire s_axi_bready,
 input wire [5:0] s_axi_araddr, input wire [2:0] s_axi_arprot,
 input wire s_axi_arvalid, output wire s_axi_arready,
 output wire [31:0] s_axi_rdata, output wire [1:0] s_axi_rresp, output wire s_axi_rvalid, input wire s_axi_rready,
 input wire [15:0] s_axis_a_tdata, input wire s_axis_a_tvalid, output wire s_axis_a_tready,
 input wire [15:0] s_axis_b_tdata, input wire s_axis_b_tvalid, output wire s_axis_b_tready,
 output wire [63:0] m_axis_tdata, output wire m_axis_tvalid, output wire m_axis_tlast,
 input wire m_axis_tready, output wire irq
);
 reg aw_hold,w_hold,b_hold,ar_hold,r_hold,start_reg;
 reg [5:0] awaddr_reg,araddr_reg;
 reg [31:0] wdata_reg,rdata_reg;
 reg [3:0] wstrb_reg,op_reg;
 wire busy,done,error,a_loaded,b_loaded,aux_loaded;
 reg aux_load_reg;
 assign s_axi_awready=!aw_hold&&!b_hold; assign s_axi_wready=!w_hold&&!b_hold;
 assign s_axi_bvalid=b_hold; assign s_axi_bresp=0;
 assign s_axi_arready=!ar_hold&&!r_hold; assign s_axi_rvalid=r_hold;
 assign s_axi_rresp=0; assign s_axi_rdata=rdata_reg; assign irq=done;
 always @(posedge aclk) begin
  if(!aresetn) begin aw_hold<=0;w_hold<=0;b_hold<=0;ar_hold<=0;r_hold<=0;start_reg<=0;aux_load_reg<=0;op_reg<=0;awaddr_reg<=0;araddr_reg<=0;wdata_reg<=0;wstrb_reg<=0;rdata_reg<=0; end
  else begin
   start_reg<=0;
   aux_load_reg<=0;
   if(s_axi_awvalid&&s_axi_awready) begin aw_hold<=1;awaddr_reg<=s_axi_awaddr;end
   if(s_axi_wvalid&&s_axi_wready) begin w_hold<=1;wdata_reg<=s_axi_wdata;wstrb_reg<=s_axi_wstrb;end
   if(aw_hold&&w_hold&&!b_hold) begin
    if(wstrb_reg[0] && awaddr_reg[5:2]==0) begin start_reg<=wdata_reg[0];op_reg<=wdata_reg[7:4];end
    if(wstrb_reg[0] && awaddr_reg[5:2]==2 && wdata_reg[0]) aux_load_reg<=1;
    aw_hold<=0;w_hold<=0;b_hold<=1;
   end
   if(b_hold&&s_axi_bready)b_hold<=0;
   if(s_axi_arvalid&&s_axi_arready) begin
    ar_hold<=1;araddr_reg<=s_axi_araddr;
    case(s_axi_araddr[5:2]) 0:rdata_reg<=0;1:rdata_reg<={26'b0,aux_loaded,b_loaded,a_loaded,error,done,busy};default:rdata_reg<=32'h534E414B;endcase
   end
   if(ar_hold)r_hold<=1;
   if(r_hold&&s_axi_rready)begin r_hold<=0;ar_hold<=0;end
  end
 end
 snake_acc_top #(.M(M),.K(K)) u_core(
  .ap_clk(aclk),.ap_resetn(aresetn),.start(start_reg),.op(op_reg),
  .s_axis_a_tdata(s_axis_a_tdata),.s_axis_a_tvalid(s_axis_a_tvalid),.s_axis_a_tready(s_axis_a_tready),
  .s_axis_b_tdata(s_axis_b_tdata),.s_axis_b_tvalid(s_axis_b_tvalid),.s_axis_b_tready(s_axis_b_tready),
  .aux_load(aux_load_reg),.a_loaded(a_loaded),.b_loaded(b_loaded),.aux_loaded(aux_loaded),.m_axis_tdata(m_axis_tdata),.m_axis_tvalid(m_axis_tvalid),.m_axis_tlast(m_axis_tlast),.m_axis_tready(m_axis_tready),
  .busy(busy),.done(done),.error(error),.mm_tvalid(),.mm_fp32(),.mm_bf16());
endmodule
