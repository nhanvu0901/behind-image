# The action of the `bti-editor` task: start our app (run\app.bat) in this (the desktop) session with a hidden window.
$h = 'D:\code\behind-the-image'
Copy-Item "$h\tools\deploy\app.bat" "$h\run\app.bat" -Force
$p = Start-Process -FilePath cmd.exe -ArgumentList "/c $h\run\app.bat" -WorkingDirectory $h -WindowStyle Hidden -PassThru
Set-Content -Path "$h\run\app.pid" -Value $p.Id
