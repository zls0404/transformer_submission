`timescale 1ns/1ps
module tb_gelu_backpressure;
 reg clk=0;always #5 clk=~clk;reg rst=0;
 reg [31:0] din=0;reg vin=0,lin=0,ready=1;wire rin,vout,lout;wire[31:0] dout;wire[3:0] keep;
 EightGelus dut(.clk(clk),.rst_n(rst),.in_data(din),.in_valid(vin),.in_ready(rin),.in_last(lin),.in_keep(4'hf),.out_data(dout),.out_valid(vout),.out_ready(ready),.out_last(lout),.out_keep(keep),.scale(4'd7));
 integer cycle=0,accepted=0,received=0,hold_errors=0,i,fd;string root;reg held=0;reg[36:0] previous;
 always @(posedge clk)begin
  cycle=cycle+1;
  if(rst)begin
   if(vin&&rin)accepted=accepted+1;
   if(vout&&ready)received=received+1;
   if(held && {vout,lout,keep,dout}!=={1'b1,previous})hold_errors=hold_errors+1;
   held=vout&&!ready;previous={lout,keep,dout};
  end else held=0;
 end
 initial begin
  if(!$value$plusargs("ROOT=%s",root))root="../..";
  repeat(20)@(negedge clk);rst=1;
  for(i=0;i<32;i=i+1)begin
   @(negedge clk);vin=1;din={4{8'(i)}};lin=(i==31);
   while(!rin)@(negedge clk);
  end
  @(negedge clk);vin=0;lin=0;repeat(30)@(negedge clk);
  fd=$fopen({root,"/raw/gelu_backpressure.csv"},"w");
  $fdisplay(fd,"accepted,received,hold_errors");$fdisplay(fd,"%0d,%0d,%0d",accepted,received,hold_errors);$fclose(fd);$finish;
 end
 initial begin
  wait(rst);repeat(12)@(negedge clk);ready=0;repeat(8)@(negedge clk);ready=1;
 end
 initial begin #100000;$fatal(1,"Timeout");end
endmodule
