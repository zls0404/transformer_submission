`timescale 1ns/1ps
// Common self-checking capture harness. Five small top files select each op.
// Full numerical checks run independently in scripts/analyze_results.py.
module tb_operator_validation #(parameter integer OP_FILTER=-1);
    localparam integer N=768, BEATS=192, MAX_CASES=64;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, in_valid=0;
    reg [63:0] in_bf16=0;
    reg [3:0] op=0;
    wire out_valid, fifo1_fault, fifo2_fault;
    wire [127:0] out_fp32;
    wire [63:0] out_bf16;
    operator_standalone dut(.*);

    reg [15:0] input_words [0:MAX_CASES*N-1];
    reg [7:0] gap_flags [0:MAX_CASES-1];
    integer selected_op, num_cases, case_limit;
    integer tc, beat, lane, cycle=0, out_count, in_count;
    integer first_in, last_in, first_out, last_out;
    integer unknown_beats, unknown_valid, premature_beats, fault1_seen, fault2_seen;
    integer waited, sample_file, summary_file;
    reg capture=0;
    string output_dir, data_dir;

    // Sample on consuming clock edges, before nonblocking updates, like a
    // downstream synchronous consumer. Inputs are driven on falling edges.
    always @(posedge clk) begin
        cycle=cycle+1;
        if (capture) begin
            if (in_valid) begin
                if (in_count==0) first_in=cycle;
                last_in=cycle;
                in_count=in_count+1;
            end
            if (out_valid === 1'b1) begin
                if (out_count==0) first_out=cycle;
                last_out=cycle;
                if (in_count==0) premature_beats=premature_beats+1;
                if ($isunknown(out_fp32) || $isunknown(out_bf16))
                    unknown_beats=unknown_beats+1;
                for (integer l=0; l<4; l=l+1)
                    $fwrite(sample_file,"%0d,%0d,%0d,%0d,%0d,%08h,%04h\n",
                        selected_op,tc,out_count,l,cycle,
                        out_fp32[l*32+:32],out_bf16[l*16+:16]);
                out_count=out_count+1;
            end else if (out_valid !== 1'b0) unknown_valid=unknown_valid+1;
            if (fifo1_fault === 1'b1) fault1_seen=1;
            if (fifo2_fault === 1'b1) fault2_seen=1;
        end
    end

    initial begin
        selected_op=OP_FILTER;
        if (selected_op<0 && !$value$plusargs("OP=%d",selected_op)) selected_op=0;
        if (selected_op<0 || selected_op>4) $fatal(1,"OP must be 0..4");
        op=selected_op;
        if (!$value$plusargs("CASES=%d",num_cases)) num_cases=26;
        if ($value$plusargs("CASE_LIMIT=%d",case_limit) && case_limit<num_cases)
            num_cases=case_limit;
        if (!$value$plusargs("OUT_DIR=%s",output_dir)) output_dir="../results/manual";
        if (num_cases<1 || num_cases>MAX_CASES) $fatal(1,"Invalid case count");
        if (!$value$plusargs("DATA_DIR=%s",data_dir)) data_dir="../../../../data/bf16";
        $readmemh({data_dir,"/inputs.hex"},input_words);
        $readmemh({data_dir,"/gaps.hex"},gap_flags);
        sample_file=$fopen({output_dir,"/rtl_samples.csv"},"w");
        summary_file=$fopen({output_dir,"/rtl_summary.csv"},"w");
        if (!sample_file || !summary_file) $fatal(1,"Cannot open result files");
        $fwrite(sample_file,"op,case_id,beat,lane,cycle,fp32_hex,bf16_hex\n");
        $fwrite(summary_file,"op,case_id,in_beats,out_beats,first_in,last_in,first_out,last_out,unknown_beats,unknown_valid,premature_beats,fifo1_fault,fifo2_fault,timeout\n");
        for (tc=0;tc<num_cases;tc=tc+1) begin
            // Mirrors the original integration: clear controls/FIFOs and
            // drain non-resettable floating IPs before starting each frame.
            @(negedge clk); capture=0; rst_n=0; in_valid=0; in_bf16=0;
            repeat(288) @(negedge clk);
            rst_n=1;
            repeat(16) @(negedge clk);
            out_count=0; in_count=0;
            first_in=-1;last_in=-1;first_out=-1;last_out=-1;
            unknown_beats=0;unknown_valid=0;premature_beats=0;
            fault1_seen=0;fault2_seen=0;capture=1;
            for (beat=0;beat<BEATS;beat=beat+1) begin
                if (gap_flags[tc]!=0 && beat%17==8) begin
                    in_valid=0;
                    @(negedge clk);
                end
                in_valid=1;
                for (lane=0;lane<4;lane=lane+1)
                    in_bf16[lane*16+:16]=input_words[tc*N+beat*4+lane];
                @(negedge clk);
            end
            in_valid=0; in_bf16=0; waited=0;
            while (out_count<BEATS && waited<6000) begin
                @(negedge clk); waited=waited+1;
            end
            // Capture late/duplicate beats rather than silently truncating.
            repeat(256) @(negedge clk);
            capture=0;
            $fwrite(summary_file,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                selected_op,tc,in_count,out_count,first_in,last_in,first_out,last_out,
                unknown_beats,unknown_valid,premature_beats,fault1_seen,fault2_seen,
                waited>=6000 ? 1:0);
            $display("CAPTURE op=%0d case=%0d input=%0d output=%0d first=%0d last=%0d fault=%0d/%0d",
                selected_op,tc,in_count,out_count,first_out-first_in,last_out-first_in,
                fault1_seen,fault2_seen);
        end
        $fclose(sample_file);$fclose(summary_file);
        $display("CAPTURE_COMPLETED op=%0d cases=%0d",selected_op,num_cases);
        $finish;
    end
    initial begin #20000000; $fatal(1,"Global simulation timeout"); end
endmodule
