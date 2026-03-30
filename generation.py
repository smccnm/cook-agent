"""Meal-plan generation with Gemini-first streaming and local fallback."""

from __future__ import annotations

from typing import AsyncGenerator

from google import genai
from google.genai import types

from models import RetrievedRecipe, UserMenuConstraints
from settings import AppSettings

CHEF_SYSTEM_PROMPT = """你是一位拥有严密逻辑和极高厨艺水准的米其林行政总厨，同时也是库存管理大师。

请严格遵守：
1. 绝对不能超发库存。
2. 必须先做“总厨算账总结”，解释食材如何分配。
3. 必须剔除参考灵感里与忌口冲突的内容。
4. 输出必须是 Markdown，不要输出 JSON。
5. 第一段标题必须为：### 👨‍🍳 总厨算账总结
6. 后续每道菜都使用：
   - `### 菜名`
   - `#### 精确用料`
   - `#### 烹饪步骤`
"""


def chunk_text(text: str, size: int = 80) -> list[str]:
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


class LocalMealPlanService:
    def filter_inspirations(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> list[RetrievedRecipe]:
        dislikes = [item for item in constraints.allergies_and_dislikes if item]
        if not dislikes:
            return retrieved_recipes

        filtered: list[RetrievedRecipe] = []
        for recipe in retrieved_recipes:
            haystack = " ".join(
                [recipe.title, recipe.instructions_or_snippet, *recipe.ingredients]
            )
            if any(dislike in haystack for dislike in dislikes):
                continue
            filtered.append(recipe)
        return filtered

    def allocate_inventory(self, constraints: UserMenuConstraints) -> list[dict[str, str]]:
        allocations: list[dict[str, str]] = []
        for index, item in enumerate(constraints.available_ingredients, start=1):
            dish_label = "主菜" if index == 1 else f"配菜{index - 1}"
            allocations.append(
                {"name": item.name, "quantity": item.quantity, "dish": dish_label}
            )
        return allocations

    def build_summary(
        self, constraints: UserMenuConstraints, allocations: list[dict[str, str]]
    ) -> str:
        if allocations:
            allocation_text = "；".join(
                f"{item['quantity']}{item['name']}用于{item['dish']}" for item in allocations
            )
        else:
            allocation_text = "当前库存未识别到明确主食材，按灵活家常餐方案处理。"

        return (
            "### 👨‍🍳 总厨算账总结\n\n"
            f"为了满足“{constraints.global_requests or '灵活家常餐'}”的需求，"
            f"我先按库存做了保守分配：{allocation_text}。"
        )

    def build_dishes(
        self,
        constraints: UserMenuConstraints,
        allocations: list[dict[str, str]],
        retrieved_recipes: list[RetrievedRecipe],
    ) -> list[str]:
        inspirations = self.filter_inspirations(constraints, retrieved_recipes)
        inspiration_text = (
            inspirations[0].instructions_or_snippet
            if inspirations
            else "按清晰、快手、少浪费的家常逻辑执行。"
        )

        dishes: list[str] = []
        for item in allocations[:2]:
            dishes.append(
                "\n".join(
                    [
                        f"### {item['name']}家常菜",
                        "#### 精确用料",
                        f"- {item['name']}: {item['quantity']}",
                        "- 盐: 适量",
                        "- 生抽: 适量",
                        "#### 烹饪步骤",
                        f"1. 先处理{item['name']}，按库存量完成切配。",
                        "2. 热锅后下主料，用基础调味建立主体味型。",
                        f"3. 参考灵感微调火候与调味：{inspiration_text}",
                    ]
                )
            )

        if not dishes:
            dishes.append(
                "\n".join(
                    [
                        "### 灵活家常菜",
                        "#### 精确用料",
                        "- 现有库存: 适量",
                        "#### 烹饪步骤",
                        "1. 优先使用最容易浪费的食材。",
                        "2. 采用一锅或一盘完成的快手做法。",
                        "3. 保持调味克制并避开用户忌口。",
                    ]
                )
            )

        return dishes

    def compose_markdown(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> str:
        allocations = self.allocate_inventory(constraints)
        summary = self.build_summary(constraints, allocations)
        dishes = self.build_dishes(constraints, allocations, retrieved_recipes)
        return "\n\n".join([summary, *dishes])

    async def stream(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> AsyncGenerator[str, None]:
        text = self.compose_markdown(constraints, retrieved_recipes)
        for chunk in chunk_text(text):
            yield chunk


class MealGenerationService:
    def __init__(
        self,
        openai_client=None,
        settings: AppSettings | None = None,
        local_service: LocalMealPlanService | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.local_service = local_service or LocalMealPlanService()
        self.google_client = (
            genai.Client(api_key=self.settings.gemini_api_key)
            if self.settings.gemini_enabled
            else None
        )
        self.openai_client = openai_client

    async def _stream_with_gemini(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> AsyncGenerator[str, None]:
        prompt = (
            f"库存：{[item.model_dump() for item in constraints.available_ingredients]}\n"
            f"人数：{constraints.portion_size}\n"
            f"全局需求：{constraints.global_requests}\n"
            f"忌口：{constraints.allergies_and_dislikes}\n"
            f"参考灵感：{[item.model_dump() for item in retrieved_recipes[:6]]}\n"
        )

        stream = await self.google_client.aio.models.generate_content_stream(
            model=self.settings.gemini_generation_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=CHEF_SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def stream(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> AsyncGenerator[str, None]:
        if self.google_client is not None:
            try:
                async for chunk in self._stream_with_gemini(constraints, retrieved_recipes):
                    yield chunk
                return
            except Exception:
                pass

        async for chunk in self.local_service.stream(constraints, retrieved_recipes):
            yield chunk
