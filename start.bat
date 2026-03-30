@echo off
setlocal

echo.
echo =====================================
echo   Cook Agent Launcher
echo =====================================
echo.

if not exist "venv" (
    echo [setup] Creating virtual environment...
    python -m venv venv
)

set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [setup] Virtual environment python not found.
    exit /b 1
)

echo [setup] Activating virtual environment...
call venv\Scripts\activate.bat

echo [setup] Installing dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt

if not exist ".env" (
    echo [setup] Creating .env from .env.example...
    copy /Y .env.example .env > nul
)

echo [backend] Starting FastAPI backend...
start "" "%PYTHON_EXE%" main.py

echo [backend] Waiting for health check...
set /a WAIT_COUNT=0
:wait_backend
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/health' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" > nul 2>&1
if %errorlevel%==0 goto backend_ready
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo [backend] Backend did not become ready in time.
    exit /b 1
)
timeout /t 1 /nobreak > nul
goto wait_backend

:backend_ready
echo [backend] Ready at http://localhost:8000
echo [frontend] Launching Streamlit at http://localhost:8501
start "" "%PYTHON_EXE%" -m streamlit run app.py --server.port 8501
echo [frontend] Streamlit launched in a separate window.
