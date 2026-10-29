# CLI: vivado -mode batch -source build/build.tcl -tclargs int8|bf16 synth|bitstream
set root [file dirname [file dirname [file normalize [info script]]]]
set precision bf16
set requested_stage bitstream
if {[info exists ::target_precision]} {set precision $::target_precision}
if {[info exists ::argc] && $::argc>0} {set precision [lindex $::argv 0]}
if {[info exists ::argc] && $::argc>1} {set requested_stage [lindex $::argv 1]}
if {$precision ni {int8 bf16}} {error "Precision must be int8 or bf16"}
set saved_argv $::argv
set saved_argc $::argc
set ::argv [list $requested_stage]
set ::argc 1
try {source [file join $root build $precision build.tcl]} finally {set ::argv $saved_argv;set ::argc $saved_argc}
