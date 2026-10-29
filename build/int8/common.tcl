# Shared paths. All inputs are resolved from this script, never from pwd.
namespace eval int8 {
    variable root [file dirname [file dirname [file dirname [file normalize [info script]]]]]
    variable name int8_z2
    variable part xc7z020clg400-1
    variable jobs 4
    if {[info exists ::int8_project_dir]} {
        variable project_dir [file normalize $::int8_project_dir]
    } else {
        variable project_dir [file join $root build generated int8]
    }
    variable project_file [file join $project_dir ${name}.xpr]
    variable repo [file join $root src int8 ip_repo]
    variable reports [file join $root build reports int8 rebuild]
    variable exports [file join $root board int8 rebuilt]
}
proc int8::check_environment {} {
    if {![string match "2026.1*" [version -short]]} {
        error "This package was validated with Vivado 2026.1. Current version: [version -short]"
    }
    foreach f [list [file join $int8::repo transformer_block_axi_top component.xml] \
                    [file join $int8::repo transformer_block_axi_top src transformer_block_axi_top.v] \
                    [file join $int8::root build int8 bd_config.tcl]] {
        if {![file isfile $f]} {error "Required source is missing: $f"}
    }
    set_param general.maxThreads $int8::jobs
    file mkdir $int8::reports
}
proc int8::check_run {run} {
    set status [get_property STATUS [get_runs $run]]
    if {![string match "*Complete*" $status]} {error "$run failed or is incomplete: $status"}
}
proc int8::same_path {left right} {
    set left [file normalize $left]
    set right [file normalize $right]
    if {$::tcl_platform(platform) eq "windows"} {return [string equal -nocase $left $right]}
    return [string equal $left $right]
}
proc int8::open_or_create {} {
    if {[llength [get_projects -quiet]]} {
        if {![int8::same_path [get_property DIRECTORY [current_project]] $int8::project_dir] || \
            [get_property NAME [current_project]] ne $int8::name} {
            error "A different project is open. Close it before running this build script."
        }
    } elseif {[file isfile $int8::project_file]} {
        open_project $int8::project_file
    } else {
        source [file join $int8::root build int8 create_project.tcl]
    }
    if {[get_property PART [current_project]] ne $int8::part} {error "Unexpected FPGA part"}
}
