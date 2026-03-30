from __future__ import annotations

import json
import re
from itertools import combinations
from typing import Iterable

from google import genai
from google.genai import types

from models import IngredientItem, UserMenuConstraints
from settings import AppSettings

PLANNING_SYSTEM_PROMPT = """# ROLE

你是一个极其严谨的美食统筹大脑兼高级搜索算法工程师。你的任务是将用户模糊、非结构化的自然语言，转化为高度结构化的 JSON 规划书。

# INPUT

用户的原始需求：{user_input}

# RULES & CONSTRAINTS

你必须严格遵守以下规则提取和推导信息：

1.【食材量化规则 (Ingredient Parsing)】

- 精确提取数量：将数量与名称分离，如“三个番茄” -> [{"name": "番茄", "quantity": "3个"}]。模糊量词填“适量”。

2.【全局约束与忌口提取 (Constraints & Allergies)】

- 隐性需求转化：“晚上吃” -> “易消化”；“做两菜一汤” -> 记录到 global_requests。
- 绝对红线提取：提取所有“过敏”、“不吃”、“讨厌”的食材，填入 allergies_and_dislikes。
- 偏好提取：提取“减脂”、“清淡”、“要辣”等偏好，填入 flavor_preferences。

3.【全量召回与红线校验策略 (Full-Recall Query Engineering) - 核心任务】

为了最大化搜索范围并严守用户底线，你必须推导并输出 4 到 8 个 search_queries。这些 query 必须按以下三种维度混合生成，且每一个 query 都必须绑定用户的特殊偏好（如减脂、不辣），并绝对排除忌口！

- 维度一（原始食材广撒网）：很多优秀菜谱不写具体菜名。你必须直接用原始食材进行两两或三三组合，加上烹饪目的。
  例（土豆+茄子+减脂）：["土豆 茄子 神仙吃法 减脂", "茄子 土豆 做法 少油"]

- 维度二（精准菜名击打）：根据食材组合猜想经典菜品，并加上修饰词。
  例（土豆+茄子+减脂）：["少油版 地三鲜", "空气炸锅 地三鲜"]

- 维度三（宏观场景补足）：如果用户有“两菜一汤”等需求，需专门生成场景词。
  例（一荤一素）：["快手 纯素菜 清淡", "下饭 荤菜 不辣"]

警告：

- 搜索词必须是“关键词空格组合”，绝对不能是完整的句子！
- 在生成任何 query 前进行内部红线校验：绝不生成违背 allergies_and_dislikes 的内容。

# OUTPUT FORMAT

严格按照 UserMenuConstraints JSON Schema 输出结果，不要输出任何额外解释性文本。
"""

KNOWN_INGREDIENTS = (
    "番茄",
    "西红柿",
    "鸡蛋",
    "土豆",
    "茄子",
    "黄瓜",
    "五花肉",
    "牛肉",
    "豆腐",
    "白菜",
    "豆角",
    "排骨",
    "虾",
    "鱼",
)

STOP_WORDS = {
    "我",
    "我们",
    "有",
    "想",
    "做",
    "晚上",
    "今天",
    "明天",
    "一个",
    "两个人",
    "不吃",
    "不要",
    "讨厌",
}

CN_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def _normalize_name(name: str) -> str:
    if name == "西红柿":
        return "番茄"
    return name.strip()


def _contains_stop_word(token: str) -> bool:
    return token in STOP_WORDS or len(token) <= 1


def _parse_cn_number(text: str) -> int | None:
    if not text:
        return None
    if text in CN_NUMBERS:
        return CN_NUMBERS[text]
    if text == "十":
        return 10
    if text.startswith("十"):
        return 10 + CN_NUMBERS.get(text[1:], 0)
    if text.endswith("十"):
        return CN_NUMBERS.get(text[0], 1) * 10
    if "十" in text and len(text) == 3:
        return CN_NUMBERS.get(text[0], 0) * 10 + CN_NUMBERS.get(text[2], 0)
    return None


def extract_ingredients(user_input: str) -> list[IngredientItem]:
    ingredients: list[IngredientItem] = []
    seen: set[str] = set()

    quantity_pattern = re.compile(
        r"(\d+\s*(?:个|克|g|kg|斤|两|ml|毫升)?)\s*([\u4e00-\u9fff]{1,8})"
    )
    for match in quantity_pattern.finditer(user_input):
        quantity = match.group(1).strip()
        name = _normalize_name(match.group(2).strip())
        if _contains_stop_word(name) or name in seen:
            continue
        ingredients.append(IngredientItem(name=name, quantity=quantity))
        seen.add(name)

    for candidate in KNOWN_INGREDIENTS:
        normalized = _normalize_name(candidate)
        if candidate in user_input and normalized not in seen:
            ingredients.append(IngredientItem(name=normalized, quantity="适量"))
            seen.add(normalized)

    return ingredients


def extract_dislikes(user_input: str) -> list[str]:
    dislikes: list[str] = []
    for prefix in ("不吃", "不要", "讨厌", "过敏"):
        pattern = re.compile(rf"{prefix}\s*([^\s，。；、]+)")
        for match in pattern.finditer(user_input):
            dislikes.append(match.group(1))
    return _dedupe(dislikes)


def extract_portion_size(user_input: str) -> int:
    digit_match = re.search(r"(\d+)\s*(?:人|个人|位)", user_input)
    if digit_match:
        return max(int(digit_match.group(1)), 1)

    cn_match = re.search(r"([零一二两三四五六七八九十]{1,3})\s*(?:人|个人|位)", user_input)
    if cn_match:
        value = _parse_cn_number(cn_match.group(1))
        if value:
            return max(value, 1)
    return 1


def extract_global_request(user_input: str) -> str:
    requests: list[str] = []
    if "晚上吃" in user_input:
        requests.append("易消化")
    if "两菜一汤" in user_input:
        requests.append("两菜一汤")
    if "一荤一素" in user_input:
        requests.append("一荤一素")
    for keyword in ("减脂", "清淡", "不辣", "快手", "下饭"):
        if keyword in user_input:
            requests.append(keyword)
    return "；".join(_dedupe(requests)) or "家常餐"


def build_keyword_queries(
    ingredients: list[IngredientItem],
    dislikes: list[str],
    global_requests: str,
) -> list[str]:
    ingredient_names = [item.name for item in ingredients] or ["家常菜"]
    queries: list[str] = []
    dislike_terms = ["不辣"] if any(item in {"辣", "辣椒"} for item in dislikes) else []
    scene_terms = [item for item in global_requests.split("；") if item]

    for combo_size in (2, 3):
        count = min(combo_size, len(ingredient_names[:4]))
        if count < 2:
            continue
        for combo in combinations(ingredient_names[:4], count):
            base = " ".join(combo)
            queries.append(f"{base} 神仙吃法")
            queries.append(f"{base} 做法")

    classic_pairs = {
        frozenset({"土豆", "茄子"}): ["少油版 地三鲜", "空气炸锅 地三鲜"],
        frozenset({"番茄", "鸡蛋"}): ["番茄炒蛋 家常", "西红柿炒鸡蛋 快手", "番茄 鸡蛋 汤"],
        frozenset({"豆腐", "白菜"}): ["豆腐 白菜 清淡", "白菜 豆腐 汤"],
    }
    existing = set(ingredient_names)
    for pair, pair_queries in classic_pairs.items():
        if pair.issubset(existing):
            queries.extend(pair_queries)

    for term in scene_terms + dislike_terms:
        queries.append(f"{' '.join(ingredient_names[:3])} {term}")

    filtered = []
    for query in _dedupe(queries):
        if any(dislike and dislike in query for dislike in dislikes):
            continue
        filtered.append(query)
        if len(filtered) == 8:
            break

    while len(filtered) < 4:
        fallback = f"{' '.join(ingredient_names[:2])} 家常 做法 {len(filtered)+1}"
        if fallback not in filtered:
            filtered.append(fallback)

    return filtered[:8]


class LocalPlanningService:
    def plan(self, user_input: str) -> UserMenuConstraints:
        ingredients = extract_ingredients(user_input)
        dislikes = extract_dislikes(user_input)
        portion_size = extract_portion_size(user_input)
        global_requests = extract_global_request(user_input)
        search_queries = build_keyword_queries(ingredients, dislikes, global_requests)
        return UserMenuConstraints(
            available_ingredients=ingredients,
            allergies_and_dislikes=dislikes,
            portion_size=portion_size,
            global_requests=global_requests,
            search_queries=search_queries,
        )


class PlanningService:
    def __init__(
        self,
        openai_client=None,
        settings: AppSettings | None = None,
        local_service: LocalPlanningService | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.local_service = local_service or LocalPlanningService()
        self.google_client = (
            genai.Client(api_key=self.settings.gemini_api_key)
            if self.settings.gemini_enabled
            else None
        )
        self.openai_client = openai_client

    async def plan(self, user_input: str) -> UserMenuConstraints:
        if self.google_client is not None:
            try:
                return await self._plan_with_gemini(user_input)
            except Exception:
                pass
        if self.openai_client and self.settings.openai_enabled:
            try:
                return await self._plan_with_openai(user_input)
            except Exception:
                pass
        return self.local_service.plan(user_input)

    async def _plan_with_gemini(self, user_input: str) -> UserMenuConstraints:
        response = await self.google_client.aio.models.generate_content(
            model=self.settings.gemini_planning_model,
            contents=PLANNING_SYSTEM_PROMPT.format(user_input=user_input),
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=UserMenuConstraints,
            ),
        )
        payload = json.loads(response.text)
        constraints = UserMenuConstraints(**payload)
        if not constraints.search_queries:
            constraints.search_queries = build_keyword_queries(
                constraints.available_ingredients,
                constraints.allergies_and_dislikes,
                constraints.global_requests,
            )
        return constraints

    async def _plan_with_openai(self, user_input: str) -> UserMenuConstraints:
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": PLANNING_SYSTEM_PROMPT.format(user_input=user_input)},
            ],
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return UserMenuConstraints(**payload)
