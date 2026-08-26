@echo off
chcp 65001 > nul
title Aura Autonomous Browser Engine - Test Suite
echo Starting Aura Autonomous Browser Interactive Test Runner...
.\.venv\Scripts\python.exe scripts\test_autonomous_browser_interactive.py
pause
