param([string]$Bat)
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine="cmd.exe /c $Bat"; CurrentDirectory='D:\bench\claude_code'}
"ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId)"
