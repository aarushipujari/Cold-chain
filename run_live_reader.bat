@echo off
title BioShield AI - Live Hardware Sensor Streamer
cd /d "%~dp0"
echo ========================================================
echo   Connecting to ESP32 Hardware ^& Streaming Live Probes
echo ========================================================
echo.
echo NOTE: Make sure the Arduino IDE Serial Monitor is CLOSED!
echo.
"C:\Users\aarus\AppData\Local\Programs\Python\Python310\python.exe" live_sensor_reader.py
pause
