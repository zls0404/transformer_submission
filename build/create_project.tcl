# CLI: vivado -mode batch -source build/create_project.tcl -tclargs int8|bf16
set root [file dirname [file dirname [file normalize [info script]]]]
set precision bf16
if {[info exists ::target_precision]} {set precision $::target_precision}
if {[info exists ::argc] && $::argc>0} {set precision [lindex $::argv 0]}
if {$precision ni {int8 bf16}} {error "Precision must be int8 or bf16"}
source [file join $root build $precision create_project.tcl]
