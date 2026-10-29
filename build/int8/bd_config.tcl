create_bd_design SYS_SOC
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0
source [file join $int8::root build int8 ps7_pynq_z2.tcl]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} CONFIG.PCW_USE_S_AXI_HP1 {1} CONFIG.PCW_USE_S_AXI_HP2 {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}] [get_bd_cells processing_system7_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0
set_property -dict [list CONFIG.c_addr_width {32} CONFIG.c_include_mm2s {1} CONFIG.c_include_mm2s_dre {1} CONFIG.c_include_s2mm {0} CONFIG.c_include_sg {0} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {64} CONFIG.c_mm2s_burst_size {16} CONFIG.c_sg_length_width {16}] [get_bd_cells axi_dma_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_1
set_property -dict [list CONFIG.c_addr_width {32} CONFIG.c_include_mm2s {1} CONFIG.c_include_mm2s_dre {1} CONFIG.c_include_s2mm {0} CONFIG.c_include_sg {0} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {64} CONFIG.c_mm2s_burst_size {16} CONFIG.c_sg_length_width {16}] [get_bd_cells axi_dma_1]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_2
set_property -dict [list CONFIG.c_addr_width {32} CONFIG.c_include_mm2s {0} CONFIG.c_include_s2mm {1} CONFIG.c_include_s2mm_dre {1} CONFIG.c_include_sg {0} CONFIG.c_m_axi_s2mm_data_width {64} CONFIG.c_s2mm_burst_size {16} CONFIG.c_s_axis_s2mm_tdata_width {64} CONFIG.c_sg_length_width {16}] [get_bd_cells axi_dma_2]
create_bd_cell -type ip -vlnv xilinx.com:ip:axis_dwidth_converter:1.1 axis_dwidth_converter_0
set_property -dict [list CONFIG.HAS_MI_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.M_TDATA_NUM_BYTES {16} CONFIG.S_TDATA_NUM_BYTES {8}] [get_bd_cells axis_dwidth_converter_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axis_dwidth_converter:1.1 axis_dwidth_converter_1
set_property -dict [list CONFIG.HAS_MI_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.M_TDATA_NUM_BYTES {16} CONFIG.S_TDATA_NUM_BYTES {8}] [get_bd_cells axis_dwidth_converter_1]
create_bd_cell -type ip -vlnv xilinx.com:ip:axis_dwidth_converter:1.1 axis_dwidth_converter_2
set_property -dict [list CONFIG.HAS_MI_TKEEP {1} CONFIG.HAS_TKEEP {1} CONFIG.HAS_TLAST {1} CONFIG.M_TDATA_NUM_BYTES {8} CONFIG.S_TDATA_NUM_BYTES {4}] [get_bd_cells axis_dwidth_converter_2]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_interconnect_0
set_property -dict [list CONFIG.NUM_MI {4} CONFIG.NUM_SI {1}] [get_bd_cells axi_interconnect_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_interconnect_hp0
set_property -dict [list CONFIG.NUM_MI {1} CONFIG.NUM_SI {1}] [get_bd_cells axi_interconnect_hp0]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_interconnect_hp1
set_property -dict [list CONFIG.NUM_MI {1} CONFIG.NUM_SI {1}] [get_bd_cells axi_interconnect_hp1]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_interconnect_hp2
set_property -dict [list CONFIG.NUM_MI {1} CONFIG.NUM_SI {1}] [get_bd_cells axi_interconnect_hp2]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 xlconstant_0
set_property -dict [list CONFIG.CONST_VAL {1} CONFIG.CONST_WIDTH {1}] [get_bd_cells xlconstant_0]
create_bd_cell -type ip -vlnv xilinx.com:user:transformer_block_axi_top:1.0 transformer_block_ax_0
create_bd_intf_port -mode Master -vlnv xilinx.com:interface:ddrx_rtl:1.0 DDR
create_bd_intf_port -mode Master -vlnv xilinx.com:display_processing_system7:fixedio_rtl:1.0 FIXED_IO
connect_bd_intf_net -intf_net axi_dma_0_M_AXIS_MM2S [get_bd_intf_pins {axi_dma_0/M_AXIS_MM2S}] [get_bd_intf_pins {axis_dwidth_converter_0/S_AXIS}]
connect_bd_intf_net -intf_net axi_dma_0_M_AXI_MM2S [get_bd_intf_pins {axi_dma_0/M_AXI_MM2S}] [get_bd_intf_pins {axi_interconnect_hp0/S00_AXI}]
connect_bd_intf_net -intf_net axi_dma_1_M_AXIS_MM2S [get_bd_intf_pins {axi_dma_1/M_AXIS_MM2S}] [get_bd_intf_pins {axis_dwidth_converter_1/S_AXIS}]
connect_bd_intf_net -intf_net axi_dma_1_M_AXI_MM2S [get_bd_intf_pins {axi_dma_1/M_AXI_MM2S}] [get_bd_intf_pins {axi_interconnect_hp1/S00_AXI}]
connect_bd_intf_net -intf_net axi_dma_2_M_AXI_S2MM [get_bd_intf_pins {axi_dma_2/M_AXI_S2MM}] [get_bd_intf_pins {axi_interconnect_hp2/S00_AXI}]
connect_bd_intf_net -intf_net axi_interconnect_0_M00_AXI [get_bd_intf_pins {axi_interconnect_0/M00_AXI}] [get_bd_intf_pins {transformer_block_ax_0/s00_axi}]
connect_bd_intf_net -intf_net axi_interconnect_0_M01_AXI [get_bd_intf_pins {axi_interconnect_0/M01_AXI}] [get_bd_intf_pins {axi_dma_0/S_AXI_LITE}]
connect_bd_intf_net -intf_net axi_interconnect_0_M02_AXI [get_bd_intf_pins {axi_interconnect_0/M02_AXI}] [get_bd_intf_pins {axi_dma_1/S_AXI_LITE}]
connect_bd_intf_net -intf_net axi_interconnect_0_M03_AXI [get_bd_intf_pins {axi_interconnect_0/M03_AXI}] [get_bd_intf_pins {axi_dma_2/S_AXI_LITE}]
connect_bd_intf_net -intf_net axi_interconnect_hp0_M00_AXI [get_bd_intf_pins {axi_interconnect_hp0/M00_AXI}] [get_bd_intf_pins {processing_system7_0/S_AXI_HP0}]
connect_bd_intf_net -intf_net axi_interconnect_hp1_M00_AXI [get_bd_intf_pins {axi_interconnect_hp1/M00_AXI}] [get_bd_intf_pins {processing_system7_0/S_AXI_HP1}]
connect_bd_intf_net -intf_net axi_interconnect_hp2_M00_AXI [get_bd_intf_pins {axi_interconnect_hp2/M00_AXI}] [get_bd_intf_pins {processing_system7_0/S_AXI_HP2}]
connect_bd_intf_net -intf_net axis_dwidth_converter_0_M_AXIS [get_bd_intf_pins {axis_dwidth_converter_0/M_AXIS}] [get_bd_intf_pins {transformer_block_ax_0/s0_axis}]
connect_bd_intf_net -intf_net axis_dwidth_converter_1_M_AXIS [get_bd_intf_pins {axis_dwidth_converter_1/M_AXIS}] [get_bd_intf_pins {transformer_block_ax_0/s1_axis}]
connect_bd_intf_net -intf_net axis_dwidth_converter_2_M_AXIS [get_bd_intf_pins {axis_dwidth_converter_2/M_AXIS}] [get_bd_intf_pins {axi_dma_2/S_AXIS_S2MM}]
connect_bd_intf_net -intf_net processing_system7_0_DDR [get_bd_intf_ports {DDR}] [get_bd_intf_pins {processing_system7_0/DDR}]
connect_bd_intf_net -intf_net processing_system7_0_FIXED_IO [get_bd_intf_ports {FIXED_IO}] [get_bd_intf_pins {processing_system7_0/FIXED_IO}]
connect_bd_intf_net -intf_net processing_system7_0_M_AXI_GP0 [get_bd_intf_pins {processing_system7_0/M_AXI_GP0}] [get_bd_intf_pins {axi_interconnect_0/S00_AXI}]
connect_bd_intf_net -intf_net transformer_block_ax_0_m0_axis [get_bd_intf_pins {transformer_block_ax_0/m0_axis}] [get_bd_intf_pins {axis_dwidth_converter_2/S_AXIS}]
connect_bd_net -net proc_sys_reset_0_peripheral_aresetn [get_bd_pins {proc_sys_reset_0/peripheral_aresetn}] [get_bd_pins {axi_dma_0/axi_resetn}] [get_bd_pins {axi_dma_1/axi_resetn}] [get_bd_pins {axi_dma_2/axi_resetn}] [get_bd_pins {axi_interconnect_0/ARESETN}] [get_bd_pins {axi_interconnect_0/S00_ARESETN}] [get_bd_pins {axi_interconnect_0/M00_ARESETN}] [get_bd_pins {axi_interconnect_0/M01_ARESETN}] [get_bd_pins {axi_interconnect_0/M02_ARESETN}] [get_bd_pins {axi_interconnect_0/M03_ARESETN}] [get_bd_pins {axi_interconnect_hp0/ARESETN}] [get_bd_pins {axi_interconnect_hp0/S00_ARESETN}] [get_bd_pins {axi_interconnect_hp0/M00_ARESETN}] [get_bd_pins {axi_interconnect_hp1/ARESETN}] [get_bd_pins {axi_interconnect_hp1/S00_ARESETN}] [get_bd_pins {axi_interconnect_hp1/M00_ARESETN}] [get_bd_pins {axi_interconnect_hp2/ARESETN}] [get_bd_pins {axi_interconnect_hp2/S00_ARESETN}] [get_bd_pins {axi_interconnect_hp2/M00_ARESETN}] [get_bd_pins {axis_dwidth_converter_0/aresetn}] [get_bd_pins {axis_dwidth_converter_1/aresetn}] [get_bd_pins {axis_dwidth_converter_2/aresetn}] [get_bd_pins {transformer_block_ax_0/aresetn}]
connect_bd_net -net processing_system7_0_FCLK_CLK0 [get_bd_pins {processing_system7_0/FCLK_CLK0}] [get_bd_pins {axi_dma_0/s_axi_lite_aclk}] [get_bd_pins {axi_dma_0/m_axi_mm2s_aclk}] [get_bd_pins {axi_dma_1/s_axi_lite_aclk}] [get_bd_pins {axi_dma_1/m_axi_mm2s_aclk}] [get_bd_pins {axi_dma_2/s_axi_lite_aclk}] [get_bd_pins {axi_dma_2/m_axi_s2mm_aclk}] [get_bd_pins {axi_interconnect_0/ACLK}] [get_bd_pins {axi_interconnect_0/S00_ACLK}] [get_bd_pins {axi_interconnect_0/M00_ACLK}] [get_bd_pins {axi_interconnect_0/M01_ACLK}] [get_bd_pins {axi_interconnect_0/M02_ACLK}] [get_bd_pins {axi_interconnect_0/M03_ACLK}] [get_bd_pins {axi_interconnect_hp0/ACLK}] [get_bd_pins {axi_interconnect_hp0/S00_ACLK}] [get_bd_pins {axi_interconnect_hp0/M00_ACLK}] [get_bd_pins {axi_interconnect_hp1/ACLK}] [get_bd_pins {axi_interconnect_hp1/S00_ACLK}] [get_bd_pins {axi_interconnect_hp1/M00_ACLK}] [get_bd_pins {axi_interconnect_hp2/ACLK}] [get_bd_pins {axi_interconnect_hp2/S00_ACLK}] [get_bd_pins {axi_interconnect_hp2/M00_ACLK}] [get_bd_pins {axis_dwidth_converter_0/aclk}] [get_bd_pins {axis_dwidth_converter_1/aclk}] [get_bd_pins {axis_dwidth_converter_2/aclk}] [get_bd_pins {proc_sys_reset_0/slowest_sync_clk}] [get_bd_pins {processing_system7_0/M_AXI_GP0_ACLK}] [get_bd_pins {processing_system7_0/S_AXI_HP0_ACLK}] [get_bd_pins {processing_system7_0/S_AXI_HP1_ACLK}] [get_bd_pins {processing_system7_0/S_AXI_HP2_ACLK}] [get_bd_pins {transformer_block_ax_0/aclk}]
connect_bd_net -net processing_system7_0_FCLK_RESET0_N [get_bd_pins {processing_system7_0/FCLK_RESET0_N}] [get_bd_pins {proc_sys_reset_0/ext_reset_in}]
connect_bd_net -net xlconstant_0_dout [get_bd_pins {xlconstant_0/dout}] [get_bd_pins {proc_sys_reset_0/dcm_locked}]
assign_bd_address
set seg [get_bd_addr_segs {processing_system7_0/Data/SEG_axi_dma_0_Reg}]
if {[llength $seg]!=1} {error "Missing address segment: processing_system7_0/Data/SEG_axi_dma_0_Reg"}
set_property range 64K $seg
set_property offset 0x40400000 $seg
set seg [get_bd_addr_segs {processing_system7_0/Data/SEG_axi_dma_1_Reg}]
if {[llength $seg]!=1} {error "Missing address segment: processing_system7_0/Data/SEG_axi_dma_1_Reg"}
set_property range 64K $seg
set_property offset 0x40410000 $seg
set seg [get_bd_addr_segs {processing_system7_0/Data/SEG_axi_dma_2_Reg}]
if {[llength $seg]!=1} {error "Missing address segment: processing_system7_0/Data/SEG_axi_dma_2_Reg"}
set_property range 64K $seg
set_property offset 0x40420000 $seg
set seg [get_bd_addr_segs {processing_system7_0/Data/SEG_transformer_block_ax_0_reg0}]
if {[llength $seg]!=1} {error "Missing address segment: processing_system7_0/Data/SEG_transformer_block_ax_0_reg0"}
set_property range 4K $seg
set_property offset 0x40000000 $seg
set seg [get_bd_addr_segs {axi_dma_0/Data_MM2S/SEG_processing_system7_0_HP0_DDR_LOWOCM}]
if {[llength $seg]!=1} {error "Missing address segment: axi_dma_0/Data_MM2S/SEG_processing_system7_0_HP0_DDR_LOWOCM"}
set_property range 512M $seg
set_property offset 0x00000000 $seg
set seg [get_bd_addr_segs {axi_dma_1/Data_MM2S/SEG_processing_system7_0_HP1_DDR_LOWOCM}]
if {[llength $seg]!=1} {error "Missing address segment: axi_dma_1/Data_MM2S/SEG_processing_system7_0_HP1_DDR_LOWOCM"}
set_property range 512M $seg
set_property offset 0x00000000 $seg
set seg [get_bd_addr_segs {axi_dma_2/Data_S2MM/SEG_processing_system7_0_HP2_DDR_LOWOCM}]
if {[llength $seg]!=1} {error "Missing address segment: axi_dma_2/Data_S2MM/SEG_processing_system7_0_HP2_DDR_LOWOCM"}
set_property range 512M $seg
set_property offset 0x00000000 $seg
validate_bd_design
save_bd_design
generate_target all [get_files SYS_SOC.bd]
set wrapper [make_wrapper -files [get_files SYS_SOC.bd] -top]
add_files -norecurse $wrapper
set_property top SYS_SOC_wrapper [get_filesets sources_1]
update_compile_order -fileset sources_1
write_bd_tcl -force [file join $int8::project_dir export_sys_soc.tcl]
puts "INT8_PROJECT_CREATED=$int8::project_file"
