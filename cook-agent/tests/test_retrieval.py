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

from retrieval import (
    CaptchaDetectedError,
    FallbackRetriever,
    PlaywrightStrategy,
    RetrievedRecipe,
    SchemaExtractionStrategy,
)


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


def test_schema_strategy_extracts_detail_links_from_search_html():
    strategy = SchemaExtractionStrategy()
    html = '''
    <html><body>
      <a href="/recipe/123456/">detail</a>
      <a href="https://www.xiachufang.com/recipe/999999/">detail2</a>
    </body></html>
    '''

    links = strategy._extract_detail_links(html, "xiachufang")

    assert links == [
        "https://www.xiachufang.com/recipe/123456/",
        "https://www.xiachufang.com/recipe/999999/",
    ]


def test_schema_strategy_uses_detail_page_jsonld_after_search_page():
    strategy = SchemaExtractionStrategy()
    search_html = '<a href="/recipe/123456/">detail</a>'
    detail_html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"Recipe","name":"番茄炒蛋","recipeIngredient":["番茄 2个","鸡蛋 2个"],"recipeInstructions":[{"text":"先炒蛋"},{"text":"再炒番茄"}]}
    </script>
    </head><body></body></html>
    """

    async def fake_fetch(url: str):
        if "search" in url:
            return search_html
        return detail_html

    strategy._fetch_text = fake_fetch
    result = asyncio.run(
        strategy._fetch_and_parse(
            "番茄 鸡蛋 做法",
            {"url_template": "https://www.xiachufang.com/search/?kw={}", "name": "xiachufang"},
        )
    )

    assert result is not None
    assert result.title == "番茄炒蛋"
    assert "先炒蛋" in result.instructions_or_snippet


def test_playwright_strategy_fuses_when_detail_content_missing():
    strategy = PlaywrightStrategy()
    assert strategy._should_fuse_missing_content(None) is True
    assert strategy._should_fuse_missing_content({}) is True
    assert strategy._should_fuse_missing_content({"title": "番茄炒蛋"}) is False
