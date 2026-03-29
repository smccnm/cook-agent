"""
FastAPI 后端服务 - SSE 长链接支持
"""
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from agent import process_agent_stream

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ======================== 生命周期管理 ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭事件
    """
    logger.info("🚀 美食排菜 Agent 后端启动...")
    yield
    logger.info("🛑 后端关闭")


app = FastAPI(
    title="美食排菜 Agent API",
    description="全局资源分配的美食 Agent 后端服务",
    version="1.0.0",
    lifespan=lifespan,
)


# ======================== 中间件 ========================

@app.middleware("http")
async def cors_middleware(request, call_next):
    """CORS 中间件"""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ======================== 路由 ========================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "meal-plan-agent"}


def event_generator(user_input: str):
    """
    生成 SSE 事件流
    """
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def generate():
            async for event in process_agent_stream(user_input):
                # 转换为 SSE 格式
                json_data = json.dumps(event, ensure_ascii=False)
                yield f"data: {json_data}\n\n"
        
        yield from loop.run_until_complete(generate())
    except Exception as e:
        logger.error(f"事件生成失败: {e}")
        error_event = json.dumps(
            {"event": "error", "data": {"message": str(e)}},
            ensure_ascii=False,
        )
        yield f"data: {error_event}\n\n"


@app.get("/api/v1/stream_meal_plan")
async def stream_meal_plan(
    user_input: str = Query(..., description="用户输入的自然语言需求")
):
    """
    流式菜单规划 API
    
    使用 Server-Sent Events (SSE) 推送实时更新。
    
    事件类型：
    - planning_done: 规划提取完成，返回 UserMenuConstraints
    - retrieval_update: 检索状态更新，返回 {"query": str, "status": "success|fail"}
    - recipe_stream: 菜谱生成流，返回 {"chunk": str}
    - error: 错误事件，返回 {"message": str}
    
    Example:
        curl "http://localhost:8000/api/v1/stream_meal_plan?user_input=我有5个土豆和半斤五花肉"
    """
    logger.info(f"📨 收到请求: {user_input[:100]}")
    
    return StreamingResponse(
        event_generator(user_input),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/stream_meal_plan")
async def stream_meal_plan_post(request_data: dict):
    """
    POST 版本的流式菜单规划 API
    """
    user_input = request_data.get("user_input")
    if not user_input:
        return {"error": "user_input 字段必须"}
    
    return await stream_meal_plan(user_input)


# ======================== 静态健康路由 ========================

@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "美食排菜 Agent API 已就绪",
        "docs": "/docs",
        "api": "/api/v1/stream_meal_plan",
    }


# ======================== 启动脚本 ========================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    log_level = os.getenv("BACKEND_LOG_LEVEL", "info")

    logger.info(f"启动服务器: {host}:{port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=True,
    )
