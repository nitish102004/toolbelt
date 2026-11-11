@echo off
setlocal
set "BIN_DIR=%~dp0"
set "TOOLBELT_SIGNOZ_ENV=jj"
call "%BIN_DIR%soz.cmd" %*
