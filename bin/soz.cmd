@echo off
setlocal
set "TOOLS_SRC=%~dp0..\src"
set "PYTHONPATH=%TOOLS_SRC%;%PYTHONPATH%"
if defined TOOLBELT_PYTHON (
  "%TOOLBELT_PYTHON%" -m signoz %*
) else (
  python -m signoz %*
)
