@echo off
:: Wrapper that calls the PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0test-guardian.ps1" %*
