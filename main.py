"""FastAPI entrypoint for the streaming meal-plan backend."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from sse_starlette import EventSourceResponse

from agent import process_agent_stream
from settings import AppSettings
from xhs_service import XHSServiceManager

load_dotenv()

settings = AppSettings()
xhs_manager = XHSServiceManager(settings)

logging.basicConfig(
    level=settings.backend_log_level.upper(),
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


@app.post("/api/v1/xhs/login/start")
async def xhs_login_start():
    result = xhs_manager.start_login()
    return {"success": True, "data": result}


@app.get("/api/v1/xhs/login/status")
async def xhs_login_status():
    return {"success": True, "data": xhs_manager.login_status()}


@app.post("/api/v1/xhs/mcp/start")
async def xhs_mcp_start():
    base_url = xhs_manager.ensure_mcp_server()
    return {"success": True, "data": {"base_url": base_url}}


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
        host=settings.backend_host,
        port=settings.backend_port,
        log_level=settings.backend_log_level,
        reload=True,
    )
