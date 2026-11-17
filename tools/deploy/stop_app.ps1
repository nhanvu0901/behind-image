# Stop OUR app only: the process tree whose root is in run\app.pid, and only if its command line is ours.
$home_ = 'D:\code\behind-the-image'
$f = "$home_\run\app.pid"
if (-not (Test-Path $f)) { "no run\app.pid: nothing to stop"; exit 0 }
$p = [int](Get-Content $f)
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue
if (-not $proc) { "pid $p is not running"; Remove-Item $f -Force; exit 0 }
if ($proc.CommandLine -notlike '*behind-the-image*app.bat*') { "pid $p is not our app ($($proc.CommandLine)); refusing"; exit 2 }
cmd /c "taskkill /PID $p /T /F" | Out-Null
Start-Sleep -Seconds 1
Remove-Item $f, "$home_\run\python.pid" -Force -ErrorAction SilentlyContinue
$l = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
if ($l) { "STILL LISTENING on 8560 (pid $($l[0].OwningProcess))"; exit 3 } else { "stopped; 8560 is free" }
