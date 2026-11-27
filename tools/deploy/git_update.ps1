# Runs ON the server (copied there by git_deploy.sh as _deploy\git_update-<id>.ps1). Brings the server's git checkout
# (default D:\code\behind-the-image) up to origin/<Branch> with a fast-forward only, refreshes .venv when requirements.txt
# changed, optionally restarts OUR app. Takes the deploy lock run\deploy.lock like remote_update.ps1.
# It refuses (changes nothing) when the checkout is not on <Branch>, when a tracked file differs from HEAD, or when
# origin/<Branch> is not a fast-forward of HEAD. Tracked files are never discarded, reset, stashed or cleaned here.
# Never touches .env, books, library, projects, .venv* (except pip), run (except deploy.lock and last_deploy.txt), logs, cache.
# Exit codes: 0 ok / nothing to do, 11 failed, 12 code updated but our app did not start again, 20 lock timeout,
#             30 no .git, 31 wrong branch, 32 tracked files modified,
#             33 not a fast-forward, 34 fetch failed or origin/<Branch> missing, 36 server is not on the -Commit asked for.
param([Parameter(Mandatory)][string]$Branch, [string]$Commit = '', [switch]$Restart, [switch]$Check, [string]$JobGuard = '',
      [string]$Root = 'D:\code\behind-the-image', [switch]$NoVenv,
      [int]$WaitMinutes = 20, [int]$StaleMinutes = 30)
# 'Continue' on purpose: with 'Stop', Windows PowerShell 5.1 throws on any stderr text of a native command.
# Every native call is checked through $LASTEXITCODE instead.
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
$Id = 'git-' + (Get-Date -Format yyyyMMddHHmmss)
$lock = "$Root\run\deploy.lock"
New-Item -ItemType Directory -Force "$Root\logs", "$Root\run" | Out-Null

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

$code = 0
$stopped = $false      # our app was stopped by this script
$started = $false      # and started again
$merged = $false       # the merge changed the working tree
$remoteRef = "origin/$Branch"
function Refuse($c, $msg) { throw "REFUSE|$c|$msg" }     # nothing has been changed when this is thrown before the merge
# NOT named Git: PowerShell names are case-insensitive, so `& git` inside a function called Git would call itself forever.
function GitR { & git.exe -C $Root @args }
function Check-ProjectJobs {
  if ($JobGuard) {
    & powershell.exe -NoProfile -EncodedCommand $JobGuard
    if ($LASTEXITCODE -ne 0) { Refuse 37 'REFUSED: a project job is running or its state could not be verified.' }
  }
}
try {
  Check-ProjectJobs
  if (-not (Test-Path "$Root\.git")) { Refuse 30 "REFUSED: $Root is not a git checkout (no .git folder). Nothing was changed." }

  "== fetch"
  git -C $Root fetch -q origin 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { Refuse 34 "REFUSED: git fetch origin failed (exit $LASTEXITCODE). Nothing was changed." }
  git -C $Root rev-parse -q --verify "$remoteRef^{commit}" | Out-Null
  if ($LASTEXITCODE -ne 0) { Refuse 34 "REFUSED: $remoteRef does not exist on the remote. Was the branch pushed? Nothing was changed." }

  # ---- refusals, nothing is changed
  $cur = (GitR symbolic-ref --short -q HEAD)
  if ($cur -ne $Branch) {
    $curTxt = if ($cur) { $cur } else { '(detached HEAD)' }
    Refuse 31 "REFUSED: the server checkout is on branch $curTxt, not on $Branch. A person must look at it; nothing was changed."
  }
  $dirty = @(GitR status --porcelain --untracked-files=no)
  if ($dirty.Count -gt 0) {
    "REFUSED: $($dirty.Count) tracked file(s) in the server checkout differ from HEAD (modified, deleted or staged). First 20:"
    $dirty | Select-Object -First 20 | ForEach-Object { "  $_" }
    Refuse 32 "Someone changed code on the server or ran the old tar deploy (deploy_windows.sh). A person must look at these files; they are never discarded automatically. Nothing was changed."
  }
  $head = (GitR rev-parse HEAD)
  GitR merge-base --is-ancestor HEAD $remoteRef
  if ($LASTEXITCODE -ne 0) {
    Refuse 33 "REFUSED: $remoteRef is not a fast-forward of the server's HEAD ($($head.Substring(0, 7))). The history diverged (a commit exists only on the server, or the branch was rewritten). A person must look at it; nothing was changed."
  }

  # ---- what is incoming
  $target = (GitR rev-parse $remoteRef)
  if ($Commit -and $target -ne $Commit) {
    "NOTE: $remoteRef is $($target.Substring(0, 7)), not the commit asked for ($($Commit.Substring(0, [Math]::Min(7, $Commit.Length)))). Was the push complete?"
  }
  $files = @(GitR diff --name-only HEAD $remoteRef)
  "server HEAD: $($head.Substring(0, 7))   ${remoteRef}: $($target.Substring(0, 7))   incoming files: $($files.Count)"
  if ($files.Count -eq 0) {
    "Nothing incoming: the server is already on $remoteRef."
    if ($Commit -and $head -ne $Commit) { $code = 36; "The server is on $($head.Substring(0, 7)), not on the commit asked for ($Commit)." }
    if ($code -eq 0) { "UPDATE DONE (nothing to do)" }
    throw 'STOP|'
  }
  $reqIn = [bool]($files -contains 'requirements.txt')
  $appFiles = @($files | Where-Object { $_ -match '^(bti|config|style|skills|prompts)/' -or $_ -eq 'requirements.txt' })
  "requirements.txt among them: $reqIn   files the running app has loaded among them: $($appFiles.Count)"

  if ($Check) { "CHECK ONLY: nothing was changed (the fetch only updated origin/$Branch inside .git)."; throw 'STOP|' }

  # ---- act
  Check-ProjectJobs
  if ($Restart) {
    "== stop our app"
    & "$Root\tools\deploy\stop_app.ps1" | Out-Host
    if ($LASTEXITCODE -gt 0) { throw "could not stop our app" }
    $stopped = $true
  } elseif ($appFiles.Count -gt 0) {
    "WARNING: the page files change at once, but the running app keeps the old Python code until it is restarted with --restart."
  }

  "== merge (fast-forward only)"
  git -C $Root merge --ff-only $remoteRef 2>&1 | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "git merge --ff-only failed (exit $LASTEXITCODE); the working tree may be partly updated, look at: git status" }
  $merged = $true
  $now = (GitR rev-parse HEAD)
  if ($Commit -and $now -ne $Commit) {
    $code = 36
    "The server is now on $($now.Substring(0, 7)), NOT on the commit asked for ($Commit). Continuing with the venv step and the restart."
  }

  if (-not $NoVenv) {
    "== venv"
    $py = "$Root\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { throw ".venv is missing; see docs/WINDOWS.md (environments)" }
    $want = (Get-FileHash "$Root\requirements.txt" -Algorithm SHA256).Hash
    $had = if (Test-Path "$Root\.venv\req.sha256") { (Get-Content "$Root\.venv\req.sha256").Trim() } else { '' }
    if ($want -ne $had) {
      $ok = $false
      foreach ($i in 1..4) {
        & $py -m pip install -q --disable-pip-version-check -r "$Root\requirements.txt"
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        "pip failed (try $i); waiting"; Start-Sleep -Seconds (10 * $i)
      }
      if (-not $ok) { throw "pip install failed" }
      Set-Content "$Root\.venv\req.sha256" $want
    } else { "requirements unchanged" }
  }

  $appDown = $false
  if ($Restart) {
    "== start our app"
    & "$Root\tools\deploy\start_app.ps1" | Out-Host
    $startCode = $LASTEXITCODE
    $started = $true               # one attempt only: the finally block does not try again
    if ($startCode -ne 0) { $appDown = $true; "THE APP IS DOWN: start_app.ps1 failed (exit $startCode). Start it by hand: tools\deploy\start_app.ps1" }
  }
  Set-Content "$Root\run\last_deploy.txt" "id=git-$($now.Substring(0, 7)) finished=$(Get-Date -Format s) data=False"
  if ($code -eq 36) { "UPDATE DONE, but the server is not on the commit asked for (exit 36)" }
  if ($appDown) { $code = 12; "UPDATE DONE, but the app did not start (exit 12)" }
  if ($code -eq 0) { "UPDATE DONE" }
} catch {
  $m = "$_"
  if ($m -like 'STOP|*') {
    # normal early end (nothing incoming, or -Check); $code is already set
  } elseif ($m -like 'REFUSE|*') {
    $p = $m -split '\|', 3
    $code = [int]$p[1]; $p[2]
  } else {
    "DEPLOY FAILED: $m"
    $code = 11
    if ($merged) { "State: the checkout was fast-forwarded to $remoteRef; a later step failed." }
    elseif ($stopped) { "State: the checkout was NOT changed (it is still on its old commit)." }
  }
} finally {
  # An app we stopped must not stay down, whatever failed in between.
  if ($stopped -and -not $started) {
    "== trying to start our app again"
    & "$Root\tools\deploy\start_app.ps1" | Out-Host
    if ($LASTEXITCODE -ne 0) { "THE APP IS DOWN: start_app.ps1 failed (exit $LASTEXITCODE). Start it by hand: tools\deploy\start_app.ps1" }
  }
  Remove-Item -Recurse -Force $lock -ErrorAction SilentlyContinue
  Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue   # this per-deploy copy of the script
}
exit $code
