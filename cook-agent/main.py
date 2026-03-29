"""FastAPI entrypoint for the streaming meal-plan backend."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from sse_starlette import EventSourceResponse

from agent import process_agent_stream

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("cook-agent backend starting")
    yield
    logger.info("cook-agent backend stopping")


app = FastAPI(
    title="Cook Agent API",
    description="Streaming meal-plan backend",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def cors_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meal-plan-agent"}


@app.get("/api/v1/stream_meal_plan")
async def stream_meal_plan(
    user_input: str = Query(..., description="Unstructured meal-planning input")
):
    async def event_publisher():
        async for event in process_agent_stream(user_input):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_publisher())


@app.post("/api/v1/stream_meal_plan")
async def stream_meal_plan_post(request_data: dict):
    user_input = request_data.get("user_input")
    if not user_input:
        return {"error": "user_input is required"}
    return await stream_meal_plan(user_input)


@app.get("/")
async def root():
    return {
        "message": "Cook Agent API ready",
        "docs": "/docs",
        "api": "/api/v1/stream_meal_plan",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", 8000)),
        log_level=os.getenv("BACKEND_LOG_LEVEL", "info"),
        reload=True,
    )
