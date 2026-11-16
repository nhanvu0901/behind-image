$o=Get-CimInstance Win32_OperatingSystem
"FreeVirtualKB=$($o.FreeVirtualMemory) FreePhysKB=$($o.FreePhysicalMemory) TotalVisibleKB=$($o.TotalVisibleMemorySize)"
"--- production-like processes (names only)"
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '_chatterbox_worker|stages\.stage_4|stages\.stage_5|ffmpeg' } | ForEach-Object { "$($_.ProcessId) $($_.Name)" }
"--- port 8550 listener"
Get-NetTCPConnection -LocalPort 8550 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { "listening pid $($_.OwningProcess)" }
"--- fonts"
Get-ChildItem C:\Windows\Fonts | Where-Object { $_.Name -match '^(GOTHIC|segoeui|arial|futura|jost|montserrat|calibri|framd|trebuc)' } | ForEach-Object Name
"--- bench"
Test-Path D:\bench
"--- disk D free GB"
[math]::Round((Get-PSDrive D).Free/1GB,1)
