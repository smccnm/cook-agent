import asyncio
import sys
import types

# Stub optional runtime dependencies so retrieval imports in test environment.
sys.modules.setdefault("fake_useragent", types.SimpleNamespace(UserAgent=object))
playwright_module = types.ModuleType("playwright")
async_api_module = types.ModuleType("playwright.async_api")
async_api_module.async_playwright = None
playwright_module.async_api = async_api_module
sys.modules.setdefault("playwright", playwright_module)
sys.modules.setdefault("playwright.async_api", async_api_module)

from retrieval import FallbackRetriever, RetrievedRecipe


class FailingStrategy:
    name = "MCP"

    async def retrieve(self, query: str):
        return None


class SuccessStrategy:
    name = "Schema"

    async def retrieve(self, query: str):
        return RetrievedRecipe(
            source_query=query,
            source_strategy="Schema",
            title="少油版地三鲜",
            instructions_or_snippet="土豆 茄子 少油快炒",
        )


def test_retriever_stops_at_first_success():
    retriever = FallbackRetriever(strategies=[FailingStrategy(), SuccessStrategy()])
    result, meta = asyncio.run(retriever.retrieve_query("土豆 茄子 少油"))

    assert result is not None
    assert result.source_strategy == "Schema"
    assert meta["status"] == "success"


def test_batch_retrieve_isolates_query_failures():
    retriever = FallbackRetriever(strategies=[FailingStrategy()])
    results, updates = asyncio.run(retriever.batch_retrieve(["query-a", "query-b"]))

    assert results == []
    assert len(updates) == 2
    assert all(item["status"] == "fail" for item in updates)
