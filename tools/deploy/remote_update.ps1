# Runs ON the server (copied there by deploy_windows.sh). Takes the deploy lock, unpacks _deploy\code-<Id>.tgz
# (and _deploy\data-<Id>.tgz with -Data), mirrors the code folders, refreshes .venv when requirements.txt changed,
# optionally restarts OUR app. Writes only below D:\code\behind-the-image. Never deletes .venv*, cache, logs, run,
# _deploy, books, library, projects, demo_runs or research_media.
param([Parameter(Mandatory)][string]$Id, [switch]$Data, [switch]$Restart,
      [int]$WaitMinutes = 20, [int]$StaleMinutes = 30)
$ErrorActionPreference = 'Stop'
$home_ = 'D:\code\behind-the-image'
$dep = "$home_\_deploy"
$lock = "$home_\run\deploy.lock"
New-Item -ItemType Directory -Force "$home_\logs", "$home_\run" | Out-Null

# ---- the lock: a folder; mkdir fails when it exists (atomic). Older than $StaleMinutes = abandoned, taken over.
function Get-LockAge {
  $f = "$lock\owner.txt"
  $t = if (Test-Path $f) { (Get-Item $f).LastWriteTime } else { (Get-Item $lock).LastWriteTime }
  return (New-TimeSpan -Start $t -End (Get-Date)).TotalMinutes
}
$deadline = (Get-Date).AddMinutes($WaitMinutes)
$have = $false
while (-not $have) {
  cmd /c "mkdir `"$lock`" 2>nul" | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Set-Content "$lock\owner.txt" "id=$Id started=$(Get-Date -Format s) stale_after_min=$StaleMinutes"
    $have = $true; break
  }
  if ((Test-Path $lock) -and (Get-LockAge) -gt $StaleMinutes) {
    "deploy.lock is older than $StaleMinutes min ($(Get-Content "$lock\owner.txt" -ErrorAction SilentlyContinue)); taking it over"
    Start-Sleep -Milliseconds (Get-Random -Maximum 2000)
    if ((Test-Path $lock) -and (Get-LockAge) -gt $StaleMinutes) { Remove-Item -Recurse -Force $lock -ErrorAction SilentlyContinue }
    continue
  }
  if ((Get-Date) -gt $deadline) { "TIMEOUT: deploy.lock held for more than $WaitMinutes min by: $(Get-Content "$lock\owner.txt" -ErrorAction SilentlyContinue)"; exit 20 }
  "waiting for deploy.lock ($(Get-Content "$lock\owner.txt" -ErrorAction SilentlyContinue))"
  Start-Sleep -Seconds 5
}

$stage = "$dep\stage-$Id"
$code = 0
try {
  if ($Restart) { & "$home_\tools\deploy\stop_app.ps1" | Out-Host; if ($LASTEXITCODE -gt 0) { throw "could not stop our app" } }

  "== code"
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
  New-Item -ItemType Directory -Force $stage | Out-Null
  tar -xzf "$dep\code-$Id.tgz" -C $stage
  if ($LASTEXITCODE -ne 0) { throw "tar failed" }
  Get-ChildItem $stage -Recurse -Force -Filter '._*' | Remove-Item -Force -ErrorAction SilentlyContinue
  Get-ChildItem $stage -Force -Filter '.env*' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  $keep = @('.venv*', 'cache', 'logs', 'run', '_deploy', '__pycache__', '.pytest_cache')
  $protected = @('books', 'library', 'projects', 'demo_runs', 'research_media')   # never mirrored, never packed as code
  foreach ($d in Get-ChildItem $stage -Directory -Force) {
    if ($protected -contains $d.Name -or $d.Name -like '.venv*' -or $d.Name -in @('cache', 'logs', 'run', '_deploy')) { continue }
    robocopy $d.FullName "$home_\$($d.Name)" /MIR /XD @keep /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $($d.Name) failed ($LASTEXITCODE)" }
  }
  Get-ChildItem $stage -File -Force | ForEach-Object { Copy-Item $_.FullName "$home_\$($_.Name)" -Force }
  Remove-Item -Recurse -Force $stage
  Remove-Item "$dep\code-$Id.tgz" -Force

  if ($Data) {
    "== data (books, library, projects): overwrites same-named files, deletes nothing"
    tar -xzf "$dep\data-$Id.tgz" -C $home_
    if ($LASTEXITCODE -ne 0) { throw "data tar failed" }
    Remove-Item "$dep\data-$Id.tgz" -Force
    Get-ChildItem "$home_\books", "$home_\library", "$home_\projects" -Recurse -Force -Filter '._*' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
  }

  "== venv"
  $py = "$home_\.venv\Scripts\python.exe"
  if (-not (Test-Path $py)) { throw ".venv is missing; see docs/WINDOWS.md (environments)" }
  $want = (Get-FileHash "$home_\requirements.txt" -Algorithm SHA256).Hash
  $had = if (Test-Path "$home_\.venv\req.sha256") { (Get-Content "$home_\.venv\req.sha256").Trim() } else { '' }
  if ($want -ne $had) {
    $ok = $false
    foreach ($i in 1..4) {
      & $py -m pip install -q --disable-pip-version-check -r "$home_\requirements.txt"
      if ($LASTEXITCODE -eq 0) { $ok = $true; break }
      "pip failed (try $i); waiting"; Start-Sleep -Seconds (10 * $i)
    }
    if (-not $ok) { throw "pip install failed" }
    Set-Content "$home_\.venv\req.sha256" $want
  } else { "requirements unchanged" }

  if ($Restart) { "== restart"; & "$home_\tools\deploy\start_app.ps1" | Out-Host }
  Set-Content "$home_\run\last_deploy.txt" "id=$Id finished=$(Get-Date -Format s) data=$Data"
  "UPDATE DONE"
} catch {
  "DEPLOY FAILED: $_"
  $code = 11
} finally {
  Remove-Item -Recurse -Force $lock -ErrorAction SilentlyContinue
  Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue   # this per-deploy copy of the script
}
exit $code
