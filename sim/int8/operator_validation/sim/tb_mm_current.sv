`timescale 1ns/1ps
module tb_mm_current;
 reg clk=0;always #5 clk=~clk;reg rst=0;
 reg[9:0] shift=0,rows=0;reg[4:0] kb=0,nb=0;
 reg fv=0,fl=0,wv=0,wl=0;reg[127:0] fdata=0,wdata=0;
 wire fr,wr,ov,ol;wire[127:0] od;reg ready=1;
 MM_ultra #(.OUT_MEM_WIDTH(21),.F_length_width(10)) dut(.clk(clk),.rst_n(rst),.shift_in(shift),.F_length_in(rows),.F_width_block_num_in(kb),.W_width_block_num_in(nb),.in_F_valid(fv),.in_F_last(fl),.in_F_ready(fr),.in_F_data(fdata),.in_W_valid(wv),.in_W_last(wl),.in_W_ready(wr),.in_W_data(wdata),.out_data_valid(ov),.out_data_ready(ready),.out_data_last(ol),.out_data(od));
 integer fd,raw,summ,rc,total,cid,m,k,n,sh,probe,i,cycle=0,start,first,finalc,recv,lasts,unknown,hold_errors,drain;
 reg active=0,held=0;reg[128:0] prev;reg[127:0] fs[0:4095],ws[0:4095];string root,data_dir;
 always @(negedge clk)begin if(active && probe!=0)ready=(cycle%13<9);else ready=1;end
 always @(posedge clk)begin
  cycle=cycle+1;
  if(active && rst)begin
   if(held && {ov,ol,od}!=={1'b1,prev})hold_errors=hold_errors+1;
   held=ov&&!ready;prev={ol,od};
   if(ov&&ready)begin
    if(recv==0)first=cycle;finalc=cycle;
    if((^od)===1'bx)unknown=unknown+1;
    $fdisplay(raw,"%0d,%0d,%032h,%b,%0d",cid,recv,od,ol,cycle);
    recv=recv+1;if(ol)lasts=lasts+1;
   end
  end else held=0;
 end
 initial begin
  if(!$value$plusargs("ROOT=%s",root))root="../..";
    if(!$value$plusargs("DATA_DIR=%s",data_dir))data_dir={root,"/../../../data/int8"};
  fd=$fopen({data_dir,"/mm_vectors.txt"},"r");raw=$fopen({root,"/raw/mm_samples.csv"},"w");summ=$fopen({root,"/raw/mm_summary.csv"},"w");
  if(!fd||!raw||!summ)$fatal(1,"File open failed");
  $fdisplay(raw,"case_id,beat,data_hex,last,cycle");$fdisplay(summ,"case_id,m,k,n,probe,output_beats,last_count,unknowns,hold_errors,timeout,first_cycles,completion_cycles");
  rc=$fscanf(fd,"%d",total);
  repeat(20)@(negedge clk);
  repeat(total)begin
   rc=$fscanf(fd,"%d %d %d %d %d %d",cid,m,k,n,sh,probe);if(rc!=6)$fatal(1,"Bad header");
   for(i=0;i<m*k/16;i=i+1)rc=$fscanf(fd,"%h",fs[i]);
   for(i=0;i<k*n/16;i=i+1)rc=$fscanf(fd,"%h",ws[i]);
   @(negedge clk);active=0;rst=0;fv=0;wv=0;fl=0;wl=0;rows=m;kb=k/16;nb=n/16;shift=sh;
   repeat(30)@(negedge clk);rst=1;repeat(20)@(negedge clk);
   recv=0;lasts=0;unknown=0;hold_errors=0;first=-1;finalc=-1;active=1;start=-1;
   for(i=0;i<k*n/16;i=i+1)begin
    @(negedge clk);wv=1;wdata=ws[i];wl=(i==k*n/16-1);if(i==0)start=cycle+1;
    @(posedge clk);while(!wr)@(posedge clk);
    if(probe && i%5==0)begin @(negedge clk);wv=0;repeat(2)@(negedge clk);end
   end
   @(negedge clk);wv=0;wl=0;
   for(i=0;i<m*k/16;i=i+1)begin
    @(negedge clk);fv=1;fdata=fs[i];fl=(i==m*k/16-1);
    @(posedge clk);while(!fr)@(posedge clk);
    if(probe && i%5==0)begin @(negedge clk);fv=0;repeat(2)@(negedge clk);end
   end
   @(negedge clk);fv=0;fl=0;drain=0;
   while(recv<m*n/16 && drain<20000)begin @(negedge clk);drain=drain+1;end
   repeat(50)@(negedge clk);active=0;
   $fdisplay(summ,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",cid,m,k,n,probe,recv,lasts,unknown,hold_errors,drain>=20000,first-start,finalc-start);
   $display("MM case %0d outputs=%0d expected=%0d",cid,recv,m*n/16);
  end
  $fclose(raw);$fclose(summ);$finish;
 end
 initial begin #20000000;$fatal(1,"Timeout");end
endmodule


