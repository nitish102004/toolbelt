@echo off
setlocal
rem gl -- top-layer CLI wrapper for the GitLab tool.
rem   Add this file's parent folder (tools\bin) to your PATH so `gl ...`
rem   works from anywhere. Callers never see the token or API details.
rem See docs/ARCHITECTURE.md for design and INSTALL.md for setup.
rem Optional per-machine settings (TOOLBELT_PYTHON, TOOLBELT_SECRETS, etc.)
rem live in an untracked bin/env.cmd -- see bin/env.cmd.example.
if exist "%~dp0env.cmd" call "%~dp0env.cmd"
set "TOOLS_SRC=%~dp0..\src"
set "PYTHONPATH=%TOOLS_SRC%;%PYTHONPATH%"
if defined TOOLBELT_PYTHON (
  if not exist "%TOOLBELT_PYTHON%" (
    1>&2 echo [toolbelt] TOOLBELT_PYTHON points to a file that does not exist:
    1>&2 echo   %TOOLBELT_PYTHON%
    1>&2 echo   Fix: setx TOOLBELT_PYTHON "C:\path\to\python.exe", or unset it and add Python to PATH.
    exit /b 2
  )
  "%TOOLBELT_PYTHON%" -m gitlab %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if errorlevel 1 (
  1>&2 echo [toolbelt] Python 3.11+ was not found on PATH.
  1>&2 echo   Fix: either add Python to PATH, or point TOOLBELT_PYTHON at an interpreter, e.g.
  1>&2 echo     setx TOOLBELT_PYTHON "H:\venv311\Scripts\python.exe"
  1>&2 echo   Then open a fresh terminal. See INSTALL.md step 3 for details.
  exit /b 2
)
python -m gitlab %*

