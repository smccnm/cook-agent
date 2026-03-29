"""Agent orchestration compatibility layer.

This file keeps the current public function names stable while later tasks
move planning, generation, and streaming responsibilities into dedicated
modules.
"""

import json
import logging
import os
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from models import RetrievedRecipe, UserMenuConstraints
from planning import PlanningService
from retrieval import CaptchaDetectedError, retrieve_recipes

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
planning_service = PlanningService(openai_client=client)


def _chunk_text(text: str, chunk_size: int = 120) -> list[str]:
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _local_meal_plan_markdown(
    constraints: UserMenuConstraints,
    retrieved_recipes: list[RetrievedRecipe],
) -> str:
    ingredients = ", ".join(
        f"{item.name} {item.quantity}" for item in constraints.available_ingredients
    ) or "available pantry items"
    dislikes = ", ".join(constraints.allergies_and_dislikes) or "none"
    inspiration = ", ".join(recipe.title for recipe in retrieved_recipes[:3] if recipe.title)
    inspiration_line = inspiration or "current retrieval hints"

    return (
        "### Chef Allocation Summary\n\n"
        f"- Inventory: {ingredients}\n"
        f"- Portions: {constraints.portion_size}\n"
        f"- Global request: {constraints.global_requests or 'flexible home meal'}\n"
        f"- Avoid: {dislikes}\n"
        f"- Inspiration: {inspiration_line}\n\n"
        "### Draft Menu\n\n"
        "#### Ingredients\n"
        f"- {ingredients}\n\n"
        "#### Steps\n"
        "1. Review the available ingredients and reserve enough for every dish.\n"
        "2. Start with the quickest dish and reuse overlapping prep.\n"
        "3. Adjust seasoning to match the user's dislikes and preferences.\n"
    )


async def _generate_markdown(
    constraints: UserMenuConstraints,
    retrieved_recipes: list[RetrievedRecipe],
) -> str:
    if os.getenv("OPENAI_API_KEY", "").strip():
        prompt = (
            "Create a markdown meal plan that starts with '### Chef Allocation Summary'.\n"
            f"Inventory: {json.dumps([item.model_dump() for item in constraints.available_ingredients], ensure_ascii=False)}\n"
            f"Portions: {constraints.portion_size}\n"
            f"Global request: {constraints.global_requests}\n"
            f"Dislikes: {json.dumps(constraints.allergies_and_dislikes, ensure_ascii=False)}\n"
            f"Inspiration: {json.dumps([recipe.model_dump() for recipe in retrieved_recipes[:5]], ensure_ascii=False)}\n"
        )
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a careful home cooking planner. Return markdown only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
        except Exception as exc:
            logger.warning("[Node 3] OpenAI generation failed, falling back locally: %s", exc)

    return _local_meal_plan_markdown(constraints, retrieved_recipes)


async def node_1_planning_extract(user_input: str) -> UserMenuConstraints:
    """Node 1 planning through an OpenAI-first service with local fallback."""

    logger.info("[Node 1] planning input: %s...", user_input[:100])
    try:
        constraints = await planning_service.plan(user_input)
    except Exception as exc:
        logger.error("[Node 1] planning failure: %s", exc)
        raise ValueError(f"Planning service failure: {exc}") from exc

    logger.info(
        "[Node 1] planning completed with %s search queries",
        len(constraints.search_queries),
    )
    return constraints


async def node_2_concurrent_retrieval(
    queries: list[str],
) -> tuple[list[RetrievedRecipe], list[dict[str, Any]]]:
    """Node 2 retrieval wrapper with query-level failure insulation."""

    logger.info("[Node 2] retrieval starting with %s queries", len(queries))
    try:
        success_results, failed_queries = await retrieve_recipes(queries)
        logger.info(
            "[Node 2] retrieval completed: %s successes, %s failures",
            len(success_results),
            len(failed_queries),
        )
        return success_results, failed_queries
    except CaptchaDetectedError as exc:
        logger.error("[Node 2] captcha detected: %s", exc)
        return [], [{"query": "all", "reason": "captcha_detected"}]
    except Exception as exc:
        logger.error("[Node 2] retrieval failure: %s", exc)
        return [], [{"query": "all", "reason": str(exc)}]


async def node_3_generate_meal_plan_stream(
    constraints: UserMenuConstraints,
    retrieved_recipes: list[RetrievedRecipe],
) -> AsyncGenerator[str, None]:
    """Temporary streaming layer until Task 4 introduces generation.py."""

    logger.info("[Node 3] generation starting")
    markdown = await _generate_markdown(constraints, retrieved_recipes)
    for chunk in _chunk_text(markdown):
        yield chunk


async def process_agent_stream(
    user_input: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the three-stage agent flow and emit SSE-friendly event payloads."""

    try:
        constraints = await node_1_planning_extract(user_input)
        yield {
            "event": "planning_done",
            "data": constraints.model_dump(),
        }

        retrieved_recipes, _failed_queries = await node_2_concurrent_retrieval(
            constraints.search_queries
        )

        for query in constraints.search_queries:
            is_success = any(recipe.source_query == query for recipe in retrieved_recipes)
            yield {
                "event": "retrieval_update",
                "data": {
                    "query": query,
                    "status": "success" if is_success else "fail",
                },
            }

        async for chunk in node_3_generate_meal_plan_stream(
            constraints, retrieved_recipes
        ):
            yield {
                "event": "recipe_stream",
                "data": {"chunk": chunk},
            }
    except Exception as exc:
        logger.error("[Agent] pipeline failure: %s", exc)
        yield {
            "event": "error",
            "data": {"message": str(exc)},
        }
