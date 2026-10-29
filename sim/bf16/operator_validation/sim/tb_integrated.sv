`timescale 1ns/1ps
// UNMODIFIED production streaming core. ROWS=1 isolates a row; ROWS=4 checks production framing.
// K=4,N=768 in both configurations. PS/DMA excluded.
module tb_integrated #(parameter integer OP_FILTER=-1, ROWS=1);
 localparam M=ROWS,K=4,N=768,BEATS=192,CASES=6,AUX=(K+3)*N;
 reg clk=0,rst_n=0,start=0,aux_load=0,a_valid=0,b_valid=0,out_ready=1;
 always #5 clk=~clk;
 reg [15:0] a_data=0,b_data=0;reg [3:0] op=0;
 wire a_ready,b_ready,a_loaded,b_loaded,aux_loaded,busy,done,error,out_valid,out_last,mm_valid;
 wire [63:0] out_data,mm_bf16;wire [127:0] mm_fp32;
 snake_acc_top #(.M(M),.K(K)) dut(
 .ap_clk(clk),.ap_resetn(rst_n),.start(start),.op(op),.aux_load(aux_load),
 .s_axis_a_tdata(a_data),.s_axis_a_tvalid(a_valid),.s_axis_a_tready(a_ready),
 .s_axis_b_tdata(b_data),.s_axis_b_tvalid(b_valid),.s_axis_b_tready(b_ready),
 .a_loaded(a_loaded),.b_loaded(b_loaded),.aux_loaded(aux_loaded),
 .m_axis_tdata(out_data),.m_axis_tvalid(out_valid),.m_axis_tlast(out_last),.m_axis_tready(out_ready),
 .busy(busy),.done(done),.error(error),.mm_tvalid(mm_valid),.mm_fp32(mm_fp32),.mm_bf16(mm_bf16));
 reg [15:0] av[0:CASES*4*K-1],bv[0:CASES*K*N-1],auxv[0:CASES*AUX-1];
 integer selected_op,tc,cycle=0,outs,mmouts,first_a,last_load,first_start,first_out,last_out,done_cycle;
 integer tl_errors,stall_errors,unknowns,fault1,fault2,error_seen,waited,load_timeout,extra;
 integer fs,fm,fh,case_start,case_stop;reg capture=0,stalled=0;reg [63:0] held;reg held_last;
 string dir,data_dir;
 always @(negedge clk) begin
  if(capture && tc==4 && first_start>=0) out_ready=(cycle%11>=3);
  else out_ready=1;
 end
 always @(posedge clk) begin
  cycle=cycle+1;
  if(capture) begin
   if(a_valid&&a_ready&&first_a<0) first_a=cycle;
   if(error===1'b1)error_seen=1;
   if(dut.snake_resetn && dut.fifo1_fault)fault1=1;
   if(dut.snake_resetn && dut.fifo2_fault)fault2=1;
   if(done)done_cycle=cycle;
   if(stalled && (out_valid!==1'b1 || out_data!==held || out_last!==held_last))stall_errors=stall_errors+1;
   stalled=(out_valid===1'b1 && !out_ready);held=out_data;held_last=out_last;
   if(out_valid!==1'b0 && out_valid!==1'b1)unknowns=unknowns+1;
   if(mm_valid) begin
    for(integer l=0;l<4;l=l+1)$fwrite(fm,"%0d,%0d,%0d,%0d,%0d,%0d,%08h,%04h\n",selected_op,tc,dut.row_idx,dut.proj_up,dut.tile_idx*4+l,cycle,mm_fp32[l*32+:32],mm_bf16[l*16+:16]);
    mmouts=mmouts+1;
   end
   if(out_valid && out_ready) begin
    if(first_out<0)first_out=cycle;last_out=cycle;
    if(first_start<0)extra=extra+1;
    if(out_last!==(outs==M*BEATS-1))tl_errors=tl_errors+1;
    if($isunknown(out_data))unknowns=unknowns+1;
    for(integer l=0;l<4;l=l+1)$fwrite(fs,"%0d,%0d,%0d,%0d,%0d,%04h\n",selected_op,tc,outs,l,cycle,out_data[l*16+:16]);
    outs=outs+1;
   end
  end
 end
 task automatic send_a;
  for(integer j=0;j<M*K;j=j+1) begin
   @(negedge clk);a_valid=1;a_data=av[tc*4*K+j];waited=0;
   do begin @(posedge clk); waited=waited+1; end while(!a_ready&&waited<20000);
   if(waited>=20000)load_timeout=1;
  end
  @(negedge clk);a_valid=0;
 endtask
 task automatic send_b(input integer auxiliary);
  integer count,offset;
  begin
   count=auxiliary?AUX:K*N;offset=tc*count;
   for(integer j=0;j<count;j=j+1) begin
    @(negedge clk);
    if(tc==4 && j%17==8) begin b_valid=0;@(negedge clk);end
    b_valid=1;b_data=auxiliary?auxv[offset+j]:bv[offset+j];waited=0;
    do begin @(posedge clk);waited=waited+1;end while(!b_ready&&waited<20000);
    if(waited>=20000)load_timeout=1;
   end
   @(negedge clk);b_valid=0;
  end
 endtask
 initial begin
  selected_op=OP_FILTER;if(selected_op<0 && !$value$plusargs("OP=%d",selected_op))selected_op=7;
  op=selected_op;
  if(!$value$plusargs("CASE_START=%d",case_start))case_start=0;
  if(!$value$plusargs("CASE_STOP=%d",case_stop))case_stop=CASES;
  if(!$value$plusargs("DATA_DIR=%s",data_dir))data_dir="../../../../data/bf16/integrated";
  if(!$value$plusargs("OUT_DIR=%s",dir))dir="../results/integrated_manual";
  $readmemh({data_dir,"/a.hex"},av);$readmemh({data_dir,"/b.hex"},bv);$readmemh({data_dir,"/aux_data.hex"},auxv);
  fs=$fopen({dir,"/samples.csv"},"w");fm=$fopen({dir,"/mm_samples.csv"},"w");fh=$fopen({dir,"/summary.csv"},"w");
  if(!fs||!fm||!fh)$fatal(1,"Cannot open captures");
  $fwrite(fs,"op,case_id,beat,lane,cycle,bf16_hex\n");
  $fwrite(fm,"op,case_id,row,projection,index,cycle,fp32_hex,bf16_hex\n");
  $fwrite(fh,"op,case_id,out_beats,mm_beats,first_a,last_load,start,first_out,last_out,done,tl_errors,stall_errors,unknowns,fifo1,fifo2,error,timeout,load_timeout,premature\n");
  for(tc=case_start;tc<case_stop;tc=tc+1) begin
   capture=0;stalled=0;
   if(tc!=5) begin
    @(negedge clk);rst_n=0;a_valid=0;b_valid=0;start=0;aux_load=0;
    repeat(288)@(negedge clk);rst_n=1;repeat(16)@(negedge clk);
   end
   outs=0;mmouts=0;first_a=-1;last_load=-1;first_start=-1;first_out=-1;last_out=-1;done_cycle=-1;
   tl_errors=0;stall_errors=0;unknowns=0;fault1=0;fault2=0;error_seen=0;load_timeout=0;extra=0;capture=1;
   if(tc!=5) begin
    send_a();send_b(0);
    if(selected_op>=8)begin @(negedge clk);aux_load=1;@(negedge clk);aux_load=0;send_b(1);end
    last_load=cycle;
   end
   @(negedge clk);start=1;first_start=cycle+1;
   @(negedge clk);start=0;waited=0;
   while((done_cycle<0 || outs<M*BEATS) && waited<150000)begin @(negedge clk);waited=waited+1;end
   repeat(256)@(negedge clk);capture=0;
   $fwrite(fh,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",selected_op,tc,outs,mmouts,first_a,last_load,first_start,first_out,last_out,done_cycle,tl_errors,stall_errors,unknowns,fault1,fault2,error_seen,waited>=150000,load_timeout,extra);
   $fflush(fs);$fflush(fh);$fflush(fm);
   $display("INTEGRATED_CAPTURE op=%0d case=%0d beats=%0d TLAST=%0d stable=%0d faults=%0d/%0d error=%0d",selected_op,tc,outs,tl_errors,stall_errors,fault1,fault2,error_seen);
  end
  $fclose(fs);$fclose(fh);$fclose(fm);$display("INTEGRATED_COMPLETED op=%0d rows=%0d cases=%0d",selected_op,M,case_stop-case_start);$finish;
 end
 initial begin #15000000;$fatal(1,"Global timeout");end
endmodule

module tb_integrated_m4;tb_integrated #(.ROWS(4)) run();endmodule
