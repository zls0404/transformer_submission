# Source this script from the Vivado Tcl Console, or run Vivado in batch mode.
# Fresh creation uses packaged sources/configurations; existing matching projects are reopened.
source [file join [file dirname [file normalize [info script]]] common.tcl]
bf16::check_environment
if {[file isfile $bf16::project_file]} {
    bf16::open_or_create
    puts "BF16_PROJECT_OPENED=$bf16::project_file"
    return
}
if {[llength [get_projects -quiet]]} {error "Close the current project before creating a new one."}
create_project $bf16::name $bf16::project_dir -part $bf16::part
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set_property ip_repo_paths [list $bf16::repo] [current_project]
update_ip_catalog -rebuild
create_bd_design design_1
# PS7
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7
source [file join $bf16::root build bf16 ps7_pynq_z2.tcl]
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
set_property -dict [list \
  CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_USE_S_AXI_HP1 {1} CONFIG.PCW_USE_S_AXI_HP2 {1} \
  CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
] [get_bd_cells ps7]

create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_ps7_100M
set_property CONFIG.C_EXT_RESET_HIGH {0} [get_bd_cells rst_ps7_100M]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_interconnect_ctrl
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {4} CONFIG.STRATEGY {2}] [get_bd_cells axi_interconnect_ctrl]

proc add_dma {name mm2s s2mm} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 $name
    set d [get_bd_cells $name]
    if {$mm2s} {
        set_property -dict [list CONFIG.c_include_mm2s {1} CONFIG.c_include_mm2s_dre {1} \
            CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {16} \
            CONFIG.c_m_axi_mm2s_protocol {AXI3}] $d
    } else {
        set_property CONFIG.c_include_mm2s {0} $d
    }
    if {$s2mm} {
        set_property -dict [list CONFIG.c_include_s2mm {1} CONFIG.c_include_s2mm_dre {1} \
            CONFIG.c_m_axi_s2mm_data_width {64} CONFIG.c_s_axis_s2mm_tdata_width {64} \
            CONFIG.c_m_axi_s2mm_protocol {AXI3}] $d
    } else {
        set_property CONFIG.c_include_s2mm {0} $d
    }
    set_property CONFIG.c_include_sg {0} $d
}
add_dma dma_a 1 0
add_dma dma_b 1 0
add_dma dma_out 0 1

create_bd_cell -type ip -vlnv xilinx.com:user:snake_acc_axi:1.0 snake_acc_axi_0
set_property -dict [list CONFIG.M {4} CONFIG.K {4}] [get_bd_cells snake_acc_axi_0]

# clock connections. PS7 ACLK ports are explicit clock inputs; do not use
# clkrst automation because Vivado 2026.1 rejects HPx_ACLK as an object.
foreach p {S_AXI_HP0_ACLK S_AXI_HP1_ACLK S_AXI_HP2_ACLK M_AXI_GP0_ACLK} {
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/$p]
}
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins rst_ps7_100M/slowest_sync_clk]
foreach p {aclk} { connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins snake_acc_axi_0/$p] }
foreach d {dma_a dma_b dma_out} {
  connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $d/s_axi_lite_aclk]
  if {$d != "dma_out"} { connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $d/m_axi_mm2s_aclk] }
  if {$d == "dma_out"} { connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $d/m_axi_s2mm_aclk] }
}
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_interconnect_ctrl/ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_interconnect_ctrl/S00_ACLK]
foreach i {0 1 2 3} { connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_interconnect_ctrl/M0${i}_ACLK] }

# reset connections
set rst rst_ps7_100M/peripheral_aresetn
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_ps7_100M/ext_reset_in]
connect_bd_net [get_bd_pins $rst] [get_bd_pins snake_acc_axi_0/aresetn]
foreach d {dma_a dma_b dma_out} { connect_bd_net [get_bd_pins $rst] [get_bd_pins $d/axi_resetn] }
connect_bd_net [get_bd_pins $rst] [get_bd_pins axi_interconnect_ctrl/ARESETN]
connect_bd_net [get_bd_pins $rst] [get_bd_pins axi_interconnect_ctrl/S00_ARESETN]
foreach i {0 1 2 3} { connect_bd_net [get_bd_pins $rst] [get_bd_pins axi_interconnect_ctrl/M0${i}_ARESETN] }

# GP0 control interconnect
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins axi_interconnect_ctrl/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_ctrl/M00_AXI] [get_bd_intf_pins dma_a/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_ctrl/M01_AXI] [get_bd_intf_pins dma_b/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_ctrl/M02_AXI] [get_bd_intf_pins dma_out/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_ctrl/M03_AXI] [get_bd_intf_pins snake_acc_axi_0/s_axi]

# HP datapath. Zynq-7000 HP ports are AXI3 while AXI DMA masters are AXI4,
# so insert explicit protocol converters. This does not depend on the DMA
# c_m_axi_*_protocol option being honored.
proc add_axi3_bridge {name} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_protocol_converter:2.1 $name
    set_property CONFIG.SI_PROTOCOL {AXI4} [get_bd_cells $name]
    set_property CONFIG.MI_PROTOCOL {AXI3} [get_bd_cells $name]
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $name/aclk]
    connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins $name/aresetn]
}
add_axi3_bridge pc_hp0
add_axi3_bridge pc_hp1
add_axi3_bridge pc_hp2
connect_bd_intf_net [get_bd_intf_pins dma_a/M_AXI_MM2S] [get_bd_intf_pins pc_hp0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins pc_hp0/M_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
connect_bd_intf_net [get_bd_intf_pins dma_b/M_AXI_MM2S] [get_bd_intf_pins pc_hp1/S_AXI]
connect_bd_intf_net [get_bd_intf_pins pc_hp1/M_AXI] [get_bd_intf_pins ps7/S_AXI_HP1]
connect_bd_intf_net [get_bd_intf_pins dma_out/M_AXI_S2MM] [get_bd_intf_pins pc_hp2/S_AXI]
connect_bd_intf_net [get_bd_intf_pins pc_hp2/M_AXI] [get_bd_intf_pins ps7/S_AXI_HP2]

# streaming datapath
connect_bd_intf_net [get_bd_intf_pins dma_a/M_AXIS_MM2S] [get_bd_intf_pins snake_acc_axi_0/s_axis_a]
connect_bd_intf_net [get_bd_intf_pins dma_b/M_AXIS_MM2S] [get_bd_intf_pins snake_acc_axi_0/s_axis_b]
connect_bd_intf_net [get_bd_intf_pins snake_acc_axi_0/m_axis] [get_bd_intf_pins dma_out/S_AXIS_S2MM]

# Optional interrupt intentionally left unconnected. PYNQ can poll status 0x04;
# connecting scalar irq directly to the PS 20-bit IRQ_F2P bus causes a width DRC.

# Register map must match the PYNQ host script. Never ignore address failures.
assign_bd_address
foreach entry {{dma_a 0x40400000} {dma_b 0x40410000} {dma_out 0x40420000} {snake_acc_axi_0 0x43C00000}} {
    lassign $entry cell base
    set segments [get_bd_addr_segs -quiet ps7/Data/SEG_${cell}_*]
    if {[llength $segments]!=1} {error "Expected exactly one control address segment for $cell: $segments"}
    set_property OFFSET $base $segments
    if {[get_property OFFSET $segments]!=$base} {error "Register address mismatch for $cell"}
}

validate_bd_design
save_bd_design

set bd [get_files design_1.bd]
generate_target all $bd
set wrapper [make_wrapper -files $bd -top]
add_files -norecurse $wrapper
set_property top design_1_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
write_bd_tcl -force [file join $bf16::project_dir export_design_1.tcl]
report_ip_status -file [file join $bf16::reports ip_status_project.rpt]
set f [open [file join $bf16::reports project_config.txt] w]
puts $f "part=[get_property PART [current_project]]
project=$bf16::project_file
ip_repo=$bf16::repo"
puts $f "M=[get_property CONFIG.M [get_bd_cells snake_acc_axi_0]]
K=[get_property CONFIG.K [get_bd_cells snake_acc_axi_0]]
N=768"
puts $f "fclk0_mhz=[get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ [get_bd_cells ps7]]"
foreach entry {{dma_a 0x40400000} {dma_b 0x40410000} {dma_out 0x40420000} {snake_acc_axi_0 0x43C00000}} {
 lassign $entry cell base
 puts $f "$cell=[get_property OFFSET [get_bd_addr_segs ps7/Data/SEG_${cell}_*]]"
}
close $f
puts "BF16_PROJECT_CREATED=$bf16::project_file"
puts "Next: source build/build.tcl, or open the project in Vivado."
