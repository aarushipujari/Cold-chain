@echo off
title Cold-Chain Arrhenius Live Dashboard
cd /d "%~dp0"
echo ========================================================
echo   Starting Cold-Chain Real-Time Dashboard & CSV Logger
echo ========================================================
echo.
echo NOTE: Make sure the Arduino IDE Serial Monitor is CLOSED!
echo.
"C:\Users\aarus\AppData\Local\Programs\Python\Python310\python.exe" dashboard.py
pause
