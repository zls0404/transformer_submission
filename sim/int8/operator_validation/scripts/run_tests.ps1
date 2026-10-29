param([string]$VivadoBin='D:/vivado/2026.1/Vivado/bin')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$package=Split-Path (Split-Path (Split-Path $root -Parent) -Parent) -Parent
$work=Join-Path $root 'build/xsim'
New-Item -ItemType Directory -Force -Path $work,(Join-Path $root 'raw') | Out-Null
Push-Location $work
try {
 $rtl=Get-ChildItem (Join-Path $package 'src/int8/ip_repo/transformer_block_axi_top/src/*.v') | ForEach-Object {$_.FullName}
 & "$VivadoBin/xvlog.bat" @rtl *> compile.log
 if($LASTEXITCODE){throw 'RTL compile failed'}
 foreach($top in @('tb_softmax_current','tb_gelu_current','tb_gelu_backpressure','tb_mm_current')){
  & "$VivadoBin/xvlog.bat" --sv (Join-Path $root "sim/$top.sv") *>> compile.log
  if($LASTEXITCODE){throw "Compile failed: $top"}
  & "$VivadoBin/xelab.bat" --debug typical --mt off --snapshot $top "work.$top" *> "$top.elab.log"
  if($LASTEXITCODE){throw "Elaboration failed: $top"}
  @('--testplusarg "ROOT=../.."',('--testplusarg "DATA_DIR='+(Join-Path $package 'data/int8').Replace('\','/')+'"'),('--tclbatch "'+(Join-Path $root 'scripts/run_wave.tcl').Replace('\','/')+'"'),('--wdb "'+(Join-Path $root "raw/$top.wdb").Replace('\','/')+'"')) | Set-Content xsim.options -Encoding ASCII
  & "$VivadoBin/xsim.bat" $top --file xsim.options *> "$top.sim.log"
  if($LASTEXITCODE){throw "Simulation failed: $top"}
  Get-Content -LiteralPath "$top.sim.log" | Set-Content -LiteralPath (Join-Path $root "raw/$top.log") -Encoding UTF8
 }
}finally{Pop-Location}
