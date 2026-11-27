# Read-only deploy preflight. The override is deliberate and never the default.
param([string]$BaseUrl = 'http://127.0.0.1:8560', [switch]$ForceWhileRunning)
if ($ForceWhileRunning) { exit 0 }
try {
  $projects = @(Invoke-RestMethod -UseBasicParsing -Uri "$BaseUrl/api/projects" -TimeoutSec 15 -ErrorAction Stop)
  foreach ($project in $projects) {
    $id = [uri]::EscapeDataString([string]$project.id)
    $state = Invoke-RestMethod -UseBasicParsing -Uri "$BaseUrl/api/projects/$id/state" -TimeoutSec 30 -ErrorAction Stop
    if ($null -eq $state.jobs -or @($state.problems | Where-Object { $_.code -in @('project_file_damaged', 'document_corrupt') -and $null -eq $_.step }).Count -gt 0) {
      Write-Output "REFUSED: cannot verify jobs for project $($project.id) because its state is damaged."
      exit 4
    }
    foreach ($job in @($state.jobs)) {
      if ($null -ne $job -and $job.state -in @('queued', 'waiting', 'running')) {
        Write-Output "REFUSED: project $($project.id) has a running $($job.kind) job ($($job.id)); wait or use --force-while-running."
        exit 3
      }
    }
  }
} catch {
  Write-Output "REFUSED: cannot verify running project jobs: $($_.Exception.Message)"
  exit 4
}
exit 0
