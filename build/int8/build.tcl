# GUI: source {D:/path/submission_int8/build/build.tcl}
# CLI: vivado -mode batch -source build/build.tcl -tclargs synth|bitstream
# Outputs go to build/generated, build/reports/rebuild, board/rebuilt.
source [file join [file dirname [file normalize [info script]]] common.tcl]
int8::check_environment
set stage bitstream
if {[info exists ::int8_stage]} {set stage $::int8_stage}
if {[info exists ::argc] && $::argc>0} {set stage [lindex $::argv 0]}
if {$stage ni {synth bitstream}} {error "Stage must be synth or bitstream"}
int8::open_or_create

# Same implementation settings as the existing 100 MHz Z2 design.
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs $int8::jobs
    wait_on_run synth_1
}
int8::check_run synth_1
open_run synth_1
report_utilization -file [file join $int8::reports synth_utilization.rpt]
report_timing_summary -file [file join $int8::reports synth_timing.rpt]
close_design
puts "INT8_SYNTHESIS_VERIFIED"
if {$stage eq "bitstream"} {
    if {![string match "*write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {
        launch_runs impl_1 -to_step write_bitstream -jobs $int8::jobs
        wait_on_run impl_1
    }
    int8::check_run impl_1
    open_run impl_1
    report_utilization -file [file join $int8::reports impl_utilization.rpt]
    report_timing_summary -file [file join $int8::reports timing_summary.rpt]
    report_drc -file [file join $int8::reports drc.rpt]
    report_route_status -file [file join $int8::reports route_status.rpt]
    report_clocks -file [file join $int8::reports clocks.rpt]
    set status_file [open [file join $int8::reports build_status.txt] w]
    puts $status_file "part=$int8::part\nproject=$int8::name\nvivado=[version -short]"
    set timing_ok 1
    foreach type {max min} {
        set paths [get_timing_paths -delay_type $type -max_paths 1]
        if {![llength $paths]} {
            set timing_ok 0
            puts $status_file "${type}_slack=NO_PATH"
        } else {
            set slack [get_property SLACK [lindex $paths 0]]
            puts $status_file "${type}_slack_ns=$slack"
            if {$slack<0} {set timing_ok 0}
        }
    }
    set drc_errors [get_drc_violations -quiet -filter {SEVERITY == Error}]
    puts $status_file "drc_errors=[llength $drc_errors]\ntiming_ok=$timing_ok"
    close $status_file
    if {!$timing_ok || [llength $drc_errors]} {
        error "Implementation did not pass timing/DRC checks. See build/reports/rebuild. Existing board files were not replaced."
    }
    set bit [file join [get_property DIRECTORY [get_runs impl_1]] SYS_SOC_wrapper.bit]
    set hwh [file join $int8::project_dir ${int8::name}.gen sources_1 bd SYS_SOC hw_handoff SYS_SOC.hwh]
    foreach f [list $bit $hwh] {if {![file isfile $f]} {error "Missing build output: $f"}}
    file mkdir $int8::exports
    file copy -force $bit [file join $int8::exports sys_soc.bit]
    file copy -force $hwh [file join $int8::exports sys_soc.hwh]
    foreach script {mm.py golden_model.py test_acc.py validate_acc.py validate_acc_iscas.py vit_numpy.py vit_benchmark.py export_vit_weights.py} {file copy -force [file join $int8::root src int8 ps $script] [file join $int8::exports $script]}
    puts "INT8_BITSTREAM_VERIFIED"
    puts "BOARD_FILES=$int8::exports"
    close_design
}
puts "INT8_BUILD_COMPLETE stage=$stage"
