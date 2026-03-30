"""Local-stable meal generation services."""

from __future__ import annotations

import os
from typing import AsyncGenerator

from models import RetrievedRecipe, UserMenuConstraints
from settings import AppSettings


def chunk_text(text: str, size: int = 60) -> list[str]:
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
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "dish": dish_label,
                }
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
            allocation_text = "当前库存未识别到明确主食材，按灵活家常菜方案处理。"

        return (
            "### 👨‍🍳 总厨算账总结\n\n"
            f"为了满足“{constraints.global_requests or '灵活家常餐'}”的需求，"
            f"我先按库存做了保守分配：{allocation_text}"
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
        if allocations:
            primary = allocations[0]
            dishes.append(
                "\n".join(
                    [
                        f"### {primary['name']}家常主菜",
                        "#### 精确用料",
                        f"- {primary['name']}: {primary['quantity']}",
                        "- 盐: 适量",
                        "- 生抽: 适量",
                        "#### 烹饪步骤",
                        f"1. 先处理{primary['name']}，按库存量全部用于主菜准备。",
                        "2. 热锅后先下主料，再用少量基础调味完成主体味型。",
                        f"3. 最后参考灵感微调火候与口味：{inspiration_text}",
                    ]
                )
            )

        if len(allocations) > 1:
            side = allocations[1]
            dishes.append(
                "\n".join(
                    [
                        f"### {side['name']}快手配菜",
                        "#### 精确用料",
                        f"- {side['name']}: {side['quantity']}",
                        "- 食用油: 适量",
                        "#### 烹饪步骤",
                        f"1. 将{side['name']}整理成适合快炒或快拌的状态。",
                        "2. 使用轻调味方式完成，避免与主菜抢味。",
                        "3. 出锅前确认与用户忌口不冲突。",
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
                        "3. 保持调味克制，方便后续扩展成完整套餐。",
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
        self.openai_client = openai_client
        self.settings = settings or AppSettings()
        self.local_service = local_service or LocalMealPlanService()

    async def _stream_with_openai(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> AsyncGenerator[str, None]:
        prompt = self.local_service.compose_markdown(constraints, retrieved_recipes)
        response = await self.openai_client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            messages=[
                {
                    "role": "system",
                    "content": "Rewrite the provided draft meal plan as polished markdown. Keep the first heading unchanged.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        text = response.choices[0].message.content or prompt
        for chunk in chunk_text(text):
            yield chunk

    async def stream(
        self,
        constraints: UserMenuConstraints,
        retrieved_recipes: list[RetrievedRecipe],
    ) -> AsyncGenerator[str, None]:
        if self.openai_client and self.settings.openai_enabled:
            try:
                async for chunk in self._stream_with_openai(constraints, retrieved_recipes):
                    yield chunk
                return
            except Exception:
                pass

        async for chunk in self.local_service.stream(constraints, retrieved_recipes):
            yield chunk
