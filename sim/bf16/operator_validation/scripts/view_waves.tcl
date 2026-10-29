# Use after opening one of the supplied .wdb files or launching behavioral simulation.
set base /tb_operator_validation
foreach n {softmax layernorm rmsnorm silu gelu} {
    if {[llength [get_objects -quiet /tb_${n}/test/clk]]} {set base /tb_${n}/test}
}
foreach candidate {/tb_integrated /tb_integrated_m4/run} {
    if {[llength [get_objects -quiet $candidate/clk]]} {set base $candidate}
}
foreach n {gemm softmax layernorm rmsnorm silu gelu layernorm_affine rmsnorm_affine masked_softmax swiglu} {
    if {[llength [get_objects -quiet /tb_pipeline_${n}/run/clk]]} {set base /tb_pipeline_${n}/run}
}
if {[current_wave_config] eq ""} {create_wave_config}
foreach n {clk rst_n op tc in_valid in_bf16 out_valid out_fp32 out_bf16 fifo1_fault fifo2_fault start a_data a_valid a_ready b_data b_valid b_ready out_data out_last out_ready busy done error mm_valid mm_fp32 mm_bf16} {
    set obj [get_objects -quiet $base/$n]
    if {[llength $obj]} {add_wave -radix hex $obj}
}
wave zoom full
