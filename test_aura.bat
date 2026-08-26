@echo off
chcp 65001 > nul
echo =======================================================
echo  🔮 AuraAI Autonomous Execution Test Runner
echo =======================================================
echo.
.\.venv\Scripts\python.exe scripts\test_aura_autonomous.py
echo.
pause
