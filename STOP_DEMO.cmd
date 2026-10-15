@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -B "%~dp0run.py" stop %*
) else (
  python -B "%~dp0run.py" stop %*
)
if errorlevel 1 pause
