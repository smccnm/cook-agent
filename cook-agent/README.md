# Cook Agent

FastAPI + Streamlit meal-planning agent with three visible stages:

1. Planning extraction
2. Retrieval cascade
3. Streamed meal-plan generation

## Local No-Credential Mode

This project is designed to work locally even when optional credentials are missing.

- No `OPENAI_API_KEY`: planning and generation fall back to deterministic local logic.
- No `BING_SEARCH_API_KEY`: Bing retrieval is skipped.
- No `XHS_COOKIE` / `A1`: MCP retrieval is skipped.

The default local experience should still show:

- `planning_done`
- `retrieval_update`
- `recipe_stream`

## Optional Enhancements

Add credentials in `.env` to enable richer behavior:

- `OPENAI_API_KEY` and `OPENAI_MODEL`
- `BING_SEARCH_API_KEY`
- `XHS_COOKIE` and `A1`

## Quick Start

### Windows

```powershell
start.bat
```

### Linux / macOS

```bash
./start.sh
```

Both launchers will:

- create `venv` if missing
- install dependencies
- create `.env` from `.env.example` if needed
- start the backend
- poll `http://localhost:8000/health`
- launch Streamlit

## Manual Start

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
streamlit run app.py
```

Backend endpoints:

- `GET /health`
- `GET /api/v1/stream_meal_plan`
- docs at `http://localhost:8000/docs`

Frontend:

- `http://localhost:8501`

## Test Commands

```powershell
pytest tests/test_settings_and_models.py tests/test_planning.py tests/test_retrieval.py tests/test_generation.py tests/test_api.py tests/test_stream_client.py -q -p no:cacheprovider
python -m py_compile settings.py models.py planning.py retrieval.py generation.py agent.py main.py stream_client.py app.py tests/test_settings_and_models.py tests/test_planning.py tests/test_retrieval.py tests/test_generation.py tests/test_api.py tests/test_stream_client.py
```

## Environment Variables

See `.env.example` for the full list. The most important values are:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `BING_SEARCH_API_KEY`
- `XHS_COOKIE`
- `A1`
- `BACKEND_HOST`
- `BACKEND_PORT`
- `BACKEND_URL`
- `STREAMLIT_SERVER_PORT`
