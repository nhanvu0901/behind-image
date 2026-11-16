param([string]$Log)
"FreeVirtualKB=$((Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory)"
if (Test-Path D:\bench\_heavy.lock) { Get-Content D:\bench\_heavy.lock\owner.txt } else { "no lock" }
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bench.bti' -and $_.Name -match 'python|ffmpeg|cmd' } | ForEach-Object { "$($_.ProcessId) $($_.Name)" }
if (Test-Path $Log) { Get-Content $Log -Tail 6 }
