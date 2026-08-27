@echo off
setlocal
set "AURA_DIR=D:\Sreekanta\VS Code Project\Desktop AI\AuraAI"
cd /d "%AURA_DIR%"

set "PY=%AURA_DIR%\.venv\Scripts\python.exe"

if "%~1"=="" (
    "%PY%" "%AURA_DIR%\run_voice_notch.py"
) else if "%~1"=="notch" (
    "%PY%" "%AURA_DIR%\run_voice_notch.py"
) else if "%~1"=="--notch" (
    "%PY%" "%AURA_DIR%\run_voice_notch.py"
) else if "%~1"=="voice" (
    "%PY%" "%AURA_DIR%\run_voice_notch.py"
) else if "%~1"=="--voice" (
    "%PY%" "%AURA_DIR%\run_voice_notch.py"
) else if "%~1"=="gui" (
    "%PY%" "%AURA_DIR%\main.py" --gui
) else if "%~1"=="--gui" (
    "%PY%" "%AURA_DIR%\main.py" --gui
) else if "%~1"=="main" (
    "%PY%" "%AURA_DIR%\main.py" --gui
) else if "%~1"=="--main" (
    "%PY%" "%AURA_DIR%\main.py" --gui
) else if "%~1"=="chat" (
    "%PY%" "%AURA_DIR%\run_chat_window.py"
) else if "%~1"=="--chat" (
    "%PY%" "%AURA_DIR%\run_chat_window.py"
) else (
    "%PY%" "%AURA_DIR%\main.py" %*
)
