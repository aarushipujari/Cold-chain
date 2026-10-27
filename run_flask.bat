@echo off
title AI Cold-Chain Flask Dashboard (No Streamlit)
cd /d "%~dp0"
set FLASK_SKIP_DOTENV=1
echo ========================================================
echo   Starting AI Cold-Chain Flask Dashboard
echo   100%% Clean Native Python + Flask (PythonAnywhere Ready)
echo ========================================================
echo.
echo Opening http://127.0.0.1:5000 in your browser...
echo.
start http://127.0.0.1:5000
"C:\Users\aarus\AppData\Local\Programs\Python\Python310\python.exe" flask_app.py
pause
