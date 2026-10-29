`timescale 1ns/1ps
module tb_gelu_current;
 reg clk=0;always #5 clk=~clk;
 reg [3:0] scale=7;reg signed[7:0] x=0;wire signed[7:0] y;
 gelu dut(.clk(clk),.in_scale(scale),.x(x),.y_reg1(y));
 reg [7:0] vp=0;reg drive=0;integer ip[0:7];integer idx=0,drive_idx=0;
 integer fd,raw,sum,rc,total,cid,sc,n,i,j,q[0:255],refq[0:255],cycle=0,start,first,last,recv,bad,unknown;
 string root,data_dir;
 always @(posedge clk)begin
  cycle=cycle+1;vp<={vp[6:0],drive};ip[0]<=drive_idx;for(j=1;j<8;j=j+1)ip[j]<=ip[j-1];
  #1;if(vp[7])begin
   if(recv==0)first=cycle;last=cycle;recv=recv+1;
   if((^y)===1'bx)unknown=unknown+1;
   if(y!==refq[ip[7]][7:0])bad=bad+1;
   $fdisplay(raw,"%0d,%0d,%0d,%0d,%0d",cid,sc,ip[7],y,cycle);
  end
 end
 initial begin
  if(!$value$plusargs("ROOT=%s",root))root="../..";
    if(!$value$plusargs("DATA_DIR=%s",data_dir))data_dir={root,"/../../../data/int8"};
  fd=$fopen({data_dir,"/gelu_vectors.txt"},"r");raw=$fopen({root,"/raw/gelu_samples.csv"},"w");sum=$fopen({root,"/raw/gelu_summary.csv"},"w");
  if(!fd||!raw||!sum)$fatal(1,"File open failed");
  $fdisplay(raw,"case_id,scale,index,actual_code,cycle");$fdisplay(sum,"case_id,scale,output_count,code_mismatches,unknowns,first_cycles,completion_cycles");
  rc=$fscanf(fd,"%d",total);
  for(i=0;i<total;i=i+1)begin
   rc=$fscanf(fd,"%d %d %d",cid,sc,n);if(rc!=3)$fatal(1,"Bad vectors");
   for(idx=0;idx<n;idx=idx+1)rc=$fscanf(fd,"%d %d",q[idx],refq[idx]);
   scale=sc;drive=0;repeat(20)@(negedge clk);recv=0;bad=0;unknown=0;first=-1;last=-1;
   for(idx=0;idx<n;idx=idx+1)begin @(negedge clk);x=q[idx];drive_idx=idx;drive=1;if(idx==0)start=cycle+1;end
   @(negedge clk);drive=0;repeat(16)@(negedge clk);
   $fdisplay(sum,"%0d,%0d,%0d,%0d,%0d,%0d,%0d",cid,sc,recv,bad,unknown,first-start,last-start);
   $display("GELU scale=%0d count=%0d bad=%0d",sc,recv,bad);
  end
  $fclose(raw);$fclose(sum);$finish;
 end
 initial begin #2000000;$fatal(1,"Timeout");end
endmodule

