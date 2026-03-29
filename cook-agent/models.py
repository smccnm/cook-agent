"""
数据模型定义 - 支持 Pydantic v2 结构化输出
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ======================== Node 1: 意图提取与排菜规划模型 ========================

class IngredientItem(BaseModel):
    """食材项目"""
    name: str = Field(description="食材名称，如'番茄'、'五花肉'")
    quantity: str = Field(description="精确数量，如'5个'、'250g'、'半斤'，未说明填'适量'")


class UserMenuConstraints(BaseModel):
    """用户菜单约束与规划"""
    available_ingredients: List[IngredientItem] = Field(
        description="用户可用的食材及数量清单"
    )
    allergies_and_dislikes: List[str] = Field(
        default=[],
        description="绝对忌口食材列表，如['辣', '海鲜', '花生']"
    )
    portion_size: int = Field(
        default=1,
        description="就餐人数"
    )
    flavor_preferences: List[str] = Field(
        default=[],
        description="烹饪偏好，如['减脂', '清淡', '快手菜']"
    )
    global_requests: str = Field(
        description="宏观排菜预期，如'做2菜1汤'、'一荤一素'"
    )
    search_queries: List[str] = Field(
        description="LLM推导的多个搜索关键词，每个是关键词空格组合"
    )


# ======================== Node 2: 统一检索结果模型 ========================

class RetrievalStrategy(str, Enum):
    """检索策略枚举"""
    MCP = "MCP"
    SCHEMA = "Schema"
    BING = "Bing"
    PLAYWRIGHT = "Playwright"


class RetrievedRecipe(BaseModel):
    """单条检索结果"""
    source_query: str = Field(description="搜索词")
    source_strategy: RetrievalStrategy = Field(description="使用的检索策略")
    title: str = Field(description="菜品名称")
    ingredients: List[str] = Field(default=[], description="菜品食材列表")
    instructions_or_snippet: str = Field(description="烹饪步骤或摘要")
    raw_content: Optional[str] = Field(default=None, description="原始爬取内容")


class RetrievalResult(BaseModel):
    """批量检索结果"""
    recipes: List[RetrievedRecipe] = Field(default=[], description="所有检索到的菜谱")
    failed_queries: List[dict] = Field(
        default=[],
        description="失败的查询及原因"
    )


# ======================== Node 3: 菜谱生成模型 ========================

class RecipeInstruction(BaseModel):
    """单道菜的烹饪步骤"""
    step_number: int
    description: str = Field(description="步骤描述")


class SingleRecipe(BaseModel):
    """单道菜"""
    name: str = Field(description="菜名")
    ingredients: List[str] = Field(description="所需食材清单")
    instructions: List[RecipeInstruction] = Field(description="烹饪步骤")


class MealPlan(BaseModel):
    """完整菜单计划"""
    plan_summary: str = Field(description="总厨的库存分配说明与菜单整体规划")
    recipes: List[SingleRecipe] = Field(description="最终生成的菜谱列表")
    inventory_utilization: dict = Field(
        default={},
        description="食材消耗映射，如{'土豆': '3个用于炖汤，2个用于炒菜'}"
    )


# ======================== SSE 流式事件定义 ========================

class SSEEvent(BaseModel):
    """Server-Sent Event 事件"""
    event: str = Field(description="事件类型")
    data: dict = Field(description="事件数据")


class PlanningDoneEvent(SSEEvent):
    """规划完成事件"""
    event: str = "planning_done"
    data: UserMenuConstraints


class RetrievalUpdateEvent(SSEEvent):
    """检索更新事件"""
    event: str = "retrieval_update"
    data: dict = Field(default={})  # {"query": str, "status": "success|fail"}


class RecipeStreamEvent(SSEEvent):
    """菜谱流事件"""
    event: str = "recipe_stream"
    data: dict = Field(default={})  # {"chunk": str}


class RecipeDoneEvent(SSEEvent):
    """菜谱完成事件"""
    event: str = "recipe_done"
    data: MealPlan
