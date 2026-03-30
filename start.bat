@echo off
setlocal

echo.
echo =====================================
echo   Cook Agent Dev Launcher
echo =====================================
echo.

if not exist ".env" (
    echo [setup] Creating .env from .env.example...
    copy /Y .env.example .env > nul
)

echo [backend] Starting FastAPI with reload in a separate window...
start "Cook Agent Backend" cmd /k "cd /d %CD% && python main.py"

echo [frontend] Starting Streamlit with hot reload in this window...
echo [frontend] Frontend: http://127.0.0.1:8501
echo [backend] Backend:  http://127.0.0.1:8000
python -m streamlit run app.py --server.port 8501
