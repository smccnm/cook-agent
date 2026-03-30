import asyncio

from generation import LocalMealPlanService, MealGenerationService
from models import IngredientItem, UserMenuConstraints


def test_local_generation_starts_with_accounting_summary():
    service = LocalMealPlanService()
    constraints = UserMenuConstraints(
        available_ingredients=[IngredientItem(name="土豆", quantity="5个")],
        allergies_and_dislikes=[],
        portion_size=2,
        global_requests="两菜一汤",
        search_queries=["土豆 做法 少油"],
    )

    markdown = service.compose_markdown(constraints, [])

    assert "总厨算账总结" in markdown


def test_generation_service_falls_back_to_local_chunks():
    service = MealGenerationService(openai_client=None)
    constraints = UserMenuConstraints(
        available_ingredients=[IngredientItem(name="鸡蛋", quantity="4个")],
        allergies_and_dislikes=[],
        portion_size=2,
        global_requests="两道快手菜",
        search_queries=["鸡蛋 快手菜"],
    )

    chunks = asyncio.run(_collect_chunks(service, constraints))

    assert "".join(chunks).startswith("###")


async def _collect_chunks(service: MealGenerationService, constraints: UserMenuConstraints):
    return [chunk async for chunk in service.stream(constraints, [])]
