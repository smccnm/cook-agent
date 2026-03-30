import asyncio

from planning import LocalPlanningService, PlanningService, PLANNING_SYSTEM_PROMPT


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


def test_local_planner_guesses_classic_dish_names():
    service = LocalPlanningService()
    result = service.plan("我有番茄和鸡蛋，想做快手晚饭")

    joined = " | ".join(result.search_queries)
    assert "番茄炒蛋" in joined or "西红柿炒鸡蛋" in joined


def test_planning_prompt_mentions_three_query_dimensions():
    assert "维度一（原始食材广撒网）" in PLANNING_SYSTEM_PROMPT
    assert "维度二（精准菜名击打）" in PLANNING_SYSTEM_PROMPT
    assert "维度三（宏观场景补足）" in PLANNING_SYSTEM_PROMPT
