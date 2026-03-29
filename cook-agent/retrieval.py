"""
Multi-strategy retrieval cascade:
MCP -> Schema(JSON-LD only) -> Bing(title/snippet) -> Playwright
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

try:
    from fake_useragent import UserAgent
except Exception:  # pragma: no cover - optional dependency in test env
    UserAgent = None

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional dependency in test env
    async_playwright = None

from models import RetrievedRecipe, RetrievalStrategy

logger = logging.getLogger(__name__)


class CaptchaDetectedError(Exception):
    """Raised when captcha is detected and we should stop page extraction."""


class RetrievalStrategy_ABC(ABC):
    @abstractmethod
    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """Retrieve one recipe for a query."""


class MCPRetrievalStrategy(RetrievalStrategy_ABC):
    """MCP strategy placeholder; enabled only when required env vars exist."""

    def __init__(self):
        self.xhs_cookie = os.getenv("XHS_COOKIE", "")
        self.a1 = os.getenv("A1", "")
        self.enabled = bool(self.xhs_cookie and self.a1)

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        if not self.enabled:
            return None
        logger.info("MCP retrieval placeholder for query=%s", query)
        return None


class SchemaExtractionStrategy(RetrievalStrategy_ABC):
    """Extract only Recipe JSON-LD schema from candidate pages."""

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

    async def _fetch_and_parse(self, query: str, website: dict[str, str]) -> Optional[RetrievedRecipe]:
        url = website["url_template"].format(query)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
        except Exception as exc:
            logger.debug("Schema fetch failed for %s: %s", website["name"], exc)
            return None

        soup = BeautifulSoup(response.content, "lxml")
        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            script_body = script.string or script.get_text() or ""
            if not script_body.strip():
                continue
            try:
                data = json.loads(script_body)
            except json.JSONDecodeError:
                continue

            recipe_schema = self._extract_recipe_schema(data)
            if recipe_schema is not None:
                return self._parse_recipe_schema(recipe_schema, query)

        return None

    def _extract_recipe_schema(self, data: Any) -> Optional[dict[str, Any]]:
        if isinstance(data, dict):
            if data.get("@type") == "Recipe":
                return data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict) and node.get("@type") == "Recipe":
                        return node
            return None

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Recipe":
                    return item
            return None

        return None

    def _parse_recipe_schema(self, schema_data: dict[str, Any], query: str) -> RetrievedRecipe:
        ingredients = schema_data.get("recipeIngredient", [])
        if isinstance(ingredients, str):
            ingredients = [ingredients]
        if not isinstance(ingredients, list):
            ingredients = []

        instructions = schema_data.get("recipeInstructions", "")
        if isinstance(instructions, list):
            instruction_parts: list[str] = []
            for step in instructions:
                if isinstance(step, dict):
                    instruction_parts.append(str(step.get("text", "")))
                else:
                    instruction_parts.append(str(step))
            instructions = " ".join(part for part in instruction_parts if part)
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
    """Use Bing Search API and return title+snippet only."""

    def __init__(self):
        self.api_key = os.getenv("BING_SEARCH_API_KEY", "")
        self.enabled = bool(self.api_key)

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        if not self.enabled:
            return None

        enhanced_query = f"{query} site:xiaohongshu.com"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    headers={"Ocp-Apim-Subscription-Key": self.api_key},
                    params={"q": enhanced_query, "count": 5, "freshness": "Month"},
                )
                response.raise_for_status()
        except Exception as exc:
            logger.debug("Bing search failed: %s", exc)
            return None

        payload = response.json()
        values = payload.get("webPages", {}).get("value", [])
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
    """
    Dynamic fallback fetch with random delay and captcha fuse logic.
    """

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        if async_playwright is None:
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                user_agent = UserAgent().random if UserAgent is not None else None
                page = await browser.new_page(user_agent=user_agent)

                await page.add_init_script(self._get_stealth_script())
                await page.goto(
                    f"https://www.xiachufang.com/search/?kw={query}",
                    wait_until="load",
                )
                await asyncio.sleep(random.uniform(1.5, 4.3))

                if await self._has_captcha(page):
                    raise CaptchaDetectedError(f"captcha detected for query={query}")

                recipe_data = await self._extract_recipe(page)
                await browser.close()
        except CaptchaDetectedError:
            return None
        except Exception as exc:
            logger.debug("Playwright retrieval failed: %s", exc)
            return None

        if not recipe_data:
            return None

        return RetrievedRecipe(
            source_query=query,
            source_strategy=RetrievalStrategy.PLAYWRIGHT,
            title=recipe_data.get("title", ""),
            ingredients=recipe_data.get("ingredients", []),
            instructions_or_snippet=recipe_data.get("instructions", ""),
            raw_content=json.dumps(recipe_data, ensure_ascii=False),
        )

    @staticmethod
    def _get_stealth_script() -> str:
        return """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
        """

    @staticmethod
    async def _has_captcha(page) -> bool:
        captcha_selectors = [
            "secsdk-captcha",
            "verify-bar",
            ".captcha",
            "[class*='captcha']",
        ]
        for selector in captcha_selectors:
            try:
                if await page.query_selector(selector):
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    async def _extract_recipe(page) -> Optional[dict[str, Any]]:
        try:
            recipe = await page.evaluate(
                """
                () => {
                    const title = document.querySelector('h1.recipe-title')?.textContent || '';
                    const ingredients = Array.from(document.querySelectorAll('.ingredient-item')).map(el => el.textContent || '');
                    const instructions = document.querySelector('.cooking-steps')?.textContent || '';
                    return { title, ingredients, instructions };
                }
                """
            )
        except Exception:
            return None

        if not recipe or not recipe.get("title"):
            return None
        return recipe


class FallbackRetriever:
    """
    Query-level retrieval cascade:
    MCP -> Schema -> Bing -> Playwright
    """

    def __init__(self, strategies=None):
        self.strategies = strategies or [
            MCPRetrievalStrategy(),
            SchemaExtractionStrategy(),
            BingSearchStrategy(),
            PlaywrightStrategy(),
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

    async def retrieve_with_fallback(self, query: str) -> Optional[RetrievedRecipe]:
        """Compatibility helper retained for existing callers."""
        result, _ = await self.retrieve_query(query)
        return result

    async def batch_retrieve(
        self, queries: list[str], max_concurrent: int = 3
    ) -> tuple[list[RetrievedRecipe], list[dict]]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def retrieve_with_semaphore(query: str):
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

        tasks = [retrieve_with_semaphore(query) for query in queries]
        results = await asyncio.gather(*tasks)

        success_results = [recipe for recipe, _ in results if recipe is not None]
        updates = [meta for _, meta in results]
        return success_results, updates


async def retrieve_recipes(queries: list[str]) -> tuple[list[RetrievedRecipe], list[dict]]:
    """Convenience wrapper for batch retrieval."""
    retriever = FallbackRetriever()
    return await retriever.batch_retrieve(queries)
