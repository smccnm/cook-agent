import json
import re
from itertools import combinations
from typing import Iterable

from models import IngredientItem, UserMenuConstraints
from settings import AppSettings


_INGREDIENT_STOP_WORDS = {
    "我",
    "我们",
    "有",
    "想",
    "做",
    "晚上",
    "中午",
    "早上",
    "今天",
    "明天",
    "个人",
    "人",
    "晚餐",
    "午餐",
    "早餐",
    "不吃",
    "不要",
    "两菜一汤",
}

_KNOWN_INGREDIENTS = (
    "番茄",
    "西红柿",
    "鸡蛋",
    "土豆",
    "茄子",
    "黄瓜",
    "青椒",
    "豆腐",
    "牛肉",
    "猪肉",
    "排骨",
)

_CN_NUM_MAP = {
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


def _normalize_text(text: str) -> str:
    return text.replace("，", ",").replace("。", ".").replace("；", ";").strip()


def _normalize_ingredient_name(name: str) -> str:
    normalized = name.strip()
    if normalized == "西红柿":
        return "番茄"
    return normalized


def _contains_stop_word(token: str) -> bool:
    return token in _INGREDIENT_STOP_WORDS or len(token) <= 1


def _parse_cn_number(text: str) -> int | None:
    if not text:
        return None
    if text in _CN_NUM_MAP:
        return _CN_NUM_MAP[text]
    if text == "十":
        return 10
    if text.startswith("十"):
        return 10 + _CN_NUM_MAP.get(text[1:], 0)
    if text.endswith("十"):
        return _CN_NUM_MAP.get(text[0], 1) * 10
    if "十" in text and len(text) == 3:
        return _CN_NUM_MAP.get(text[0], 0) * 10 + _CN_NUM_MAP.get(text[2], 0)
    return None


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def extract_ingredients(user_input: str) -> list[IngredientItem]:
    text = _normalize_text(user_input)
    ingredients: list[IngredientItem] = []
    seen: set[str] = set()

    quantity_pattern = re.compile(
        r"(\d+\s*(?:个|斤|克|g|kg|颗|根|只|条|块|勺|碗|ml|毫升)?)\s*([\u4e00-\u9fff]{1,8})"
    )
    for match in quantity_pattern.finditer(text):
        quantity = match.group(1).strip()
        name = _normalize_ingredient_name(match.group(2).strip())
        if _contains_stop_word(name):
            continue
        if name in seen:
            continue
        seen.add(name)
        ingredients.append(IngredientItem(name=name, quantity=quantity))

    segment_match = re.search(r"有([^。！？!?]+)", user_input)
    if segment_match:
        raw_segment = segment_match.group(1)
        segment = re.split(r"[，,。;；](?:晚上|中午|早上|想|不|给|做)", raw_segment)[0]
        tokens = re.split(r"[、,，和及与 ]+", segment)
        for token in tokens:
            token = _normalize_ingredient_name(re.sub(r"[^\u4e00-\u9fff]", "", token))
            if _contains_stop_word(token):
                continue
            if token in seen:
                continue
            seen.add(token)
            ingredients.append(IngredientItem(name=token, quantity="适量"))

    if not ingredients:
        for candidate in _KNOWN_INGREDIENTS:
            if candidate in user_input and candidate not in seen:
                ingredients.append(IngredientItem(name=candidate, quantity="适量"))
                seen.add(candidate)

    return ingredients


def extract_dislikes(user_input: str) -> list[str]:
    dislikes: list[str] = []
    for prefix in ("不吃", "不要", "不放", "讨厌"):
        pattern = re.compile(rf"{prefix}\s*([^\s，。,；;、]+)")
        for match in pattern.finditer(user_input):
            dislikes.append(f"{prefix}{match.group(1)}")
    return _dedupe(dislikes)


def extract_portion_size(user_input: str) -> int:
    digit_match = re.search(r"(\d+)\s*(?:个)?(?:人|位)", user_input)
    if digit_match:
        return max(int(digit_match.group(1)), 1)

    cn_match = re.search(r"([零一二两三四五六七八九十]{1,3})\s*(?:个)?(?:人|位)", user_input)
    if cn_match:
        parsed = _parse_cn_number(cn_match.group(1))
        if parsed:
            return max(parsed, 1)

    return 1


def extract_global_request(user_input: str) -> str:
    requests: list[str] = []
    if "晚上吃" in user_input:
        requests.append("晚上吃")

    scene_match = re.search(r"([一二两三四五六七八九十\d]+菜[一二两三四五六七八九十\d]+汤)", user_input)
    if scene_match:
        requests.append(scene_match.group(1))

    for keyword in ("减脂", "清淡", "快手", "下饭"):
        if keyword in user_input:
            requests.append(keyword)

    return "；".join(_dedupe(requests))


def build_keyword_queries(
    ingredients: list[IngredientItem],
    dislikes: list[str],
    global_requests: str,
) -> list[str]:
    ingredient_names = [item.name for item in ingredients] or ["家常菜"]
    dislike_terms: list[str] = []
    if any("辣" in item for item in dislikes):
        dislike_terms.append("不辣")
    scene_terms = [part for part in global_requests.split("；") if part]
    modifier_terms = _dedupe(scene_terms + dislike_terms)

    queries: list[str] = []
    joined = " ".join(ingredient_names[:3])
    queries.append(f"{joined} 家常 做法".strip())
    queries.append(f"{joined} 快手 菜谱".strip())

    for left, right in combinations(ingredient_names[:4], 2):
        queries.append(f"{left} {right} 做法")

    for modifier in modifier_terms:
        queries.append(f"{joined} {modifier} 做法".strip())

    if "两菜一汤" in global_requests:
        queries.append(f"{joined} 两菜一汤 菜单".strip())
        queries.append(f"{joined} 家常 汤 做法".strip())
    elif "晚上吃" in global_requests:
        queries.append(f"{joined} 晚餐 菜单".strip())
        queries.append(f"{joined} 晚上吃 汤 做法".strip())

    fallback_queries = [
        f"{joined} 少油 做法".strip(),
        f"{joined} 清淡 菜谱".strip(),
        f"{joined} 下饭 家常菜".strip(),
        f"{joined} 汤 做法".strip(),
    ]

    deduped = _dedupe(queries)
    for fallback in fallback_queries:
        if len(deduped) >= 4:
            break
        if fallback not in deduped:
            deduped.append(fallback)

    return deduped[:8]


def _extract_json_payload(raw_content: str) -> dict:
    content = raw_content.strip()
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif content.startswith("```") and content.endswith("```"):
        content = content.strip("`").strip()
    return json.loads(content)


class LocalPlanningService:
    def plan(self, user_input: str) -> UserMenuConstraints:
        ingredients = extract_ingredients(user_input)
        dislikes = extract_dislikes(user_input)
        portion_size = extract_portion_size(user_input)
        global_requests = extract_global_request(user_input)
        search_queries = build_keyword_queries(
            ingredients=ingredients,
            dislikes=dislikes,
            global_requests=global_requests,
        )
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
        self.openai_client = openai_client
        self.settings = settings or AppSettings()
        self.local_service = local_service or LocalPlanningService()

    async def plan(self, user_input: str) -> UserMenuConstraints:
        if self.openai_client and self.settings.openai_enabled:
            try:
                return await self._plan_with_openai(user_input)
            except Exception:
                pass
        return self.local_service.plan(user_input)

    async def _plan_with_openai(self, user_input: str) -> UserMenuConstraints:
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract structured cooking constraints as JSON with keys: "
                        "available_ingredients, allergies_and_dislikes, portion_size, "
                        "flavor_preferences, global_requests, search_queries."
                    ),
                },
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        payload = _extract_json_payload(content)
        constraints = UserMenuConstraints(**payload)
        if not constraints.search_queries:
            constraints.search_queries = build_keyword_queries(
                ingredients=constraints.available_ingredients,
                dislikes=constraints.allergies_and_dislikes,
                global_requests=constraints.global_requests,
            )
        return constraints
