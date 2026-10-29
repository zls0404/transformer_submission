# Log interface and control signals only; numerical CSV captures all accepted lanes.
foreach base {/tb_operator_validation /tb_integrated /tb_integrated_m4/run} {
 if {[llength [get_objects -quiet "$base/clk"]]>0} {
  foreach sig {clk rst_n op tc in_valid in_bf16 out_valid out_fp32 out_bf16 fifo1_fault fifo2_fault start aux_load a_data b_data a_valid b_valid a_ready b_ready a_loaded b_loaded aux_loaded busy done error out_data out_last out_ready mm_valid mm_fp32 mm_bf16} {
   set objects [get_objects -quiet "$base/$sig"]
   if {[llength $objects]>0} {log_wave $objects}
  }
 }
}
run all
quit
