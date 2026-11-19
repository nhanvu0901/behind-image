@echo off
rem `bti`: the command for agents that run a project of the app (see AGENTS.md). Windows twin of tools/bti: uses the project's virtual environment,
rem the way tools\run_editor.bat does, and never installs anything.
rem Usage: tools\bti status [project] ^| do ^| approve ^| ops ^| job ^| undo ^| changes ^| schema ^| doc      env: BTI_URL (default http://127.0.0.1:8560), BTI_ACTOR
setlocal
set "ROOT=%~dp0.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo bti: no virtual environment at %ROOT%\.venv ^(run tools\run_editor.bat once to make it^) 1>&2
  exit /b 2
)
pushd "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" -m bti.cli %*
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
