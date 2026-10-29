# Before sourcing: set operator_name layernorm_affine
set root [file normalize [file join [file dirname [info script]] ..]]
if {![info exists operator_name]} {set operator_name gemm}
if {$operator_name ni {gemm softmax layernorm rmsnorm silu gelu layernorm_affine rmsnorm_affine masked_softmax swiglu}} {error "Unknown operator_name"}
set project_dir [file join $root gui pipeline_$operator_name]
set project_file [file join $project_dir bf16_pipeline_${operator_name}.xpr]
if {[file exists $project_file]} {
    open_project $project_file
} else {
    create_project bf16_pipeline_${operator_name} $project_dir -part xc7z020clg400-1
    set_property target_simulator XSim [current_project]
    set_property simulator_language Mixed [current_project]
    add_files -norecurse [concat [glob [file join $root rtl *.v]] [glob [file join $root rtl *.sv]]]
    add_files -fileset sim_1 -norecurse [glob [file join $root ip * sim *.vhd]]
    add_files -fileset sim_1 -norecurse [file join $root sim tb_integrated.sv]
    add_files -fileset sim_1 -norecurse [file join $root sim tb_pipeline_${operator_name}.sv]
    set_property top tb_pipeline_${operator_name} [get_filesets sim_1]
    set_property xsim.elaborate.debug_level typical [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
}
set_property -dict [list xsim.elaborate.xelab.more_options {-L floating_point_v7_1_22 -L unisims_ver -L secureip}] [get_filesets sim_1]
set data_dir [file normalize [file join $root .. .. .. data bf16 integrated]]
set result_dir [file join $root results gui_pipeline_${operator_name}]
file mkdir $result_dir
set_property -dict [list xsim.simulate.xsim.more_options "-testplusarg \"DATA_DIR=$data_dir\" -testplusarg \"OUT_DIR=../../../../../../results/gui_pipeline_${operator_name}\""] [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
puts "Pipeline $operator_name simulation project is ready. Run Behavioral Simulation."
