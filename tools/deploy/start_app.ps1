# Start OUR app (127.0.0.1:8560), detached so that it survives the end of the ssh session.
# Refuses if 8560 is already listening. Never touches port 8550 or any process that is not ours.
$ErrorActionPreference = 'Stop'
$home_ = 'D:\code\behind-the-image'
New-Item -ItemType Directory -Force "$home_\logs", "$home_\run" | Out-Null
$busy = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
if ($busy) { "PORT 8560 BUSY (pid $($busy[0].OwningProcess)); not starting"; exit 2 }
$o = Get-CimInstance Win32_OperatingSystem
"FreeVirtualKB=$($o.FreeVirtualMemory) FreePhysKB=$($o.FreePhysicalMemory)"
if ($o.FreePhysicalMemory -lt 2000000) { "LOW MEMORY; not starting"; exit 3 }
Copy-Item "$home_\tools\deploy\app.bat" "$home_\run\app.bat" -Force
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "cmd.exe /c $home_\run\app.bat"; CurrentDirectory = $home_ }
if ($r.ReturnValue -ne 0) { "LAUNCH FAILED $($r.ReturnValue)"; exit 4 }
Set-Content -Path "$home_\run\app.pid" -Value $r.ProcessId
Start-Sleep -Seconds 6
$py = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $r.ProcessId -and $_.Name -eq 'python.exe' }
"cmd pid=$($r.ProcessId) python pid=$($py.ProcessId)"
if ($py) { Set-Content -Path "$home_\run\python.pid" -Value $py.ProcessId }
$l = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
if ($l) { "LISTENING $($l[0].LocalAddress):8560 pid=$($l[0].OwningProcess)" } else { "NOT LISTENING yet; see logs\app.log" }
