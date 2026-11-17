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
# Preferred: the on-demand task `bti-editor` (runs in the desktop session, where `agy` is signed in). Needs the task and a user at the console.
$taskOk = $false
schtasks /query /tn bti-editor 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  $console = (query user 2>$null | Select-String -Pattern 'console|Active' -Quiet)
  if ($console) { $taskOk = $true } else { "NOTE: no user is logged on at the console" }
} else { "NOTE: the task bti-editor does not exist" }
if ($taskOk) {
  schtasks /run /tn bti-editor | Out-Null
  foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    $l = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
    if ($l) { break }
  }
  $l = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
  if ($l) {
    $sid = (Get-Process -Id $l[0].OwningProcess).SessionId
    "LISTENING $($l[0].LocalAddress):8560 pid=$($l[0].OwningProcess) session=$sid (via task bti-editor)"
    exit 0
  }
  "task started but 8560 is not listening yet; see logs\app.log"
  exit 5
}
"WARNING: starting WITHOUT the desktop session: agy will not be available in this mode (the script buttons and the draft agent need it)."
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "cmd.exe /c $home_\run\app.bat"; CurrentDirectory = $home_ }
if ($r.ReturnValue -ne 0) { "LAUNCH FAILED $($r.ReturnValue)"; exit 4 }
Set-Content -Path "$home_\run\app.pid" -Value $r.ProcessId
Start-Sleep -Seconds 6
$py = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $r.ProcessId -and $_.Name -eq 'python.exe' }
"cmd pid=$($r.ProcessId) python pid=$($py.ProcessId)"
if ($py) { Set-Content -Path "$home_\run\python.pid" -Value $py.ProcessId }
$l = Get-NetTCPConnection -State Listen -LocalPort 8560 -ErrorAction SilentlyContinue
if ($l) { "LISTENING $($l[0].LocalAddress):8560 pid=$($l[0].OwningProcess)" } else { "NOT LISTENING yet; see logs\app.log" }
