$o=Get-CimInstance Win32_OperatingSystem
"FreeVirtualKB=$($o.FreeVirtualMemory)"
"--- procs"
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'ffmpeg.exe' -or $_.CommandLine -match '_chatterbox_worker|stages\.stage_4|stages\.stage_5' } | ForEach-Object { "$($_.ProcessId) $($_.Name) :: $($_.CommandLine.Substring(0,[Math]::Min(120,$_.CommandLine.Length)))" }
"--- lock"
if (Test-Path D:\bench\_heavy.lock) { Get-Content D:\bench\_heavy.lock\owner.txt } else { "no lock" }
"--- disk"
Get-PSDrive D | ForEach-Object { "D free GB: $([math]::Round($_.Free/1GB,1))" }
