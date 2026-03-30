"""Agent orchestration layer for the streaming meal-plan workflow."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from generation import MealGenerationService
from models import RetrievedRecipe, UserMenuConstraints
from planning import PlanningService
from retrieval import FallbackRetriever
from settings import AppSettings

logger = logging.getLogger(__name__)

settings = AppSettings()
planning_service = PlanningService(settings=settings)
generation_service = MealGenerationService(settings=settings)


async def node_1_planning_extract(user_input: str) -> UserMenuConstraints:
    logger.info("[Node 1] planning input: %s...", user_input[:100])
    constraints = await planning_service.plan(user_input)
    logger.info(
        "[Node 1] planning completed with %s search queries",
        len(constraints.search_queries),
    )
    return constraints


async def node_2_concurrent_retrieval(
    queries: list[str], max_concurrent: int = 3
) -> tuple[list[RetrievedRecipe], list[dict[str, Any]]]:
    retriever = FallbackRetriever(settings=settings)
    semaphore = asyncio.Semaphore(max_concurrent)
    recipes: list[RetrievedRecipe] = []
    updates: list[dict[str, Any]] = []

    async def guarded(query: str):
        async with semaphore:
            return await retriever.retrieve_query(query)

    tasks = [asyncio.create_task(guarded(query)) for query in queries]
    for task in asyncio.as_completed(tasks):
        recipe, update = await task
        if recipe is not None:
            recipes.append(recipe)
        updates.append(update)

    return recipes, updates


async def node_3_generate_meal_plan_stream(
    constraints: UserMenuConstraints,
    retrieved_recipes: list[RetrievedRecipe],
) -> AsyncGenerator[str, None]:
    async for chunk in generation_service.stream(constraints, retrieved_recipes):
        yield chunk


async def process_agent_stream(
    user_input: str,
) -> AsyncGenerator[dict[str, Any], None]:
    try:
        constraints = await node_1_planning_extract(user_input)
        yield {"event": "planning_done", "data": constraints.model_dump()}

        retrieved_recipes, updates = await node_2_concurrent_retrieval(
            constraints.search_queries
        )
        for update in updates:
            yield {"event": "retrieval_update", "data": update}

        async for chunk in node_3_generate_meal_plan_stream(
            constraints, retrieved_recipes
        ):
            yield {"event": "recipe_stream", "data": {"chunk": chunk}}

        yield {"event": "recipe_done", "data": {"status": "complete"}}
    except Exception as exc:
        logger.exception("[Agent] pipeline failure")
        yield {"event": "error", "data": {"message": str(exc)}}
