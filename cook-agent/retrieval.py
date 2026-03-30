"""Retrieval cascade:
MCP service -> Schema detail-page JSON-LD -> Bing -> Playwright fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

try:
    from fake_useragent import UserAgent
except Exception:  # pragma: no cover
    UserAgent = None

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover
    async_playwright = None

from models import RetrievedRecipe, RetrievalStrategy
from settings import AppSettings
from xhs_service import XHSServiceManager

logger = logging.getLogger(__name__)


class CaptchaDetectedError(Exception):
    """Raised when captcha or anti-bot behavior is detected."""


class RetrievalStrategy_ABC(ABC):
    @abstractmethod
    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """Retrieve one recipe for a query."""


class MCPRetrievalStrategy(RetrievalStrategy_ABC):
    def __init__(
        self,
        settings: AppSettings | None = None,
        xhs_manager: XHSServiceManager | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.xhs_manager = xhs_manager or XHSServiceManager(self.settings)

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        status = self.xhs_manager.login_status()
        if not status["logged_in"]:
            return None

        try:
            items = await self.xhs_manager.search(query)
        except Exception as exc:
            logger.debug("MCP retrieval failed: %s", exc)
            return None

        first = items[0] if items else {}
        title = (
            first.get("noteCard", {}).get("displayTitle")
            or first.get("displayTitle")
            or first.get("title")
            or ""
        )
        snippet = (
            first.get("noteCard", {}).get("desc")
            or first.get("desc")
            or first.get("content")
            or ""
        )
        if not title and not snippet:
            return None

        return RetrievedRecipe(
            source_query=query,
            source_strategy=RetrievalStrategy.MCP,
            title=str(title),
            instructions_or_snippet=str(snippet),
            raw_content=json.dumps(first, ensure_ascii=False),
        )


class SchemaExtractionStrategy(RetrievalStrategy_ABC):
    WEBSITES = [
        {"url_template": "https://www.xiachufang.com/search/?kw={}", "name": "xiachufang"},
        {"url_template": "https://www.meishij.net/search?q={}", "name": "meishij"},
        {"url_template": "https://www.douguo.com/search?keywords={}", "name": "douguo"},
    ]

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        for website in self.WEBSITES:
            result = await self._fetch_and_parse(query, website)
            if result is not None:
                return result
        return None

    async def _fetch_text(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _fetch_and_parse(
        self, query: str, website: dict[str, str]
    ) -> Optional[RetrievedRecipe]:
        try:
            search_html = await self._fetch_text(website["url_template"].format(query))
        except Exception as exc:
            logger.debug("Schema search fetch failed for %s: %s", website["name"], exc)
            return None

        recipe = self._parse_html_for_recipe(query, search_html)
        if recipe is not None:
            return recipe

        detail_links = self._extract_detail_links(search_html, website["name"])
        for detail_url in detail_links[:5]:
            try:
                detail_html = await self._fetch_text(detail_url)
            except Exception as exc:
                logger.debug("Schema detail fetch failed for %s: %s", detail_url, exc)
                continue
            recipe = self._parse_html_for_recipe(query, detail_html)
            if recipe is not None:
                return recipe
        return None

    def _parse_html_for_recipe(self, query: str, html: str) -> Optional[RetrievedRecipe]:
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            recipe_schema = self._extract_recipe_schema(data)
            if recipe_schema is not None:
                return self._parse_recipe_schema(recipe_schema, query)
        return None

    def _extract_detail_links(self, html: str, site_name: str) -> list[str]:
        if site_name == "xiachufang":
            relative_links = re.findall(r'(/recipe/\d+/)', html)
            links = [f"https://www.xiachufang.com{path}" for path in relative_links]
            links.extend(re.findall(r'https://www\.xiachufang\.com/recipe/\d+/', html))
            return list(dict.fromkeys(links))
        if site_name == "meishij":
            links = re.findall(r'https://www\.meishij\.net/zuofa/[^"\']+\.html', html)
            return list(dict.fromkeys(links))
        if site_name == "douguo":
            links = re.findall(r'https://www\.douguo\.com/cookbook/\d+\.html', html)
            return list(dict.fromkeys(links))
        return []

    def _extract_recipe_schema(self, data: Any) -> Optional[dict[str, Any]]:
        if isinstance(data, dict):
            if data.get("@type") == "Recipe":
                return data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict) and node.get("@type") == "Recipe":
                        return node
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Recipe":
                    return item
        return None

    def _parse_recipe_schema(self, schema_data: dict[str, Any], query: str) -> RetrievedRecipe:
        ingredients = schema_data.get("recipeIngredient", [])
        if isinstance(ingredients, str):
            ingredients = [ingredients]
        if not isinstance(ingredients, list):
            ingredients = []

        instructions = schema_data.get("recipeInstructions", "")
        if isinstance(instructions, list):
            parts: list[str] = []
            for step in instructions:
                if isinstance(step, dict):
                    parts.append(str(step.get("text", "")))
                else:
                    parts.append(str(step))
            instructions = " ".join(part for part in parts if part)
        else:
            instructions = str(instructions or "")

        return RetrievedRecipe(
            source_query=query,
            source_strategy=RetrievalStrategy.SCHEMA,
            title=str(schema_data.get("name", "")),
            ingredients=[str(item) for item in ingredients],
            instructions_or_snippet=instructions,
            raw_content=json.dumps(schema_data, ensure_ascii=False),
        )


class BingSearchStrategy(RetrievalStrategy_ABC):
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        if not self.settings.bing_enabled:
            return None

        enhanced_query = f"{query} site:xiaohongshu.com"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    headers={"Ocp-Apim-Subscription-Key": self.settings.bing_search_api_key},
                    params={"q": enhanced_query, "count": 5, "freshness": "Month"},
                )
                response.raise_for_status()
        except Exception as exc:
            logger.debug("Bing search failed: %s", exc)
            return None

        values = response.json().get("webPages", {}).get("value", [])
        if not values:
            return None

        first = values[0]
        return RetrievedRecipe(
            source_query=query,
            source_strategy=RetrievalStrategy.BING,
            title=str(first.get("name", "")),
            instructions_or_snippet=str(first.get("snippet", "")),
            raw_content=json.dumps(first, ensure_ascii=False),
        )


class PlaywrightStrategy(RetrievalStrategy_ABC):
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        if async_playwright is None:
            return None

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                user_agent = UserAgent().random if UserAgent is not None else None
                page = await browser.new_page(user_agent=user_agent)
                try:
                    await page.add_init_script(self._stealth_script())
                    await page.goto(
                        f"https://www.xiachufang.com/search/?kw={query}",
                        wait_until="domcontentloaded",
                    )
                    await asyncio.sleep(
                        random.uniform(
                            self.settings.random_delay_min,
                            self.settings.random_delay_max,
                        )
                    )
                    if await self._has_captcha(page):
                        raise CaptchaDetectedError(query)

                    search_html = await page.content()
                    detail_links = SchemaExtractionStrategy()._extract_detail_links(
                        search_html, "xiachufang"
                    )
                    for detail_url in detail_links[:3]:
                        await page.goto(detail_url, wait_until="domcontentloaded")
                        await asyncio.sleep(
                            random.uniform(
                                self.settings.random_delay_min,
                                self.settings.random_delay_max,
                            )
                        )
                        if await self._has_captcha(page):
                            raise CaptchaDetectedError(query)
                        recipe = await self._extract_recipe(page)
                        if self._should_fuse_missing_content(recipe):
                            raise CaptchaDetectedError(f"missing detail content for {query}")
                        if recipe is not None:
                            return RetrievedRecipe(
                                source_query=query,
                                source_strategy=RetrievalStrategy.PLAYWRIGHT,
                                title=recipe.get("title", ""),
                                ingredients=recipe.get("ingredients", []),
                                instructions_or_snippet=recipe.get("instructions", ""),
                                raw_content=json.dumps(recipe, ensure_ascii=False),
                            )
                finally:
                    await browser.close()
        except CaptchaDetectedError:
            return None
        except Exception as exc:
            logger.debug("Playwright retrieval failed: %s", exc)
            return None

        return None

    @staticmethod
    def _stealth_script() -> str:
        return """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
        """

    async def _has_captcha(self, page) -> bool:
        if not self.settings.captcha_detection_enabled:
            return False
        content = await page.content()
        markers = ("secsdk-captcha", "verify-bar", "captcha", "人机验证")
        return any(marker in content for marker in markers)

    @staticmethod
    def _should_fuse_missing_content(recipe: Optional[dict[str, Any]]) -> bool:
        return not recipe or not recipe.get("title")

    @staticmethod
    async def _extract_recipe(page) -> Optional[dict[str, Any]]:
        try:
            html = await page.content()
        except Exception:
            return None

        return SchemaExtractionStrategy()._parse_html_for_recipe("playwright", html).model_dump() if SchemaExtractionStrategy()._parse_html_for_recipe("playwright", html) else None


class FallbackRetriever:
    def __init__(self, strategies=None, settings: AppSettings | None = None):
        self.settings = settings or AppSettings()
        self.xhs_manager = XHSServiceManager(self.settings)
        self.strategies = strategies or [
            MCPRetrievalStrategy(self.settings, self.xhs_manager),
            SchemaExtractionStrategy(),
            BingSearchStrategy(self.settings),
            PlaywrightStrategy(self.settings),
        ]

    async def retrieve_query(self, query: str) -> tuple[RetrievedRecipe | None, dict]:
        for strategy in self.strategies:
            result = await strategy.retrieve(query)
            if result is not None:
                return result, {
                    "query": query,
                    "status": "success",
                    "strategy": str(result.source_strategy),
                    "title": result.title,
                    "message": "strategy hit",
                }
        return None, {
            "query": query,
            "status": "fail",
            "strategy": "",
            "title": "",
            "message": "all strategies exhausted",
        }

    async def batch_retrieve(
        self, queries: list[str], max_concurrent: int = 3
    ) -> tuple[list[RetrievedRecipe], list[dict]]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def guarded(query: str):
            async with semaphore:
                try:
                    return await self.retrieve_query(query)
                except Exception as exc:
                    return None, {
                        "query": query,
                        "status": "fail",
                        "strategy": "",
                        "title": "",
                        "message": str(exc),
                    }

        results = await asyncio.gather(*(guarded(query) for query in queries))
        recipes = [recipe for recipe, _ in results if recipe is not None]
        updates = [meta for _, meta in results]
        return recipes, updates


async def retrieve_recipes(queries: list[str]) -> tuple[list[RetrievedRecipe], list[dict]]:
    return await FallbackRetriever().batch_retrieve(queries)
