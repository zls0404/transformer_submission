# Shared paths. All inputs are resolved from this script, never from pwd.
namespace eval bf16 {
    variable root [file dirname [file dirname [file dirname [file normalize [info script]]]]]
    variable name bf16_z2
    variable part xc7z020clg400-1
    variable jobs 4
    if {[info exists ::bf16_project_dir]} {
        variable project_dir [file normalize $::bf16_project_dir]
    } else {
        variable project_dir [file join $root build generated bf16]
    }
    variable project_file [file join $project_dir ${name}.xpr]
    variable repo [file join $root src bf16 ip_repo]
    variable reports [file join $root build reports bf16 rebuild]
    variable exports [file join $root board bf16 rebuilt]
}
proc bf16::check_environment {} {
    if {![string match "2026.1*" [version -short]]} {
        error "This package was validated with Vivado 2026.1. Current version: [version -short]"
    }
    foreach f [list [file join $bf16::repo snake_acc_axi component.xml] \
                    [file join $bf16::repo snake_acc_axi src snake_acc_top.sv] \
                    [file join $bf16::root build bf16 ps7_pynq_z2.tcl]] {
        if {![file isfile $f]} {error "Required source is missing: $f"}
    }
    set_param general.maxThreads $bf16::jobs
    file mkdir $bf16::reports
}
proc bf16::check_run {run} {
    set status [get_property STATUS [get_runs $run]]
    if {![string match "*Complete*" $status]} {error "$run failed or is incomplete: $status"}
}
proc bf16::same_path {left right} {
    set left [file normalize $left]
    set right [file normalize $right]
    if {$::tcl_platform(platform) eq "windows"} {return [string equal -nocase $left $right]}
    return [string equal $left $right]
}
proc bf16::open_or_create {} {
    if {[llength [get_projects -quiet]]} {
        if {![bf16::same_path [get_property DIRECTORY [current_project]] $bf16::project_dir] || \
            [get_property NAME [current_project]] ne $bf16::name} {
            error "A different project is open. Close it before running this build script."
        }
    } elseif {[file isfile $bf16::project_file]} {
        open_project $bf16::project_file
    } else {
        source [file join $bf16::root build bf16 create_project.tcl]
    }
    if {[get_property PART [current_project]] ne $bf16::part} {error "Unexpected FPGA part"}
}
