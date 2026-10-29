# GUI: source {D:/path/submission_bf16/build/build.tcl}
# CLI: vivado -mode batch -source build/build.tcl -tclargs synth|bitstream
# Outputs go to build/generated, build/reports/rebuild, board/rebuilt.
source [file join [file dirname [file normalize [info script]]] common.tcl]
bf16::check_environment
set stage bitstream
if {[info exists ::bf16_stage]} {set stage $::bf16_stage}
if {[info exists ::argc] && $::argc>0} {set stage [lindex $::argv 0]}
if {$stage ni {synth bitstream}} {error "Stage must be synth or bitstream"}
bf16::open_or_create

# Same implementation settings as the existing 100 MHz Z2 design.
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    launch_runs synth_1 -jobs $bf16::jobs
    wait_on_run synth_1
}
bf16::check_run synth_1
open_run synth_1
report_utilization -file [file join $bf16::reports synth_utilization.rpt]
report_timing_summary -file [file join $bf16::reports synth_timing.rpt]
close_design
puts "BF16_SYNTHESIS_VERIFIED"
if {$stage eq "bitstream"} {
    if {![string match "*write_bitstream Complete*" [get_property STATUS [get_runs impl_1]]]} {
        launch_runs impl_1 -to_step write_bitstream -jobs $bf16::jobs
        wait_on_run impl_1
    }
    bf16::check_run impl_1
    open_run impl_1
    report_utilization -file [file join $bf16::reports impl_utilization.rpt]
    report_timing_summary -file [file join $bf16::reports timing_summary.rpt]
    report_drc -file [file join $bf16::reports drc.rpt]
    report_route_status -file [file join $bf16::reports route_status.rpt]
    report_clocks -file [file join $bf16::reports clocks.rpt]
    set status_file [open [file join $bf16::reports build_status.txt] w]
    puts $status_file "part=$bf16::part\nproject=$bf16::name\nvivado=[version -short]"
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
    set bit [file join [get_property DIRECTORY [get_runs impl_1]] design_1_wrapper.bit]
    set hwh [file join $bf16::project_dir ${bf16::name}.gen sources_1 bd design_1 hw_handoff design_1.hwh]
    foreach f [list $bit $hwh] {if {![file isfile $f]} {error "Missing build output: $f"}}
    file mkdir $bf16::exports
    file copy -force $bit [file join $bf16::exports design_1.bit]
    file copy -force $hwh [file join $bf16::exports design_1.hwh]
    file copy -force [file join $bf16::root src bf16 ps bench_snake_report.py] [file join $bf16::exports bench_snake_report.py]
    puts "BF16_BITSTREAM_VERIFIED"
    puts "BOARD_FILES=$bf16::exports"
    close_design
}
puts "BF16_BUILD_COMPLETE stage=$stage"
