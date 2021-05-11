@echo off
:: This wrapper script is necessary to make the "labbench-rack" command on windows work
@SET "PYTHON_EXE=%~dp0\..\python.exe"
call "%PYTHON_EXE%" "%~dp0\labbench-rack-script.py" %*