@echo off
cd /d "%~dp0"
call .\.venv\Scripts\python.exe run_chat_window.py
pause
