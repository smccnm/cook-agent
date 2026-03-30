from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IngredientItem(BaseModel):
    name: str = Field(description="Ingredient name")
    quantity: str = Field(description="User-provided quantity text")


class UserMenuConstraints(BaseModel):
    available_ingredients: list[IngredientItem] = Field(default_factory=list)
    allergies_and_dislikes: list[str] = Field(default_factory=list)
    portion_size: int = 1
    flavor_preferences: list[str] = Field(default_factory=list)
    global_requests: str = ""
    search_queries: list[str] = Field(default_factory=list)


class RetrievalStrategy(str, Enum):
    MCP = "MCP"
    SCHEMA = "Schema"
    BING = "Bing"
    PLAYWRIGHT = "Playwright"


class RetrievedRecipe(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source_query: str
    source_strategy: RetrievalStrategy = RetrievalStrategy.SCHEMA
    title: str = ""
    ingredients: list[str] = Field(default_factory=list)
    instructions_or_snippet: str = ""
    raw_content: str | None = None


class RetrievalResult(BaseModel):
    recipes: list[RetrievedRecipe] = Field(default_factory=list)
    failed_queries: list[dict[str, Any]] = Field(default_factory=list)


class RecipeInstruction(BaseModel):
    step_number: int
    description: str


class SingleRecipe(BaseModel):
    name: str
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[RecipeInstruction] = Field(default_factory=list)


class MealPlan(BaseModel):
    plan_summary: str
    recipes: list[SingleRecipe] = Field(default_factory=list)
    inventory_utilization: dict[str, str] = Field(default_factory=dict)


class PlanningDoneData(BaseModel):
    constraints: UserMenuConstraints


class RetrievalUpdateData(BaseModel):
    query: str
    status: str
    strategy: str = ""
    title: str = ""
    message: str = ""


class RecipeStreamData(BaseModel):
    chunk: str


class ErrorData(BaseModel):
    message: str


class SSEEvent(BaseModel):
    event: str
    data: Any


class PlanningDoneEvent(SSEEvent):
    event: Literal["planning_done"] = "planning_done"
    data: UserMenuConstraints


class RetrievalUpdateEvent(SSEEvent):
    event: Literal["retrieval_update"] = "retrieval_update"
    data: RetrievalUpdateData


class RecipeStreamEvent(SSEEvent):
    event: Literal["recipe_stream"] = "recipe_stream"
    data: RecipeStreamData


class RecipeDoneEvent(SSEEvent):
    event: Literal["recipe_done"] = "recipe_done"
    data: MealPlan


class ErrorEvent(SSEEvent):
    event: Literal["error"] = "error"
    data: ErrorData
