@echo off
setlocal enabledelayedexpansion

:: Determine project root directory (parent of bin\)
set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "DOWNLY_HOME=%%~fI"

set "MAIN_PY=%DOWNLY_HOME%\main.py"
set "VENV_PYTHONW=%DOWNLY_HOME%\.venv\Scripts\pythonw.exe"
set "VENV_PYTHON=%DOWNLY_HOME%\.venv\Scripts\python.exe"

:: 1. Launch via Virtual Environment pythonw (Independent detached window)
if exist "%VENV_PYTHONW%" (
    start "" "%VENV_PYTHONW%" "%MAIN_PY%" %*
    exit /b 0
)

:: 2. Launch via Virtual Environment python
if exist "%VENV_PYTHON%" (
    start "" "%VENV_PYTHON%" "%MAIN_PY%" %*
    exit /b 0
)

:: 3. Launch via System pythonw
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw "%MAIN_PY%" %*
    exit /b 0
)

:: 4. Launch via System python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" python "%MAIN_PY%" %*
    exit /b 0
)

echo.
echo [Downly Error] No Python runtime found to launch Downly.
echo Please ensure Python is installed and available in PATH.
echo.
exit /b 1
