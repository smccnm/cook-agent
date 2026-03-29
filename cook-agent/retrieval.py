"""
多策略检索瀑布流实现
支持四层降级：MCP -> Schema提取 -> Bing搜索 -> Playwright爬取
"""
import asyncio
import json
import logging
import os
import random
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

from models import RetrievedRecipe, RetrievalStrategy

logger = logging.getLogger(__name__)


class CaptchaDetectedError(Exception):
    """检测到验证码时抛出"""
    pass


class RetrievalStrategy_ABC(ABC):
    """检索策略抽象基类"""

    @abstractmethod
    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """
        执行检索，返回单个菜谱或None（失败）
        """
        pass


# ======================== 策略 1: MCP 协议接入法 ========================

class MCPRetrievalStrategy(RetrievalStrategy_ABC):
    """
    通过 MCP 协议连接小红书爬虫服务
    需要环境变量：XHS_COOKIE, A1
    """

    def __init__(self):
        self.xhs_cookie = os.getenv("XHS_COOKIE", "")
        self.a1 = os.getenv("A1", "")
        self.enabled = bool(self.xhs_cookie and self.a1)

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """MCP 检索实现"""
        if not self.enabled:
            logger.warning("MCP 策略未启用：缺少 XHS_COOKIE 或 A1 环境变量")
            return None

        try:
            # TODO: 实现 MCP 客户端连接与 search_notes 调用
            # 这里是占位符，实际需要通过 mcp SDK 连接服务
            logger.info(f"MCP 检索: {query}")
            # mcp_client = MCPClient(...)
            # result = await mcp_client.search_notes(query)
            # return self._parse_mcp_result(result)
            return None
        except Exception as e:
            logger.error(f"MCP 检索失败: {e}")
            return None

    def _parse_mcp_result(self, raw_result: Dict[str, Any]) -> Optional[RetrievedRecipe]:
        """解析 MCP 返回结果"""
        try:
            return RetrievedRecipe(
                source_query=raw_result.get("query", ""),
                source_strategy=RetrievalStrategy.MCP,
                title=raw_result.get("title", ""),
                ingredients=raw_result.get("ingredients", []),
                instructions_or_snippet=raw_result.get("description", ""),
                raw_content=json.dumps(raw_result),
            )
        except Exception as e:
            logger.error(f"MCP 结果解析失败: {e}")
            return None


# ======================== 策略 2: 垂类网站 Schema 提取法 ========================

class SchemaExtractionStrategy(RetrievalStrategy_ABC):
    """
    从下厨房、美食杰、豆果美食等网站提取 JSON-LD Schema 数据
    """

    WEBSITES = [
        {"url_template": "https://www.xiachufang.com/search/?kw={}", "name": "下厨房"},
        {"url_template": "https://www.meishij.net/search?q={}", "name": "美食杰"},
        {"url_template": "https://www.douguo.com/search?keywords={}", "name": "豆果美食"},
    ]

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """尝试从各个垂类网站提取 Schema"""
        for website in self.WEBSITES:
            try:
                result = await self._fetch_and_parse(query, website)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"从 {website['name']} 提取失败: {e}")
                continue

        return None

    async def _fetch_and_parse(self, query: str, website: Dict) -> Optional[RetrievedRecipe]:
        """获取网页并从 <head> 的 JSON-LD Schema 提取数据"""
        try:
            url = website["url_template"].format(query)
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

            soup = BeautifulSoup(response.content, "lxml")
            
            # 提取 JSON-LD 数据
            json_ld_scripts = soup.find_all("script", {"type": "application/ld+json"})
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if data.get("@type") == "Recipe":
                        return self._parse_recipe_schema(data, query, website["name"])
                except json.JSONDecodeError:
                    continue

            return None

        except Exception as e:
            logger.error(f"Schema 提取失败 ({website['name']}): {e}")
            return None

    def _parse_recipe_schema(
        self, schema_data: Dict, query: str, source_name: str
    ) -> RetrievedRecipe:
        """解析 Recipe Schema 结构"""
        ingredients = []
        if "recipeIngredient" in schema_data:
            ingredients = schema_data["recipeIngredient"]
            if isinstance(ingredients, str):
                ingredients = [ingredients]

        instructions = ""
        if "recipeInstructions" in schema_data:
            instructions_data = schema_data["recipeInstructions"]
            if isinstance(instructions_data, list):
                instructions = " ".join(
                    [step.get("text", "") if isinstance(step, dict) else str(step)
                     for step in instructions_data]
                )
            else:
                instructions = str(instructions_data)

        return RetrievedRecipe(
            source_query=query,
            source_strategy=RetrievalStrategy.SCHEMA,
            title=schema_data.get("name", ""),
            ingredients=ingredients,
            instructions_or_snippet=instructions,
            raw_content=json.dumps(schema_data),
        )


# ======================== 策略 3: 搜索引擎摘要提取法 ========================

class BingSearchStrategy(RetrievalStrategy_ABC):
    """
    调用 Bing Search API 获取摘要，不进行二次爬取
    Query 自动附加 site:xiaohongshu.com
    """

    def __init__(self):
        self.api_key = os.getenv("BING_SEARCH_API_KEY", "")
        self.enabled = bool(self.api_key)

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """Bing 搜索实现"""
        if not self.enabled:
            logger.warning("Bing 搜索策略未启用：缺少 BING_SEARCH_API_KEY")
            return None

        try:
            # 增强 query 以更好地命中小红书内容
            enhanced_query = f"{query} site:xiaohongshu.com"
            
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Ocp-Apim-Subscription-Key": self.api_key}
                params = {
                    "q": enhanced_query,
                    "count": 5,
                    "freshness": "Month",
                }
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()

            data = response.json()
            
            # 提取第一个结果的 title 和 snippet
            if data.get("webPages", {}).get("value"):
                first_result = data["webPages"]["value"][0]
                return RetrievedRecipe(
                    source_query=query,
                    source_strategy=RetrievalStrategy.BING,
                    title=first_result.get("name", ""),
                    instructions_or_snippet=first_result.get("snippet", ""),
                    raw_content=json.dumps(first_result),
                )

            return None

        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            return None


# ======================== 策略 4: Playwright 动态爬取 ========================

class PlaywrightStrategy(RetrievalStrategy_ABC):
    """
    使用 Playwright 进行动态爬取
    - 注入 stealth 脚本
    - 随机延迟（1.5-4.3秒）
    - 滑块验证码熔断
    """

    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        """Playwright 爬取实现"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(user_agent=UserAgent().random)
                
                # 注入 stealth 脚本
                await page.add_init_script(self._get_stealth_script())
                
                # 访问搜索页面
                search_url = f"https://www.xiachufang.com/search/?kw={query}"
                await page.goto(search_url, wait_until="load")
                
                # 随机延迟
                await asyncio.sleep(random.uniform(1.5, 4.3))
                
                # 检查验证码
                if await self._has_captcha(page):
                    raise CaptchaDetectedError(f"检测到验证码，熔断查询: {query}")
                
                # 提取菜谱数据
                recipe_data = await self._extract_recipe(page)
                
                await browser.close()
                
                if recipe_data:
                    return RetrievedRecipe(
                        source_query=query,
                        source_strategy=RetrievalStrategy.PLAYWRIGHT,
                        title=recipe_data.get("title", ""),
                        ingredients=recipe_data.get("ingredients", []),
                        instructions_or_snippet=recipe_data.get("instructions", ""),
                        raw_content=json.dumps(recipe_data),
                    )

                return None

        except CaptchaDetectedError as e:
            logger.error(f"Playwright 策略熔断: {e}")
            return None
        except Exception as e:
            logger.error(f"Playwright 爬取失败: {e}")
            return None

    @staticmethod
    def _get_stealth_script() -> str:
        """返回反检测脚本"""
        return """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });
        window.chrome = {runtime: {}};
        """

    @staticmethod
    async def _has_captcha(page) -> bool:
        """检查页面是否包含验证码"""
        captcha_selectors = [
            "secsdk-captcha",
            "verify-bar",
            ".captcha",
            "[class*='captcha']",
        ]
        
        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    logger.warning(f"检测到验证码选择器: {selector}")
                    return True
            except:
                pass

        return False

    @staticmethod
    async def _extract_recipe(page) -> Optional[Dict[str, Any]]:
        """从页面提取菜谱信息"""
        # TODO: 根据下厨房的实际 DOM 结构提取
        try:
            recipe = await page.evaluate("""
                () => {
                    const title = document.querySelector('h1.recipe-title')?.textContent || '';
                    const ingredients = Array.from(document.querySelectorAll('.ingredient-item')).map(el => el.textContent);
                    const instructions = document.querySelector('.cooking-steps')?.textContent || '';
                    return { title, ingredients, instructions };
                }
            """)
            return recipe if recipe and recipe.get("title") else None
        except Exception as e:
            logger.error(f"页面数据提取失败: {e}")
            return None


# ======================== 瀑布流编排器 ========================

class FallbackRetriever:
    """
    多策略瀑布流检索器
    按优先级：MCP -> Schema -> Bing -> Playwright
    """

    def __init__(self):
        self.strategies: List[RetrievalStrategy_ABC] = [
            MCPRetrievalStrategy(),
            SchemaExtractionStrategy(),
            BingSearchStrategy(),
            PlaywrightStrategy(),
        ]

    async def retrieve_with_fallback(self, query: str) -> Optional[RetrievedRecipe]:
        """
        按优先级依次尝试各策略，遇到 CaptchaDetectedError 立即熔断
        """
        for strategy in self.strategies:
            try:
                logger.info(f"尝试策略 {strategy.__class__.__name__}: {query}")
                result = await strategy.retrieve(query)
                if result:
                    logger.info(f"✓ {strategy.__class__.__name__} 成功获取: {result.title}")
                    return result
                logger.debug(f"✗ {strategy.__class__.__name__} 无结果，继续降级")
            except CaptchaDetectedError as e:
                logger.error(f"❌ 验证码熔断，放弃此查询: {query}")
                raise
            except Exception as e:
                logger.warning(f"✗ {strategy.__class__.__name__} 异常，继续降级: {e}")
                continue

        logger.warning(f"⚠ 所有策略均失败: {query}")
        return None

    async def batch_retrieve(
        self, queries: List[str], max_concurrent: int = 3
    ) -> tuple[List[RetrievedRecipe], List[dict]]:
        """
        并发批量检索，限制并发数
        返回 (成功结果, 失败查询)
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def retrieve_with_semaphore(query: str):
            async with semaphore:
                try:
                    result = await self.retrieve_with_fallback(query)
                    return (result, None)
                except CaptchaDetectedError:
                    return (None, {"query": query, "reason": "captcha_detected"})
                except Exception as e:
                    return (None, {"query": query, "reason": str(e)})

        tasks = [retrieve_with_semaphore(q) for q in queries]
        results = await asyncio.gather(*tasks)

        success_results = [r[0] for r in results if r[0]]
        failed_queries = [r[1] for r in results if r[1]]

        return success_results, failed_queries


# ======================== 快速初始化 ========================

async def retrieve_recipes(queries: List[str]) -> tuple[List[RetrievedRecipe], List[dict]]:
    """便捷函数：直接执行批量检索"""
    retriever = FallbackRetriever()
    return await retriever.batch_retrieve(queries)
