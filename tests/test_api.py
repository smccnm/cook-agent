import os

from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import main
from main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stream_route_emits_expected_event_names(monkeypatch):
    async def fake_process_agent_stream(_user_input: str):
        yield {"event": "planning_done", "data": {"search_queries": ["q1"]}}
        yield {
            "event": "retrieval_update",
            "data": {
                "query": "q1",
                "status": "success",
                "strategy": "MCP",
                "title": "番茄炒蛋",
                "source_url": "https://www.xiaohongshu.com/explore/test",
            },
        }
        yield {"event": "recipe_stream", "data": {"chunk": "hello"}}

    monkeypatch.setattr(main, "process_agent_stream", fake_process_agent_stream)

    client = TestClient(app)
    response = client.get(
        "/api/v1/stream_meal_plan",
        params={"user_input": "我有土豆和鸡蛋"},
    )

    assert response.status_code == 200
    body = response.text
    assert "planning_done" in body
    assert "retrieval_update" in body
    assert "recipe_stream" in body
    assert "source_url" in body


def test_stream_route_works_without_optional_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BING_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("XHS_COOKIE", raising=False)
    monkeypatch.delenv("A1", raising=False)

    client = TestClient(app)
    response = client.get("/api/v1/stream_meal_plan", params={"user_input": "我有鸡蛋和番茄"})

    assert response.status_code == 200
    assert "planning_done" in response.text
