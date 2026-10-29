# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  set Page_0 [ipgui::add_page $IPINST -name "Page 0"]
  ipgui::add_param $IPINST -name "A_size" -parent ${Page_0}
  ipgui::add_param $IPINST -name "F_length_width" -parent ${Page_0}
  ipgui::add_param $IPINST -name "F_width_block_num_width" -parent ${Page_0}
  ipgui::add_param $IPINST -name "GELU_FIFO_DEPTH" -parent ${Page_0}
  ipgui::add_param $IPINST -name "IN_Feature_Block_num" -parent ${Page_0}
  ipgui::add_param $IPINST -name "OUT_Feature_Block_num" -parent ${Page_0}
  ipgui::add_param $IPINST -name "OUT_MEM_WIDTH" -parent ${Page_0}
  ipgui::add_param $IPINST -name "W_width_block_num_width" -parent ${Page_0}
  ipgui::add_param $IPINST -name "Weight_Block_num" -parent ${Page_0}
  ipgui::add_param $IPINST -name "data_width" -parent ${Page_0}
  ipgui::add_param $IPINST -name "num_gelu" -parent ${Page_0}
  ipgui::add_param $IPINST -name "shift_width" -parent ${Page_0}


}

proc update_PARAM_VALUE.A_size { PARAM_VALUE.A_size } {
	# Procedure called to update A_size when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.A_size { PARAM_VALUE.A_size } {
	# Procedure called to validate A_size
	return true
}

proc update_PARAM_VALUE.F_length_width { PARAM_VALUE.F_length_width } {
	# Procedure called to update F_length_width when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.F_length_width { PARAM_VALUE.F_length_width } {
	# Procedure called to validate F_length_width
	return true
}

proc update_PARAM_VALUE.F_width_block_num_width { PARAM_VALUE.F_width_block_num_width } {
	# Procedure called to update F_width_block_num_width when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.F_width_block_num_width { PARAM_VALUE.F_width_block_num_width } {
	# Procedure called to validate F_width_block_num_width
	return true
}

proc update_PARAM_VALUE.GELU_FIFO_DEPTH { PARAM_VALUE.GELU_FIFO_DEPTH } {
	# Procedure called to update GELU_FIFO_DEPTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.GELU_FIFO_DEPTH { PARAM_VALUE.GELU_FIFO_DEPTH } {
	# Procedure called to validate GELU_FIFO_DEPTH
	return true
}

proc update_PARAM_VALUE.IN_Feature_Block_num { PARAM_VALUE.IN_Feature_Block_num } {
	# Procedure called to update IN_Feature_Block_num when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.IN_Feature_Block_num { PARAM_VALUE.IN_Feature_Block_num } {
	# Procedure called to validate IN_Feature_Block_num
	return true
}

proc update_PARAM_VALUE.OUT_Feature_Block_num { PARAM_VALUE.OUT_Feature_Block_num } {
	# Procedure called to update OUT_Feature_Block_num when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.OUT_Feature_Block_num { PARAM_VALUE.OUT_Feature_Block_num } {
	# Procedure called to validate OUT_Feature_Block_num
	return true
}

proc update_PARAM_VALUE.OUT_MEM_WIDTH { PARAM_VALUE.OUT_MEM_WIDTH } {
	# Procedure called to update OUT_MEM_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.OUT_MEM_WIDTH { PARAM_VALUE.OUT_MEM_WIDTH } {
	# Procedure called to validate OUT_MEM_WIDTH
	return true
}

proc update_PARAM_VALUE.USE_POW2_SOFTMAX { PARAM_VALUE.USE_POW2_SOFTMAX } {
	# Procedure called to update USE_POW2_SOFTMAX when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.USE_POW2_SOFTMAX { PARAM_VALUE.USE_POW2_SOFTMAX } {
	# Procedure called to validate USE_POW2_SOFTMAX
	return true
}

proc update_PARAM_VALUE.W_width_block_num_width { PARAM_VALUE.W_width_block_num_width } {
	# Procedure called to update W_width_block_num_width when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.W_width_block_num_width { PARAM_VALUE.W_width_block_num_width } {
	# Procedure called to validate W_width_block_num_width
	return true
}

proc update_PARAM_VALUE.Weight_Block_num { PARAM_VALUE.Weight_Block_num } {
	# Procedure called to update Weight_Block_num when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.Weight_Block_num { PARAM_VALUE.Weight_Block_num } {
	# Procedure called to validate Weight_Block_num
	return true
}

proc update_PARAM_VALUE.data_width { PARAM_VALUE.data_width } {
	# Procedure called to update data_width when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.data_width { PARAM_VALUE.data_width } {
	# Procedure called to validate data_width
	return true
}

proc update_PARAM_VALUE.num_gelu { PARAM_VALUE.num_gelu } {
	# Procedure called to update num_gelu when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.num_gelu { PARAM_VALUE.num_gelu } {
	# Procedure called to validate num_gelu
	return true
}

proc update_PARAM_VALUE.shift_width { PARAM_VALUE.shift_width } {
	# Procedure called to update shift_width when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.shift_width { PARAM_VALUE.shift_width } {
	# Procedure called to validate shift_width
	return true
}


proc update_MODELPARAM_VALUE.A_size { MODELPARAM_VALUE.A_size PARAM_VALUE.A_size } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.A_size}] ${MODELPARAM_VALUE.A_size}
}

proc update_MODELPARAM_VALUE.data_width { MODELPARAM_VALUE.data_width PARAM_VALUE.data_width } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.data_width}] ${MODELPARAM_VALUE.data_width}
}

proc update_MODELPARAM_VALUE.shift_width { MODELPARAM_VALUE.shift_width PARAM_VALUE.shift_width } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.shift_width}] ${MODELPARAM_VALUE.shift_width}
}

proc update_MODELPARAM_VALUE.Weight_Block_num { MODELPARAM_VALUE.Weight_Block_num PARAM_VALUE.Weight_Block_num } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.Weight_Block_num}] ${MODELPARAM_VALUE.Weight_Block_num}
}

proc update_MODELPARAM_VALUE.IN_Feature_Block_num { MODELPARAM_VALUE.IN_Feature_Block_num PARAM_VALUE.IN_Feature_Block_num } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.IN_Feature_Block_num}] ${MODELPARAM_VALUE.IN_Feature_Block_num}
}

proc update_MODELPARAM_VALUE.OUT_Feature_Block_num { MODELPARAM_VALUE.OUT_Feature_Block_num PARAM_VALUE.OUT_Feature_Block_num } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.OUT_Feature_Block_num}] ${MODELPARAM_VALUE.OUT_Feature_Block_num}
}

proc update_MODELPARAM_VALUE.OUT_MEM_WIDTH { MODELPARAM_VALUE.OUT_MEM_WIDTH PARAM_VALUE.OUT_MEM_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.OUT_MEM_WIDTH}] ${MODELPARAM_VALUE.OUT_MEM_WIDTH}
}

proc update_MODELPARAM_VALUE.F_length_width { MODELPARAM_VALUE.F_length_width PARAM_VALUE.F_length_width } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.F_length_width}] ${MODELPARAM_VALUE.F_length_width}
}

proc update_MODELPARAM_VALUE.F_width_block_num_width { MODELPARAM_VALUE.F_width_block_num_width PARAM_VALUE.F_width_block_num_width } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.F_width_block_num_width}] ${MODELPARAM_VALUE.F_width_block_num_width}
}

proc update_MODELPARAM_VALUE.W_width_block_num_width { MODELPARAM_VALUE.W_width_block_num_width PARAM_VALUE.W_width_block_num_width } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.W_width_block_num_width}] ${MODELPARAM_VALUE.W_width_block_num_width}
}

proc update_MODELPARAM_VALUE.num_gelu { MODELPARAM_VALUE.num_gelu PARAM_VALUE.num_gelu } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.num_gelu}] ${MODELPARAM_VALUE.num_gelu}
}

proc update_MODELPARAM_VALUE.GELU_FIFO_DEPTH { MODELPARAM_VALUE.GELU_FIFO_DEPTH PARAM_VALUE.GELU_FIFO_DEPTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.GELU_FIFO_DEPTH}] ${MODELPARAM_VALUE.GELU_FIFO_DEPTH}
}

proc update_MODELPARAM_VALUE.USE_POW2_SOFTMAX { MODELPARAM_VALUE.USE_POW2_SOFTMAX PARAM_VALUE.USE_POW2_SOFTMAX } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.USE_POW2_SOFTMAX}] ${MODELPARAM_VALUE.USE_POW2_SOFTMAX}
}

