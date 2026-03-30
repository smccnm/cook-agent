import asyncio

from planning import LocalPlanningService, PlanningService


def test_local_planner_returns_bounded_queries():
    service = LocalPlanningService()
    result = service.plan("tomato egg quick dinner for 2")

    assert result.portion_size >= 1
    assert 4 <= len(result.search_queries) <= 8
    assert all(query.strip() for query in result.search_queries)


def test_planning_service_falls_back_without_openai():
    service = PlanningService(openai_client=None)
    result = asyncio.run(service.plan("simple home meal ideas"))

    assert result.search_queries
    assert 4 <= len(result.search_queries) <= 8


def test_local_planner_handles_leftover_fast_meal_case():
    service = LocalPlanningService()
    result = service.plan(
        "我这只有半个昨天吃剩的圆白菜，3个鸡蛋，1根有点干瘪的火腿肠，"
        "还有大概一碗半的剩米饭。就我一个人吃，给我搞个能填饱肚子的快手晚餐，别太复杂。"
    )

    names = [item.name for item in result.available_ingredients]
    quantities = {item.name: item.quantity for item in result.available_ingredients}

    assert "鸡蛋" in names
    assert "火腿肠" in names
    assert "圆白菜" in names
    assert quantities["鸡蛋"] == "3个"
    assert quantities["火腿肠"] == "1根"
    assert result.portion_size == 1
    assert "快手" in result.global_requests


def test_local_planner_guesses_classic_dish_names():
    service = LocalPlanningService()
    result = service.plan("我有番茄和鸡蛋，想做快手晚饭")

    joined = " | ".join(result.search_queries)
    assert "番茄炒蛋" in joined or "西红柿炒鸡蛋" in joined
