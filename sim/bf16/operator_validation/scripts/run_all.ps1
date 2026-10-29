param(
    [string]$PythonExe = 'python',
    [string]$VivadoRoot = 'D:/vivado/2026.1/Vivado'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
function Invoke-Stage([string]$ScriptName, [string[]]$StageArgs = @()) {
    & $PythonExe -X utf8 (Join-Path $PSScriptRoot $ScriptName) @StageArgs
    if ($LASTEXITCODE -ne 0) { throw "Stage failed: $ScriptName" }
}
Invoke-Stage 'generate_vectors.py'
Invoke-Stage 'generate_integrated.py'
Invoke-Stage 'run_validation.py' @('--vivado', $VivadoRoot)
Invoke-Stage 'analyze_results.py'
Invoke-Stage 'run_integrated.py' @('--vivado', $VivadoRoot)
Invoke-Stage 'analyze_integrated.py'
Invoke-Stage 'plot_paper.py'
Invoke-Stage 'build_report.py' @('--markdown-only')
Write-Host 'Finished. Read report/validation_report.md and package picture/bf16/index.html.'
