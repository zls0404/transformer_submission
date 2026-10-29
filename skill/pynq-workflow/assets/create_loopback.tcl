# Reusable Zynq-7000 AXI DMA loopback. Provide the actual board's PS7 preset.
# vivado -mode batch -source create_loopback.tcl -tclargs part preset project_dir export_dir clock_mhz project|bitstream
if {$argc != 6} {error "Expected: part ps7_preset project_dir export_dir clock_mhz project|bitstream"}
lassign $argv part preset project_dir export_dir clock_mhz stage
if {![regexp {^xc7z} $part]} {error "This hardware template supports Zynq-7000 PS7 only. The software skill is independent of this template."}
if {![string is double -strict $clock_mhz] || $clock_mhz<=0 || $clock_mhz>150} {error "Invalid PL clock MHz"}
if {$stage ni {project bitstream}} {error "Stage must be project or bitstream"}
set preset [file normalize $preset]
set project_dir [file normalize $project_dir]
set export_dir [file normalize $export_dir]
if {![file isfile $preset]} {error "Supply the actual board's PS7 configuration Tcl (cell name ps7)"}
if {[file exists $project_dir] || [file exists $export_dir]} {error "Use fresh project and export directories"}
if {[llength [get_projects -quiet]]} {error "Close other projects first"}
create_project loopback_zynq $project_dir -part $part
set_property target_language Verilog [current_project]
create_bd_design loopback_bd
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7
source $preset
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $clock_mhz] [get_bd_cells ps7]
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_micro_dma {0} CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {1} CONFIG.c_include_mm2s_dre {1} CONFIG.c_include_s2mm_dre {1} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axi_s2mm_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {64} CONFIG.c_s_axis_s2mm_tdata_width {64} CONFIG.c_sg_length_width {16}] [get_bd_cells axi_dma]
foreach {name inputs outputs} {ctrl_bus 1 1 memory_bus 2 1} {
 create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 $name
 set_property -dict [list CONFIG.NUM_SI $inputs CONFIG.NUM_MI $outputs] [get_bd_cells $name]
}
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset_control
set_property CONFIG.C_EXT_RESET_HIGH {0} [get_bd_cells reset_control]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 locked
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells locked]
foreach {left right} {
 ps7/M_AXI_GP0 ctrl_bus/S00_AXI
 ctrl_bus/M00_AXI axi_dma/S_AXI_LITE
 axi_dma/M_AXI_MM2S memory_bus/S00_AXI
 axi_dma/M_AXI_S2MM memory_bus/S01_AXI
 memory_bus/M00_AXI ps7/S_AXI_HP0
 axi_dma/M_AXIS_MM2S axi_dma/S_AXIS_S2MM
} {connect_bd_intf_net [get_bd_intf_pins $left] [get_bd_intf_pins $right]}
set clocks [list ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK axi_dma/s_axi_lite_aclk axi_dma/m_axi_mm2s_aclk axi_dma/m_axi_s2mm_aclk reset_control/slowest_sync_clk ctrl_bus/ACLK ctrl_bus/S00_ACLK ctrl_bus/M00_ACLK memory_bus/ACLK memory_bus/S00_ACLK memory_bus/S01_ACLK memory_bus/M00_ACLK]
foreach pin $clocks {connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $pin]}
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins reset_control/ext_reset_in]
connect_bd_net [get_bd_pins locked/dout] [get_bd_pins reset_control/dcm_locked]
foreach pin {axi_dma/axi_resetn ctrl_bus/ARESETN ctrl_bus/S00_ARESETN ctrl_bus/M00_ARESETN memory_bus/ARESETN memory_bus/S00_ARESETN memory_bus/S01_ARESETN memory_bus/M00_ARESETN} {
 connect_bd_net [get_bd_pins reset_control/peripheral_aresetn] [get_bd_pins $pin]
}
assign_bd_address
validate_bd_design
save_bd_design
set bd [get_files loopback_bd.bd]
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
set_property top loopback_bd_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
if {$stage eq "bitstream"} {
 launch_runs synth_1 -jobs 4
 wait_on_run synth_1
 if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed"}
 launch_runs impl_1 -to_step write_bitstream -jobs 4
 wait_on_run impl_1
 if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {error "Implementation failed"}
 open_run impl_1
 file mkdir $export_dir
 report_timing_summary -file [file join $export_dir timing_summary.rpt]
 report_utilization -file [file join $export_dir impl_utilization.rpt]
 report_drc -file [file join $export_dir drc.rpt]
 foreach type {max min} {
  set paths [get_timing_paths -delay_type $type -max_paths 1]
  if {![llength $paths] || [get_property SLACK [lindex $paths 0]]<0} {error "Timing failed; reports retained, no paired export"}
 }
 if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]} {error "DRC errors; no paired export"}
 set bit [file join [get_property DIRECTORY [get_runs impl_1]] loopback_bd_wrapper.bit]
 set hwh [file join $project_dir loopback_zynq.gen sources_1 bd loopback_bd hw_handoff loopback_bd.hwh]
 if {![file isfile $bit] || ![file isfile $hwh]} {error "Build output missing"}
 file copy $bit [file join $export_dir loopback.bit]
 file copy $hwh [file join $export_dir loopback.hwh]
 set f [open [file join $export_dir export_record.txt] w]
 puts $f "vivado=[version -short]\npart=$part\nclock_mhz=$clock_mhz\nproject=$project_dir\nsource_run=impl_1\nbit=loopback.bit\nhwh=loopback.hwh"
 close $f
 puts "PAIRED_LOOPBACK_EXPORTED=$export_dir"
}
puts "LOOPBACK_PROJECT_CREATED=$project_dir"
close_project
