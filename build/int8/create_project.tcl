# Source this script from the Vivado Tcl Console, or run Vivado in batch mode.
# Fresh creation uses packaged sources/configurations; existing matching projects are reopened.
source [file join [file dirname [file normalize [info script]]] common.tcl]
int8::check_environment
if {[file isfile $int8::project_file]} {
    int8::open_or_create
    puts "INT8_PROJECT_OPENED=$int8::project_file"
    return
}
if {[llength [get_projects -quiet]]} {error "Close the current project before creating a new one."}
create_project $int8::name $int8::project_dir -part $int8::part
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set_property ip_repo_paths [list $int8::repo] [current_project]
update_ip_catalog -rebuild
source [file join $int8::root build int8 bd_config.tcl]
