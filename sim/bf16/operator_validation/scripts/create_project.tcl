# Run from Vivado Tcl Console:
# source {ABSOLUTE_PATH/scripts/create_project.tcl}
# Optional before sourcing: set operator_name layernorm
set root [file normalize [file join [file dirname [info script]] ..]]
if {![info exists operator_name]} {set operator_name softmax}
if {$operator_name ni {softmax layernorm rmsnorm silu gelu}} {error "Unknown operator_name"}
set project_dir [file join $root gui $operator_name]
set project_file [file join $project_dir bf16_${operator_name}.xpr]
if {[file exists $project_file]} {
    open_project $project_file
} else {
    create_project bf16_${operator_name} $project_dir -part xc7z020clg400-1
    set_property target_simulator XSim [current_project]
    set_property simulator_language Mixed [current_project]
    # Same original shared nonlinear engine, with no GEMM/AXI/DMA/PS.
    set rtl_names {gluttonous_array.v acc_block.v add_mul_block.v add_mul_block_x4.v basic_block.v basic_block_4.v max_block.v squre_exp_block.v snake_frame_fifo.sv fp32_to_bf16_rne.v}
    foreach n $rtl_names {add_files -norecurse [file join $root rtl $n]}
    add_files -fileset sim_1 -norecurse [glob [file join $root ip * sim *.vhd]]
    add_files -fileset sim_1 -norecurse [file join $root sim operator_standalone.sv]
    add_files -fileset sim_1 -norecurse [file join $root sim tb_operator_validation.sv]
    add_files -fileset sim_1 -norecurse [file join $root sim tb_${operator_name}.sv]
    set_property top tb_${operator_name} [get_filesets sim_1]
    set_property xsim.elaborate.debug_level typical [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
}
set_property -dict [list xsim.elaborate.xelab.more_options {-L floating_point_v7_1_22 -L unisims_ver -L secureip}] [get_filesets sim_1]
set data_dir [file normalize [file join $root .. .. .. data bf16]]
set result_dir [file join $root results gui_${operator_name}]
file mkdir $result_dir
set_property -dict [list xsim.simulate.xsim.more_options "-testplusarg \"DATA_DIR=$data_dir\" -testplusarg \"OUT_DIR=../../../../../../results/gui_${operator_name}\" -testplusarg \"CASES=26\""] [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
puts "Independent $operator_name simulation project is ready. Run Behavioral Simulation."
