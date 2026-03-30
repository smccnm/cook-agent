#!/bin/bash
set -euo pipefail

echo ""
echo "====================================="
echo "  Cook Agent Launcher"
echo "====================================="
echo ""

if [ ! -d "venv" ]; then
  echo "[setup] Creating virtual environment..."
  python3 -m venv venv
fi

PYTHON_EXE="$(pwd)/venv/bin/python"
if [ ! -f "$PYTHON_EXE" ]; then
  echo "[setup] Virtual environment python not found."
  exit 1
fi

echo "[setup] Activating virtual environment..."
source venv/bin/activate

echo "[setup] Installing dependencies..."
"$PYTHON_EXE" -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[setup] Creating .env from .env.example..."
  cp .env.example .env
fi

echo "[backend] Starting FastAPI backend..."
"$PYTHON_EXE" main.py &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[backend] Waiting for health check..."
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "[backend] Ready at http://localhost:8000"
    echo "[frontend] Launching Streamlit at http://localhost:8501"
    "$PYTHON_EXE" -m streamlit run app.py --server.port 8501
    exit 0
  fi
  sleep 1
done

echo "[backend] Backend did not become ready in time."
exit 1
