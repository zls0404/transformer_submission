set script_root [file dirname [file normalize [info script]]]
foreach operator_name {softmax layernorm rmsnorm silu gelu} {
    source [file join $script_root create_project.tcl]
    close_project
}
foreach operator_name {gemm softmax layernorm rmsnorm silu gelu layernorm_affine rmsnorm_affine masked_softmax swiglu} {
    source [file join $script_root create_integrated_project.tcl]
    close_project
}
unset operator_name
puts "ALL_15_TEST_PROJECTS_CREATED"
