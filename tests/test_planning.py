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
