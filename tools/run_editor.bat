@echo off
rem Start the editing page backend on 127.0.0.1:8560 (never 8550, never 0.0.0.0 by default).
rem Usage: tools\run_editor.bat [--check]     env: BTI_PROJECTS_ROOT, BTI_EDITOR_PORT, BTI_PYTHON (to create the venv)
rem Windows twin of tools/run_editor.sh.
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "VENV=%ROOT%\.venv"
if not exist "%VENV%\Scripts\python.exe" (
  if defined BTI_PYTHON ( "%BTI_PYTHON%" -m venv "%VENV%" ) else ( python -m venv "%VENV%" )
  if errorlevel 1 ( echo could not create the venv >&2 & exit /b 1 )
)
"%VENV%\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 ( echo pip install failed >&2 & exit /b 1 )
if "%BTI_EDITOR_PORT%"=="" set "BTI_EDITOR_PORT=8560"
if "%BTI_EDITOR_PORT%"=="8550" ( echo port 8550 belongs to the comic UI >&2 & exit /b 1 )
if "%~1"=="--check" (
  "%VENV%\Scripts\python.exe" -c "import bti.editor.app" || exit /b 1
  echo ok
  exit /b 0
)
echo BTI editor on http://127.0.0.1:%BTI_EDITOR_PORT%
"%VENV%\Scripts\python.exe" -m uvicorn bti.editor.app:create_app --factory --host 127.0.0.1 --port %BTI_EDITOR_PORT%
exit /b %ERRORLEVEL%
