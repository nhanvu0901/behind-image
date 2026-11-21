# NOT RUN BY ANY SCRIPT. The one system change the owner may approve: a Task Scheduler task `bti-editor` that starts our app inside
# the owner's desktop session (so that `agy`, which is signed in there, works). Run it once, on the server, as `admin`, only after the
# owner's yes reaches the person running it:
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\code\behind-the-image\tools\deploy\create_task.ps1
# What it creates: one task, current user, interactive logon ("run only when the user is logged on"), normal privileges,
# NO trigger (it runs only when started on demand with `schtasks /run /tn bti-editor`).
# Remove it: schtasks /delete /tn bti-editor /f
$ErrorActionPreference = 'Stop'
$home_ = 'D:\code\behind-the-image'
# Not "$env:USERDOMAIN\$env:USERNAME": inside an ssh session USERDOMAIN is not the machine name and the account cannot be resolved.
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $home_\tools\deploy\task_app.ps1"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'bti-editor' -Action $action -Principal $principal -Settings $settings `
  -Description 'Starts the behind-the-image app on 127.0.0.1:8560 in the desktop session; no trigger, run on demand only.' | Out-Null
schtasks /query /tn bti-editor /fo list
