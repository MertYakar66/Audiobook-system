@echo off
REM Audiobook Generation System - Windows Setup Script
REM This batch file wraps the PowerShell setup script

echo.
echo ========================================
echo   Audiobook Generation System Setup
echo ========================================
echo.
echo Running PowerShell setup script...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

if errorlevel 1 (
    echo.
    echo Setup failed. Please check the errors above.
    pause
    exit /b 1
)

pause
