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

echo [setup] Activating virtual environment...
call venv\Scripts\activate.bat

echo [setup] Installing dependencies...
pip install -r requirements.txt

if not exist ".env" (
    echo [setup] Creating .env from .env.example...
    copy /Y .env.example .env > nul
)

echo [backend] Starting FastAPI backend...
start "" python main.py

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
streamlit run app.py
