@echo off
:: AuraAI Global Command Launcher
:: Location: aura.cmd
setlocal
set "AURA_ROOT=%~dp0"
if "%AURA_ROOT:~-1%"=="\" set "AURA_ROOT=%AURA_ROOT:~0,-1%"
cd /d "%AURA_ROOT%"

if "%~1"=="" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_voice_notch.py"
) else if "%~1"=="notch" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_voice_notch.py"
) else if "%~1"=="--notch" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_voice_notch.py"
) else if "%~1"=="voice" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_voice_notch.py"
) else if "%~1"=="--voice" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_voice_notch.py"
) else if "%~1"=="main" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --gui
) else if "%~1"=="--main" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --gui
) else if "%~1"=="gui" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --gui
) else if "%~1"=="--gui" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --gui
) else if "%~1"=="chat" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_chat_window.py"
) else if "%~1"=="--chat" (
    start "" "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\run_chat_window.py"
) else if "%~1"=="cli" (
    "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --cli
) else if "%~1"=="--cli" (
    "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --cli
) else (
    "%AURA_ROOT%\.venv\Scripts\python.exe" "%AURA_ROOT%\main.py" --cli %*
)
