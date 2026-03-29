# Cook Agent Local-Stable Streaming Design

## Overview

This design defines the "local-stable" edition of the cook-agent project: a FastAPI + Streamlit meal-planning agent that always delivers a complete three-stage experience on a local machine, even when optional external credentials are missing.

The system accepts highly unstructured Chinese natural-language input about available ingredients, quantities, meal expectations, and dislikes. It then:

1. Extracts a structured planning model.
2. Runs concurrent multi-query retrieval with a four-step fallback cascade.
3. Streams a final meal plan back to the user with progressive UI feedback.

The defining constraint for this edition is resilience. Missing `OPENAI_API_KEY`, `BING_SEARCH_API_KEY`, `XHS_COOKIE`, or `A1` must never make the application unusable. Instead, the system must transparently degrade while preserving the same three-stage product experience.

## Goals

- Preserve the existing top-level entrypoints: `start.bat`, `start.sh`, `main.py`, and `app.py`.
- Deliver a complete local demo flow with no required external credentials.
- Keep the backend on FastAPI with SSE output for progressive updates.
- Keep the frontend on Streamlit with visible stage progress and streaming recipe output.
- Implement Node 2 as a real cascade in this order: `MCP -> Schema -> Bing -> Playwright`.
- Ensure Node 1 and Node 3 can fall back to deterministic local logic when OpenAI is unavailable.
- Enforce inventory-aware output that never over-allocates ingredients.

## Non-Goals

- Building a production-grade persistence layer.
- Implementing user accounts, saved sessions, or multi-user state.
- Guaranteeing real-world correctness of external websites or anti-bot evasion.
- Requiring all external integrations to be active in the default local workflow.

## Scope Summary

The current repository already contains the expected files, but the present implementation has several risks for the requested "definitive" behavior:

- mismatched SDK usage patterns in the OpenAI layer
- fragile or incomplete SSE generation
- inconsistent fallback behavior across retrieval stages
- likely encoding and readability issues in several source files
- startup scripts that do not robustly verify backend readiness before launching the frontend

This design keeps the current file-level entrypoints but re-establishes clean responsibilities so the system is stable to run and straightforward to evolve.

## Architecture

### High-Level Component Boundaries

- `settings.py`
  - Centralizes environment loading and capability flags.
  - Exposes whether OpenAI, Bing, MCP prerequisites, and Playwright support are available.

- `models.py`
  - Contains all Pydantic v2 data contracts.
  - Defines Node 1, Node 2, Node 3, and SSE payload models.

- `retrieval.py`
  - Owns the Node 2 fallback cascade and concurrent query retrieval.
  - Converts every strategy result into a unified `RetrievedRecipe`.

- `agent.py`
  - Owns three-stage orchestration.
  - Emits stage results as async events in real time.

- `main.py`
  - Owns FastAPI application setup and SSE route exposure.
  - Uses `EventSourceResponse` from `sse-starlette`.

- `app.py`
  - Owns Streamlit presentation.
  - Shows planning status, retrieval status, and streamed meal-plan output.

- `start.bat` / `start.sh`
  - Own local startup flow.
  - Ensure environment setup and backend readiness checks before frontend launch.

### Design Principle

Each file should answer one clear question:

- What is the data shape?
- How do we retrieve data?
- How do we orchestrate the workflow?
- How do we expose the API?
- How do we present the interaction?

That separation keeps the retrieval cascade testable, the fallback logic predictable, and the streaming UI independent from backend internals.

## Data Contracts

The implementation must keep the requested core schemas and validate everything through Pydantic v2.

### Node 1

- `IngredientItem`
  - `name: str`
  - `quantity: str`

- `UserMenuConstraints`
  - `available_ingredients: list[IngredientItem]`
  - `allergies_and_dislikes: list[str]`
  - `portion_size: int`
  - `global_requests: str`
  - `search_queries: list[str]`

Optional internal helpers may exist, but the externally exposed planning payload should stay aligned with the requested schema.

### Node 2

- `RetrievedRecipe`
  - `source_query: str`
  - `source_strategy: str`
  - `title: str`
  - `instructions_or_snippet: str`

Internal metadata may be added for UI use, but those four fields are required.

### SSE Events

The backend should emit these event types:

- `planning_done`
- `retrieval_update`
- `recipe_stream`
- `recipe_done`
- `error`

For local stability, `retrieval_update` should include richer status details:

- `query`
- `status`
- `strategy`
- `title`
- `message`

This keeps the frontend informative without depending on backend logs.

## End-to-End Flow

### Stage 1: Planning Extraction

Node 1 receives the raw user request and produces a validated `UserMenuConstraints`.

#### Primary path

If `OPENAI_API_KEY` is present:

- call OpenAI with a planning system prompt
- request structured output aligned to `UserMenuConstraints`
- validate the response with Pydantic

#### Fallback path

If the key is missing, the request fails, or validation fails:

- run a deterministic local planner
- extract rough ingredients, quantities, dislikes, portion size, and global meal intent
- generate 4 to 8 keyword-style search queries

#### Fallback quality bar

The local planner does not need full language intelligence, but it must:

- produce valid JSON-compatible structured data
- preserve the three-stage UX
- never return an empty `search_queries` list for ordinary cooking requests

After Node 1 completes, the agent must immediately emit `planning_done`.

### Stage 2: Concurrent Retrieval

Node 2 receives `search_queries` and launches concurrent retrieval for each query using `asyncio.gather`.

Each query is processed independently through the same cascade:

1. MCP
2. Schema extraction
3. Bing summary lookup
4. Playwright fallback

Failure in one query must not cancel or poison the others.

The agent should emit `retrieval_update` as each query finishes instead of waiting for the entire batch.

### Stage 3: Meal Plan Generation

Node 3 consumes the validated planning model and the retrieved recipe inspirations, then generates final Markdown output.

#### Primary path

If `OPENAI_API_KEY` is present:

- stream completion tokens from OpenAI
- convert each text chunk into `recipe_stream`

#### Fallback path

If the key is missing or generation fails:

- use a deterministic local meal-plan composer
- still emit chunked output progressively

#### Hard constraints

- never exceed available inventory
- remove inspiration content that conflicts with dislikes or allergies
- start with a "total allocation / chef accounting" summary
- reflect macro meal structure from `global_requests` whenever possible

When generation completes, the backend should emit `recipe_done`.

## Retrieval Cascade Design

### Strategy 1: MCP

This is the preferred strategy, but only when prerequisites exist.

#### Enablement rule

MCP is enabled only if both are configured:

- `XHS_COOKIE`
- `A1`

If either is missing, the strategy is considered unavailable and the cascade immediately falls through to the next strategy.

#### Contract

- connect to the local `xiaohongshu-mcp` service through the official MCP client path used by this project
- call the `search_notes` tool
- normalize the result into `RetrievedRecipe`

#### Local-stable expectation

If MCP is not configured, the application must still be fully usable.

### Strategy 2: Schema Extraction

This is the main no-credential fallback and should be the most reliable real retrieval layer in local mode.

#### Source order

1. `xiachufang.com`
2. `meishij.net`
3. `douguo.com`

#### Parsing rules

- fetch HTML with `httpx`
- parse only `<script type="application/ld+json">`
- use `json.loads()` to read schema data
- extract `recipeIngredient` and `recipeInstructions`
- do not depend on CSS class traversal for the recipe body

This rule is important for robustness across site layout changes.

### Strategy 3: Bing Summary Lookup

This strategy is enabled only when `BING_SEARCH_API_KEY` is configured.

#### Query shaping

Append `site:xiaohongshu.com` to the query.

#### Data usage rule

Only use the search API JSON result fields:

- `title`
- `snippet`

Do not make a follow-up request to the returned target page.

### Strategy 4: Playwright Fallback

This is a special-case escape hatch, not the normal path.

#### Required behavior

- launch a browser with a randomized user agent
- inject a stealth script
- sleep for a random duration between page actions with `await asyncio.sleep(random.uniform(1.5, 4.3))`

#### Captcha fuse

After relevant page changes, the strategy must check for captcha indicators such as:

- `secsdk-captcha`
- `verify-bar`

If found, it must raise a dedicated `CaptchaDetectedError` and stop that retrieval path immediately. It must never attempt slider interaction.

## Error Handling

### Global philosophy

The system should degrade, not collapse.

### Per-stage policy

- Node 1 failure
  - If OpenAI fails, switch to local planner.
  - If the local planner fails, emit an `error` event and end the request.

- Node 2 failure
  - Treat each query independently.
  - Emit a failed `retrieval_update` for that query.
  - Continue with remaining queries.

- Node 3 failure
  - If OpenAI streaming fails before output starts, switch to local composer.
  - If streaming fails mid-response, emit an explanatory fallback chunk or terminal `error` event depending on what is still recoverable.

### Startup failures

Missing `.env` should never block startup completely. The launcher should copy `.env.example` to `.env`, explain which features are optional, and continue.

## SSE API Design

### Route

The backend must expose:

- `GET /api/v1/stream_meal_plan`

The request accepts:

- `user_input: str`

### Response model

The response is a `text/event-stream` SSE stream delivered via `EventSourceResponse`.

### Event ordering

Normal successful request order:

1. `planning_done`
2. one or more `retrieval_update`
3. many `recipe_stream`
4. `recipe_done`

Error requests should emit `error` with enough message detail for the frontend to display a useful explanation.

## Streamlit UX Design

### Layout

The Streamlit frontend should present a focused chat-style interface with:

- title and short explanation
- natural-language input area
- submit action
- streamed response area
- collapsible status panels for Node 1 and Node 2

### Status behavior

- Node 1 panel shows the structured plan JSON after `planning_done`.
- Node 2 panel appends query-by-query statuses as `retrieval_update` arrives.
- Node 3 area uses `st.write_stream()` to render `recipe_stream` chunks as a typing experience.

### Session behavior

Use `st.session_state` to preserve conversation history and the latest generated meal plan across reruns.

### Failure behavior

If the backend is unreachable or times out, show user-facing guidance rather than raw tracebacks.

## Configuration Design

The repository should include a clear `.env.example` that documents:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `BING_SEARCH_API_KEY`
- `XHS_COOKIE`
- `A1`
- backend host and port
- frontend/backend URL settings
- optional logging controls

The documentation must explain that only the base Python environment is required for the local-stable demo mode.

## Startup Flow

The launcher scripts should implement this sequence:

1. create virtual environment if missing
2. activate it
3. install dependencies if needed
4. create `.env` from `.env.example` if missing
5. start the FastAPI backend
6. wait for a healthy backend response
7. launch Streamlit

The backend readiness check is important because it removes race conditions where the frontend opens before the API is accepting connections.

## Testing Strategy

The first implementation should focus on a compact, high-value test set.

### Priority tests

- local Node 1 planner returns valid `UserMenuConstraints`
- search query generation yields 4 to 8 keyword-style queries
- retrieval cascade respects the MCP -> Schema -> Bing -> Playwright order
- one failed query does not fail the entire batch
- local Node 3 generator produces a chef accounting summary
- local Node 3 generator does not over-allocate known inventory
- SSE endpoint emits expected event types in order for a normal local run

### Verification targets

- unit-level verification for planners and retrieval strategies
- lightweight endpoint verification for the SSE route
- one end-to-end local smoke check

## Acceptance Criteria

The work is successful when the following are true:

### Local no-credential mode

- `start.bat` or `start.sh` successfully launches the app locally
- FastAPI health check responds
- Streamlit opens successfully
- a user can submit natural-language input and receive all three visible stages
- the final result is a readable Markdown meal plan

### OpenAI-enhanced mode

- with `OPENAI_API_KEY`, Node 1 uses structured LLM extraction
- with `OPENAI_API_KEY`, Node 3 streams LLM-generated Markdown

### Expanded retrieval mode

- with `BING_SEARCH_API_KEY`, Bing becomes active in the cascade
- with `XHS_COOKIE` and `A1`, MCP becomes active in the cascade
- missing optional credentials never breaks the rest of the application

## Risks And Mitigations

### Risk: External services are unavailable

Mitigation:

- make all external integrations optional
- maintain deterministic local fallback paths

### Risk: Recipe websites change structure

Mitigation:

- rely on JSON-LD schema extraction before any DOM-specific fallback

### Risk: Stream interruption creates a poor UX

Mitigation:

- emit stage-level progress early
- stream query completion incrementally
- provide user-readable error events

### Risk: Inventory accounting drifts in LLM mode

Mitigation:

- validate structured inputs before generation
- explicitly include inventory accounting rules in prompts
- keep a deterministic local generator available as a fallback and reference behavior

## Implementation Readiness

This design is ready to transition into an implementation plan. The next artifact should decompose the work into small tasks that:

- preserve current entrypoints
- rebuild the core orchestration around reliable fallbacks
- add focused verification for local-stable behavior
