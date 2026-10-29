`timescale 1ns/1ps
// Diagnostic only: instantiate the ORIGINAL vendor accumulator simulation
// wrapper directly, independently of the Snake RTL and its FIFOs.
module tb_accumulator_startup;
    reg clk=0;
    always #5 clk=~clk;
    reg valid=0,last=0;
    reg [31:0] data=0;
    wire result_valid,result_last;
    wire [31:0] result;
    floating_acc ip(.aclk(clk),.s_axis_a_tvalid(valid),.s_axis_a_tlast(last),
        .s_axis_a_tdata(data),.m_axis_result_tvalid(result_valid),
        .m_axis_result_tlast(result_last),.m_axis_result_tdata(result));
    integer cycle=0,f,frame,b;
    always @(posedge clk) begin
        cycle=cycle+1;
        if (result_valid && result_last) begin
            $fwrite(f,"%0d,%08h\n",cycle,result);
            $display("ACC_FRAME_END cycle=%0d bits=%08h",cycle,result);
        end
    end
    initial begin
        f=$fopen("../results/accumulator_startup/frame_ends.csv","w");
        if (!f) $fatal(1,"Cannot open diagnostic capture");
        $fwrite(f,"cycle,fp32_hex\n");
        repeat(304) @(negedge clk);
        for(frame=0;frame<4;frame=frame+1) begin
            for(b=0;b<192;b=b+1) begin
                valid=1;data=(frame%2==0) ? 32'h00000000 : 32'h40800000;
                last=(b==191); // frame sums: 0, 768, 0, 768
                @(negedge clk);
            end
            valid=0;last=0;
            repeat(400) @(negedge clk);
        end
        $fclose(f);$display("ACC_DIAGNOSTIC_COMPLETED");$finish;
    end
endmodule
