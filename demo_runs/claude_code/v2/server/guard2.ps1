param([string]$Job,[int]$Minutes=25)
$lock='D:\bench\_heavy.lock'
$o=Get-CimInstance Win32_OperatingSystem
if ($o.FreeVirtualMemory -lt 12000000) { "LOWMEM $($o.FreeVirtualMemory)"; exit 2 }
cmd /c "mkdir D:\bench\_heavy.lock 2>nul"
if ($LASTEXITCODE -ne 0) { $c=''; if (Test-Path "$lock\owner.txt") { $c=(Get-Content "$lock\owner.txt") }; "HELD $c"; exit 1 }
"claude_code job=$Job started=$(Get-Date -Format o) expected_end=$((Get-Date).AddMinutes($Minutes).ToString('o'))" | Set-Content "$lock\owner.txt"
$busy=Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'ffmpeg.exe' -and $_.CommandLine -notmatch 'bench') -or $_.CommandLine -match '_chatterbox_worker|stages\.stage_4|stages\.stage_5' }
if ($busy) { Remove-Item -Recurse -Force $lock; "BUSY production-like process present"; exit 3 }
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine="cmd.exe /c D:\bench\claude_code\$Job.bat"; CurrentDirectory='D:\bench\claude_code'}
"GOT launched $Job pid=$($r.ProcessId)"
