@echo off
title AI Cold-Chain Intelligent Web Dashboard
cd /d "%~dp0"
echo ========================================================
echo   Starting AI Cold-Chain Web Dashboard (Streamlit)
echo ========================================================
echo.
echo Opening interactive dashboard in your browser...
echo.
"C:\Users\aarus\AppData\Local\Programs\Python\Python310\python.exe" -m streamlit run app.py
pause
