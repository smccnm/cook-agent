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

echo "[setup] Activating virtual environment..."
source venv/bin/activate

echo "[setup] Installing dependencies..."
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[setup] Creating .env from .env.example..."
  cp .env.example .env
fi

echo "[backend] Starting FastAPI backend..."
python main.py &
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
    streamlit run app.py
    exit 0
  fi
  sleep 1
done

echo "[backend] Backend did not become ready in time."
exit 1
