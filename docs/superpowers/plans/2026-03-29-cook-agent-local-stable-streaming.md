# Cook Agent Local-Stable Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the existing cook-agent into a local-stable FastAPI + Streamlit meal-planning workflow that always completes the three visible stages, even when optional external credentials are missing.

**Architecture:** Keep the current top-level entrypoints (`main.py`, `app.py`, `start.bat`, `start.sh`) but rework the internals around clear modules for settings, planning, retrieval, generation, orchestration, and SSE transport. Treat OpenAI, MCP, Bing, and Playwright as optional capability layers that enhance the same workflow instead of defining separate codepaths.

**Tech Stack:** Python 3.10+, FastAPI, sse-starlette, Streamlit, Pydantic v2, pydantic-settings, OpenAI Python SDK, httpx, BeautifulSoup4, Playwright, pytest, pytest-asyncio

---

## File Structure

### Create

- `d:\Appdata\Agent\cook-agent\settings.py`
- `d:\Appdata\Agent\cook-agent\planning.py`
- `d:\Appdata\Agent\cook-agent\generation.py`
- `d:\Appdata\Agent\cook-agent\stream_client.py`
- `d:\Appdata\Agent\cook-agent\tests\conftest.py`
- `d:\Appdata\Agent\cook-agent\tests\test_settings_and_models.py`
- `d:\Appdata\Agent\cook-agent\tests\test_planning.py`
- `d:\Appdata\Agent\cook-agent\tests\test_retrieval.py`
- `d:\Appdata\Agent\cook-agent\tests\test_generation.py`
- `d:\Appdata\Agent\cook-agent\tests\test_api.py`
- `d:\Appdata\Agent\cook-agent\tests\test_stream_client.py`

### Modify

- `d:\Appdata\Agent\cook-agent\requirements.txt`
- `d:\Appdata\Agent\cook-agent\models.py`
- `d:\Appdata\Agent\cook-agent\retrieval.py`
- `d:\Appdata\Agent\cook-agent\agent.py`
- `d:\Appdata\Agent\cook-agent\main.py`
- `d:\Appdata\Agent\cook-agent\app.py`
- `d:\Appdata\Agent\cook-agent\.env.example`
- `d:\Appdata\Agent\cook-agent\README.md`
- `d:\Appdata\Agent\cook-agent\start.bat`
- `d:\Appdata\Agent\cook-agent\start.sh`

### Responsibilities

- `settings.py`
  - Load environment variables once.
  - Expose capability flags like `openai_enabled`, `bing_enabled`, and `mcp_enabled`.

- `models.py`
  - Hold Pydantic v2 contracts for Node 1, Node 2, Node 3, and SSE payloads.

- `planning.py`
  - Implement local deterministic planning and the OpenAI-backed planning wrapper.

- `retrieval.py`
  - Implement the four-stage fallback cascade and concurrent query retrieval.

- `generation.py`
  - Implement local deterministic meal-plan composition and the OpenAI-backed streaming wrapper.

- `agent.py`
  - Orchestrate Node 1, Node 2, and Node 3, yielding normalized events as soon as they are available.

- `main.py`
  - Expose FastAPI routes and use `EventSourceResponse`.

- `stream_client.py`
  - Parse backend SSE lines into structured frontend events that are easy to test.

- `app.py`
  - Render the chat UI, status panels, and typing-style output using `st.write_stream()`.

## Task 1: Establish Clean Settings, Contracts, And Test Tooling

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\settings.py`
- Create: `d:\Appdata\Agent\cook-agent\tests\conftest.py`
- Create: `d:\Appdata\Agent\cook-agent\tests\test_settings_and_models.py`
- Modify: `d:\Appdata\Agent\cook-agent\requirements.txt`
- Modify: `d:\Appdata\Agent\cook-agent\models.py`

- [ ] **Step 1: Write the failing settings and model tests**

```python
from models import IngredientItem, RetrievalUpdateData
from settings import AppSettings


def test_settings_flags_without_optional_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BING_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("XHS_COOKIE", raising=False)
    monkeypatch.delenv("A1", raising=False)

    settings = AppSettings()

    assert settings.openai_enabled is False
    assert settings.bing_enabled is False
    assert settings.mcp_enabled is False


def test_retrieval_update_payload_keeps_strategy_and_message():
    payload = RetrievalUpdateData(
        query="土豆 茄子 少油",
        status="success",
        strategy="Schema",
        title="少油版地三鲜",
        message="schema hit",
    )

    assert payload.strategy == "Schema"
    assert payload.title == "少油版地三鲜"


def test_ingredient_item_preserves_quantity_text():
    item = IngredientItem(name="番茄", quantity="3个")
    assert item.quantity == "3个"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_settings_and_models.py -q`

Expected: FAIL with import errors or missing model/settings attributes.

- [ ] **Step 3: Implement the minimal settings and model layer**

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    openai_api_key: str = ""
    bing_search_api_key: str = ""
    xhs_cookie: str = ""
    a1: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def bing_enabled(self) -> bool:
        return bool(self.bing_search_api_key)

    @property
    def mcp_enabled(self) -> bool:
        return bool(self.xhs_cookie and self.a1)


class RetrievalUpdateData(BaseModel):
    query: str
    status: str
    strategy: str = ""
    title: str = ""
    message: str = ""
```

Implementation notes:

- Add `pytest` and `pytest-asyncio` to `requirements.txt`.
- Rewrite `models.py` into clean ASCII-safe source with the requested schemas plus explicit SSE payload models.
- Keep `RetrievedRecipe.source_strategy` as a string or enum that serializes cleanly for the frontend.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_settings_and_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt models.py settings.py tests/conftest.py tests/test_settings_and_models.py
git commit -m "refactor: add clean settings and model contracts"
```

## Task 2: Implement Node 1 Planning With OpenAI Fallback

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\planning.py`
- Create: `d:\Appdata\Agent\cook-agent\tests\test_planning.py`
- Modify: `d:\Appdata\Agent\cook-agent\agent.py`

- [ ] **Step 1: Write the failing planning tests**

```python
import pytest

from planning import LocalPlanningService, PlanningService


def test_local_planner_extracts_basic_constraints():
    service = LocalPlanningService()
    result = service.plan("我有3个番茄，2个鸡蛋，晚上吃，2个人，不吃辣")

    assert result.portion_size == 2
    assert "辣" in "".join(result.allergies_and_dislikes)
    assert len(result.search_queries) >= 4
    assert len(result.search_queries) <= 8


@pytest.mark.asyncio
async def test_planning_service_falls_back_without_openai():
    service = PlanningService(openai_client=None)
    result = await service.plan("我有土豆和茄子，想做两菜一汤")

    assert result.global_requests
    assert result.search_queries
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_planning.py -q`

Expected: FAIL because `planning.py` and the service classes do not exist yet.

- [ ] **Step 3: Implement the planning services**

```python
class LocalPlanningService:
    def plan(self, user_input: str) -> UserMenuConstraints:
        ingredients = extract_ingredients(user_input)
        dislikes = extract_dislikes(user_input)
        portion_size = extract_portion_size(user_input)
        global_requests = extract_global_request(user_input)
        search_queries = build_keyword_queries(
            ingredients=ingredients,
            dislikes=dislikes,
            global_requests=global_requests,
        )
        return UserMenuConstraints(
            available_ingredients=ingredients,
            allergies_and_dislikes=dislikes,
            portion_size=portion_size,
            global_requests=global_requests,
            search_queries=search_queries,
        )


class PlanningService:
    async def plan(self, user_input: str) -> UserMenuConstraints:
        if self.openai_client and self.settings.openai_enabled:
            try:
                return await self._plan_with_openai(user_input)
            except Exception:
                pass
        return self.local_service.plan(user_input)
```

Implementation notes:

- Keep the local planner deterministic and easy to test.
- Generate 4 to 8 keyword-style queries, not full sentences.
- Keep OpenAI structured output isolated behind one method so fallback stays simple.
- Do not fully wire orchestration in this task; only import-ready interfaces are needed.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_planning.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add planning.py agent.py tests/test_planning.py
git commit -m "feat: add local-first planning service"
```

## Task 3: Implement Node 2 Retrieval Cascade And Batch Isolation

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\tests\test_retrieval.py`
- Modify: `d:\Appdata\Agent\cook-agent\retrieval.py`

- [ ] **Step 1: Write the failing retrieval tests**

```python
import pytest

from retrieval import FallbackRetriever, RetrievedRecipe


class FailingStrategy:
    name = "MCP"

    async def retrieve(self, query: str):
        return None


class SuccessStrategy:
    name = "Schema"

    async def retrieve(self, query: str):
        return RetrievedRecipe(
            source_query=query,
            source_strategy="Schema",
            title="少油版地三鲜",
            instructions_or_snippet="土豆 茄子 少油快炒",
        )


@pytest.mark.asyncio
async def test_retriever_stops_at_first_success():
    retriever = FallbackRetriever(strategies=[FailingStrategy(), SuccessStrategy()])
    result, meta = await retriever.retrieve_query("土豆 茄子 少油")

    assert result is not None
    assert result.source_strategy == "Schema"
    assert meta["status"] == "success"


@pytest.mark.asyncio
async def test_batch_retrieve_isolates_query_failures():
    retriever = FallbackRetriever(strategies=[FailingStrategy()])
    results, updates = await retriever.batch_retrieve(["query-a", "query-b"])

    assert results == []
    assert len(updates) == 2
    assert all(item["status"] == "fail" for item in updates)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_retrieval.py -q`

Expected: FAIL because the current retriever does not expose `retrieve_query()` metadata in the tested shape.

- [ ] **Step 3: Implement the cascade and query-level status metadata**

```python
class FallbackRetriever:
    def __init__(self, strategies=None):
        self.strategies = strategies or [
            MCPRetrievalStrategy(),
            SchemaExtractionStrategy(),
            BingSearchStrategy(),
            PlaywrightStrategy(),
        ]

    async def retrieve_query(self, query: str) -> tuple[RetrievedRecipe | None, dict]:
        for strategy in self.strategies:
            result = await strategy.retrieve(query)
            if result is not None:
                return result, {
                    "query": query,
                    "status": "success",
                    "strategy": result.source_strategy,
                    "title": result.title,
                    "message": "strategy hit",
                }
        return None, {
            "query": query,
            "status": "fail",
            "strategy": "",
            "title": "",
            "message": "all strategies exhausted",
        }
```

Implementation notes:

- Preserve the cascade order `MCP -> Schema -> Bing -> Playwright`.
- `SchemaExtractionStrategy` must parse only JSON-LD recipe schema data.
- `BingSearchStrategy` must use title + snippet only, with `site:xiaohongshu.com` appended to the query.
- `PlaywrightStrategy` must include random delay and captcha fuse logic.
- `batch_retrieve()` should return both successful recipes and a per-query update list that the agent can stream immediately.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_retrieval.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retrieval.py tests/test_retrieval.py
git commit -m "feat: implement query-level retrieval cascade"
```

## Task 4: Implement Node 3 Local Generation And Streaming Fallback

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\generation.py`
- Create: `d:\Appdata\Agent\cook-agent\tests\test_generation.py`

- [ ] **Step 1: Write the failing generation tests**

```python
import pytest

from generation import LocalMealPlanService, MealGenerationService
from models import IngredientItem, UserMenuConstraints


def test_local_generation_starts_with_accounting_summary():
    service = LocalMealPlanService()
    constraints = UserMenuConstraints(
        available_ingredients=[IngredientItem(name="土豆", quantity="5个")],
        allergies_and_dislikes=[],
        portion_size=2,
        global_requests="两菜一汤",
        search_queries=["土豆 做法 少油"],
    )

    markdown = service.compose_markdown(constraints, [])

    assert "总厨算账总结" in markdown


@pytest.mark.asyncio
async def test_generation_service_falls_back_to_local_chunks():
    service = MealGenerationService(openai_client=None)
    constraints = UserMenuConstraints(
        available_ingredients=[IngredientItem(name="鸡蛋", quantity="4个")],
        allergies_and_dislikes=[],
        portion_size=2,
        global_requests="两道快手菜",
        search_queries=["鸡蛋 快手菜"],
    )

    chunks = [chunk async for chunk in service.stream(constraints, [])]

    assert "".join(chunks).startswith("###")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_generation.py -q`

Expected: FAIL because `generation.py` and its service classes do not exist yet.

- [ ] **Step 3: Implement the generation services**

```python
class LocalMealPlanService:
    def compose_markdown(self, constraints, retrieved_recipes) -> str:
        allocation = self.allocate_inventory(constraints)
        summary = self.build_summary(constraints, allocation)
        dishes = self.build_dishes(constraints, allocation, retrieved_recipes)
        return "\n\n".join([summary, *dishes])

    async def stream(self, constraints, retrieved_recipes):
        text = self.compose_markdown(constraints, retrieved_recipes)
        for chunk in chunk_text(text, size=60):
            yield chunk


class MealGenerationService:
    async def stream(self, constraints, retrieved_recipes):
        if self.openai_client and self.settings.openai_enabled:
            try:
                async for chunk in self._stream_with_openai(constraints, retrieved_recipes):
                    yield chunk
                return
            except Exception:
                pass
        async for chunk in self.local_service.stream(constraints, retrieved_recipes):
            yield chunk
```

Implementation notes:

- Keep a deterministic inventory-allocation helper so inventory safety is testable without parsing markdown.
- The first section of the markdown must be the chef accounting summary.
- Filter out retrieved inspirations that conflict with dislikes before composing dishes.
- Use chunking in fallback mode so the frontend still shows a typing effect.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_generation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add generation.py tests/test_generation.py
git commit -m "feat: add local-stable meal generation"
```

## Task 5: Wire Agent Orchestration And FastAPI SSE

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\tests\test_api.py`
- Modify: `d:\Appdata\Agent\cook-agent\agent.py`
- Modify: `d:\Appdata\Agent\cook-agent\main.py`

- [ ] **Step 1: Write the failing API and orchestration tests**

```python
from fastapi.testclient import TestClient

from main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stream_route_emits_expected_event_names(monkeypatch):
    client = TestClient(app)
    response = client.get("/api/v1/stream_meal_plan", params={"user_input": "我有土豆和鸡蛋"})

    assert response.status_code == 200
    body = response.text
    assert "planning_done" in body
    assert "retrieval_update" in body
    assert "recipe_stream" in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_api.py -q`

Expected: FAIL because the current SSE route uses fragile manual streaming behavior and does not emit the new normalized event format.

- [ ] **Step 3: Implement orchestration and SSE transport**

```python
async def process_agent_stream(user_input: str):
    constraints = await planning_service.plan(user_input)
    yield {"event": "planning_done", "data": constraints.model_dump()}

    retrieved_recipes, updates = await retriever.batch_retrieve(constraints.search_queries)
    for update in updates:
        yield {"event": "retrieval_update", "data": update}

    async for chunk in generation_service.stream(constraints, retrieved_recipes):
        yield {"event": "recipe_stream", "data": {"chunk": chunk}}

    yield {"event": "recipe_done", "data": {"status": "complete"}}


@app.get("/api/v1/stream_meal_plan")
async def stream_meal_plan(user_input: str):
    async def event_publisher():
        async for event in process_agent_stream(user_input):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_publisher())
```

Implementation notes:

- Use `EventSourceResponse` from `sse-starlette`.
- Do not buffer all retrieval updates and emit them at the end; emit them in query-completion order.
- Keep `recipe_done` small and serializable.
- Keep `/health` as the readiness probe used by the launchers.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent.py main.py tests/test_api.py
git commit -m "feat: wire stable SSE orchestration"
```

## Task 6: Implement Streamlit SSE Client And Frontend UI

**Files:**
- Create: `d:\Appdata\Agent\cook-agent\stream_client.py`
- Create: `d:\Appdata\Agent\cook-agent\tests\test_stream_client.py`
- Modify: `d:\Appdata\Agent\cook-agent\app.py`

- [ ] **Step 1: Write the failing SSE client/parser test**

```python
from stream_client import parse_sse_lines


def test_parse_sse_lines_returns_structured_events():
    lines = [
        'event: planning_done',
        'data: {"portion_size": 2}',
        "",
    ]

    events = list(parse_sse_lines(lines))

    assert events[0]["event"] == "planning_done"
    assert events[0]["data"]["portion_size"] == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_stream_client.py -q`

Expected: FAIL because `stream_client.py` does not exist yet.

- [ ] **Step 3: Implement the SSE client helper and connect it to Streamlit**

```python
def parse_sse_lines(lines):
    event_name = "message"
    data_lines = []
    for raw_line in lines:
        if raw_line.startswith("event:"):
            event_name = raw_line.split(":", 1)[1].strip()
        elif raw_line.startswith("data:"):
            data_lines.append(raw_line.split(":", 1)[1].strip())
        elif raw_line == "":
            if data_lines:
                yield {"event": event_name, "data": json.loads("".join(data_lines))}
            event_name = "message"
            data_lines = []
```

Implementation notes:

- In `app.py`, keep three visible areas:
  - Node 1 planning status
  - Node 2 retrieval status
  - Node 3 streamed markdown
- Use `st.session_state` to preserve history and the latest generated result.
- Feed only recipe chunks into `st.write_stream()`.
- Show user-facing connection guidance on backend errors instead of tracebacks.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_stream_client.py -q`

Expected: PASS.

- [ ] **Step 5: Manual frontend check**

Run:

```bash
python main.py
streamlit run app.py
```

Expected:

- the page opens
- the status panels render
- submitting text starts a live request instead of blocking on a full response

- [ ] **Step 6: Commit**

```bash
git add stream_client.py app.py tests/test_stream_client.py
git commit -m "feat: add streamlit streaming client"
```

## Task 7: Harden Launchers, Configuration Docs, And Smoke Verification

**Files:**
- Modify: `d:\Appdata\Agent\cook-agent\.env.example`
- Modify: `d:\Appdata\Agent\cook-agent\README.md`
- Modify: `d:\Appdata\Agent\cook-agent\start.bat`
- Modify: `d:\Appdata\Agent\cook-agent\start.sh`

- [ ] **Step 1: Write the failing smoke-style verification**

```python
from fastapi.testclient import TestClient

from main import app


def test_stream_route_works_without_optional_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BING_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("XHS_COOKIE", raising=False)
    monkeypatch.delenv("A1", raising=False)

    client = TestClient(app)
    response = client.get("/api/v1/stream_meal_plan", params={"user_input": "我有鸡蛋和番茄"})

    assert response.status_code == 200
    assert "planning_done" in response.text
```

- [ ] **Step 2: Run the focused smoke test to verify it fails or is incomplete**

Run: `pytest tests/test_api.py::test_stream_route_works_without_optional_credentials -q`

Expected: FAIL until the local-fallback path is fully wired and the launcher assumptions are cleaned up.

- [ ] **Step 3: Update launchers and docs**

```text
Windows launcher:
- create venv if missing
- install dependencies
- copy .env.example to .env if missing
- start backend in a separate process
- poll http://localhost:8000/health until success or timeout
- launch Streamlit

README:
- describe local no-credential mode first
- explain optional enhancements second
- list the exact environment variables for OpenAI, Bing, and MCP
```

Implementation notes:

- Keep `.env.example` explicit about `XHS_COOKIE` and `A1` for MCP.
- Do not make startup depend on optional credentials.
- Prefer readiness polling over fixed sleeps in both launchers.

- [ ] **Step 4: Run the focused smoke test again**

Run: `pytest tests/test_api.py::test_stream_route_works_without_optional_credentials -q`

Expected: PASS.

- [ ] **Step 5: Run the full verification suite**

Run:

```bash
pytest tests -q
python -m py_compile main.py app.py agent.py models.py retrieval.py planning.py generation.py settings.py stream_client.py
```

Expected:

- all targeted tests pass
- no syntax errors

- [ ] **Step 6: Commit**

```bash
git add .env.example README.md start.bat start.sh tests/test_api.py
git commit -m "chore: harden startup flow and docs"
```

## Manual Verification Checklist

- [ ] Run `python main.py` and confirm `http://localhost:8000/health` returns `{"status":"ok","service":"meal-plan-agent"}`.
- [ ] Run `streamlit run app.py` and confirm the page loads locally.
- [ ] Submit a request with no optional credentials configured and confirm:
  - planning status completes
  - retrieval status updates per query
  - recipe text streams progressively
- [ ] Add `OPENAI_API_KEY` and confirm planning and generation still work.
- [ ] Add `BING_SEARCH_API_KEY` and confirm Bing becomes active in the retrieval cascade.
- [ ] Add `XHS_COOKIE` and `A1` and confirm MCP becomes active without breaking local fallback behavior.

## Notes For Execution

- Rewrite source files into clean UTF-8 or ASCII-safe content as needed; the current repository contains multiple files with likely encoding damage.
- Keep the public route name `GET /api/v1/stream_meal_plan`.
- Preserve the one-click launcher experience while replacing fixed startup sleeps with health checks.
- Do not revert unrelated worktree changes, especially the existing `requirements.txt` modification outside this plan's authored changes.
