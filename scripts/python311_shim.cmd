@echo off
if "%~1"=="--version" (
    echo Python 3.11.9
    exit /b 0
)
if "%~1"=="-V" (
    echo Python 3.11.9
    exit /b 0
)
if "%~1"=="-c" (
    if "%~2"=="import sys;print(sys.executable)" (
        echo %~f0
        exit /b 0
    )
)
"C:\Users\KARTHIKEYA\AppData\Local\Programs\Python\Python314\python.exe" %*

