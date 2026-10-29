`timescale 1ns/1ps
// Both original modules, same 100 predeclared cases, default project scales 6/7.
// Python generates quantized reference codes before any RTL simulation.
module tb_softmax_current;
  reg clk=0; always #5 clk=~clk;
  reg rst_n=0;
  reg [9:0] n_in=32;
  wire [10:0] n2=2*n_in;
  wire [11:0] n3=3*n_in;
  reg signed [7:0] in_code=0;
  reg s_valid=0,p_valid=0,p_last=0;
  wire p_ready; wire [7:0] b_out; wire b_valid,b_last;
  Softmax dut_baseline(.clk(clk),.rst_n(rst_n),.length_input(n_in),.lengthX2(n2),.lengthX3(n3),.scale_in(5'sd6),.scale_out(4'd7),.data_in(in_code),.valid_in(s_valid),.data_out(b_out),.valid_out(b_valid),.out_last(b_last));
  wire [7:0] s_out,p_out;
  wire s_out_valid,s_last,p_out_valid,p_out_last;
  Softmax_iscas2023 dut_serial(.clk(clk),.rst_n(rst_n),.length_input(n_in),.lengthX2(n2),.lengthX3(n3),
    .scale_in(5'sd6),.scale_out(4'd7),.data_in(in_code),.valid_in(s_valid),
    .data_out(s_out),.valid_out(s_out_valid),.out_last(s_last));
  Softmax_iscas2023_parallel #(.LANES(4)) dut_parallel(.clk(clk),.rst_n(rst_n),.length_input(n_in),
    .scale_in_input(5'sd6),.scale_out_input(4'd7),.top_data_in(in_code),.top_valid_in(p_valid),
    .top_ready_in(p_ready),.top_last_in(p_last),.top_data_out(p_out),.top_valid_out(p_out_valid),.top_last_out(p_out_last));
  integer q[0:1022],reference[0:1022],base_ref[0:1022];
  integer recv[0:2],mismatch[0:2],protocol[0:2],unknown[0:2],lasts[0:2];
  integer first[0:2],final_cycle[0:2];
  integer fd,detail_fd,summary_fd,status_fd,rc,total,case_id,n,cycle=0,start_cycle;
  integer i,pass_idx,mod_idx,drain,idx,value,failed_serial=0,failed_parallel=0;
  reg active=0;
  string root,data_dir,vector_file,result_dir;
  always @(posedge clk) begin
    cycle=cycle+1;
    #1;
    if(active && rst_n) begin
      observe(0,s_out,s_out_valid,s_last);
      observe(1,p_out,p_out_valid,p_out_last);observe(2,b_out,b_valid,b_last);
    end
  end
  task automatic observe(input integer m,input [7:0] data,input valid,input last);
    integer index;
    begin
      if(valid!==1'b0 && valid!==1'b1) unknown[m]=unknown[m]+1;
      if(last===1'b1 && valid!==1'b1) protocol[m]=protocol[m]+1;
      if(valid===1'b1) begin
        index=recv[m];recv[m]=recv[m]+1;
        if(first[m]<0)first[m]=cycle;
        final_cycle[m]=cycle;
        if(last===1'b1)lasts[m]=lasts[m]+1;
        if(index>=n)protocol[m]=protocol[m]+1;
        else begin
          if((^data)===1'bx)unknown[m]=unknown[m]+1;
          if(data!==(m==2?base_ref[index][7:0]:reference[index][7:0]))mismatch[m]=mismatch[m]+1;
          if(last!==(index==n-1))protocol[m]=protocol[m]+1;
          $fdisplay(detail_fd,"%0d,%s,%0d,%0d,%0d,%b",case_id,m==0?"serial":(m==1?"parallel":"baseline"),index,data,cycle,last);
        end
      end
    end
  endtask
  initial begin
    if(!$value$plusargs("ROOT=%s",root))root="../..";
    if(!$value$plusargs("DATA_DIR=%s",data_dir))data_dir={root,"/../../../data/int8"};
    vector_file={data_dir,"/softmax_vectors.txt"};result_dir={root,"/raw"};
    fd=$fopen(vector_file,"r");
    detail_fd=$fopen({result_dir,"/rtl_samples.csv"},"w");
    summary_fd=$fopen({result_dir,"/rtl_summary.csv"},"w");
    status_fd=$fopen({result_dir,"/simulation_status.txt"},"w");
    if(!fd || !detail_fd || !summary_fd || !status_fd)$fatal(1,"Cannot open vectors/results: %s",root);
    $fdisplay(detail_fd,"case_id,module,index,actual_code,output_cycle,last");
    $fdisplay(summary_fd,"case_id,module,n,output_count,code_mismatches,protocol_errors,unknowns,last_count,first_cycles,completion_cycles,first_ns,completion_ns");
    rc=$fscanf(fd,"%d",total);if(rc!=1)$fatal(1,"Bad vector header");
    repeat(16)@(negedge clk);
    for(i=0;i<total;i=i+1) begin
      rc=$fscanf(fd,"%d %d",case_id,n);if(rc!=2 || n<1 || n>1023)$fatal(1,"Invalid case");
      for(idx=0;idx<n;idx=idx+1)begin rc=$fscanf(fd,"%d %d %d",q[idx],reference[idx],base_ref[idx]);if(rc!=3)$fatal(1,"Truncated vectors");end
      @(negedge clk);active=0;rst_n=0;s_valid=0;p_valid=0;p_last=0;n_in=n;
      repeat(16)@(negedge clk);rst_n=1;
      repeat(3)@(negedge clk);
      for(mod_idx=0;mod_idx<3;mod_idx=mod_idx+1)begin
        recv[mod_idx]=0;mismatch[mod_idx]=0;protocol[mod_idx]=0;unknown[mod_idx]=0;lasts[mod_idx]=0;
        first[mod_idx]=-1;final_cycle[mod_idx]=-1;
      end
      active=1;start_cycle=-1;
      for(pass_idx=0;pass_idx<3;pass_idx=pass_idx+1)begin
        for(idx=0;idx<n;idx=idx+1)begin
          @(negedge clk);
          if(start_cycle<0)start_cycle=cycle+1;
          in_code=q[idx];s_valid=1;p_valid=(pass_idx==0);p_last=(pass_idx==0 && idx==n-1);
          if(pass_idx==0 && p_ready!==1'b1)$fatal(1,"Parallel input not ready");
        end
      end
      @(negedge clk);s_valid=0;p_valid=0;p_last=0;in_code=0;
      drain=0;
      while((recv[0]<n || recv[1]<n) && drain<4*n+50)begin @(negedge clk);drain=drain+1;end
      repeat(20)@(negedge clk);active=0;
      for(mod_idx=0;mod_idx<3;mod_idx=mod_idx+1)begin
        if(recv[mod_idx]!=n || lasts[mod_idx]!=1)protocol[mod_idx]=protocol[mod_idx]+1;
        if(mismatch[mod_idx]+protocol[mod_idx]+unknown[mod_idx]>0)begin
          if(mod_idx==0)failed_serial=failed_serial+1;else if(mod_idx==1)failed_parallel=failed_parallel+1;
        end
        $fdisplay(summary_fd,"%0d,%s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",case_id,
          mod_idx==0?"serial":(mod_idx==1?"parallel":"baseline"),n,recv[mod_idx],mismatch[mod_idx],protocol[mod_idx],unknown[mod_idx],lasts[mod_idx],
          first[mod_idx]-start_cycle,final_cycle[mod_idx]-start_cycle,10*(first[mod_idx]-start_cycle),10*(final_cycle[mod_idx]-start_cycle));
      end
      $display("CASE %0d N=%0d serial_diff=%0d parallel_diff=%0d",case_id,n,mismatch[0],mismatch[1]);
    end
    $fdisplay(status_fd,"CASES=%0d SERIAL_DIFFERENT_OR_PROTOCOL=%0d PARALLEL_DIFFERENT_OR_PROTOCOL=%0d",total,failed_serial,failed_parallel);
    $fdisplay(status_fd,"Clock=10ns; input scale=6; output scale=7; original RTL unchanged.");
    $display("VALIDATION COMPLETE cases=%0d serial_different=%0d parallel_different=%0d",total,failed_serial,failed_parallel);
    $fclose(fd);$fclose(detail_fd);$fclose(summary_fd);$fclose(status_fd);$finish;
  end
  initial begin #20000000;$fatal(1,"Global timeout");end
endmodule
