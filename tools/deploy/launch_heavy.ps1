# Runs ON the server. Detached launch of heavy_run.py (survives the end of the ssh session).
# Usage: powershell -File launch_heavy.ps1 -What "engine slow sweep" -Minutes 28 -PytestArgs "tests/engine -m slow"
param([string]$What, [int]$Minutes = 28, [string]$PytestArgs)
$h = 'D:\code\behind-the-image'
New-Item -ItemType Directory -Force "$h\logs" | Out-Null
$log = "$h\logs\heavy_run.log"
if (Test-Path "D:\bench\_heavy.lock") { "lock folder exists now (owner: $(Get-Content D:\bench\_heavy.lock\owner.txt -ErrorAction SilentlyContinue)); heavy_run.py will wait for it" }
$bat = "$h\run\heavy_run.bat"
Set-Content $bat "@echo off`r`ncd /d $h`r`nset PYTHONUTF8=1`r`n$h\.venv\Scripts\python.exe $h\tools\deploy\heavy_run.py `"$What`" $Minutes -- $PytestArgs > $log 2>&1`r`n"
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "cmd.exe /c $bat"; CurrentDirectory = $h }
"launched pid $($r.ProcessId) rc $($r.ReturnValue); log $log"
