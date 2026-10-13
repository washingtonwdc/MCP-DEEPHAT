@echo off
chcp 65001 > nul
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0iniciar_deephat_bridge.ps1"
pause
