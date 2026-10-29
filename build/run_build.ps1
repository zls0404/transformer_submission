param([ValidateSet('int8','bf16')][string]$Precision='bf16',[ValidateSet('project','synth','bitstream')][string]$Stage='project',[string]$VivadoExe='D:/vivado/2026.1/Vivado/bin/vivado.bat')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$script=if($Stage -eq 'project'){'create_project.tcl'}else{'build.tcl'}
$logDir=Join-Path $root "build/reports/$Precision/rebuild"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Push-Location $root
try {
 if($Stage -eq 'project'){& $VivadoExe -mode batch -notrace -source (Join-Path $PSScriptRoot $script) -log (Join-Path $logDir 'project.log') -nojournal -tclargs $Precision}
 else{& $VivadoExe -mode batch -notrace -source (Join-Path $PSScriptRoot $script) -log (Join-Path $logDir "$Stage.log") -nojournal -tclargs $Precision $Stage}
 if($LASTEXITCODE -ne 0){throw "Vivado failed: $LASTEXITCODE"}
}finally{Pop-Location}
