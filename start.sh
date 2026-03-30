#!/bin/bash
set -euo pipefail

echo ""
echo "====================================="
echo "  Cook Agent Dev Launcher"
echo "====================================="
echo ""

if [ ! -f ".env" ]; then
  echo "[setup] Creating .env from .env.example..."
  cp .env.example .env
fi

echo "[backend] Starting FastAPI with reload in background..."
python main.py &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[frontend] Starting Streamlit with hot reload in this shell..."
echo "[frontend] Frontend: http://127.0.0.1:8501"
echo "[backend] Backend:  http://127.0.0.1:8000"
python -m streamlit run app.py --server.port 8501
