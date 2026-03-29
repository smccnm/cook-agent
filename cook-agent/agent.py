"""
AI Agent 编排层 - 三阶段流式处理
Node 1: 规划提取
Node 2: 并发检索
Node 3: 菜谱生成
"""
import asyncio
import json
import logging
import os
from typing import AsyncGenerator, List, Dict, Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from models import (
    UserMenuConstraints,
    IngredientItem,
    RetrievedRecipe,
    MealPlan,
    SSEEvent,
)
from retrieval import retrieve_recipes, CaptchaDetectedError

logger = logging.getLogger(__name__)

# 初始化 OpenAI 客户端
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")


# ======================== Node 1: 规划提取 ========================

PLANNING_SYSTEM_PROMPT = """# ROLE
你是一个极其严谨的美食统筹大脑兼高级搜索算法工程师。你的任务是将用户模糊、非结构化的自然语言，转化为高度结构化的 JSON 规划书。

# INPUT
用户的原始需求：{user_input}

# RULES & CONSTRAINTS

你必须严格遵守以下规则提取和推导信息：

1.【食材量化规则 (Ingredient Parsing)】
- 精确提取数量：将数量与名称分离，如"三个番茄" -> [{"name": "番茄", "quantity": "3个"}]。模糊量词填"适量"。

2.【全局约束与忌口提取 (Constraints & Allergies)】
- 隐性需求转化："晚上吃" -> "易消化"；"做两菜一汤" -> 记录到 global_requests。
- 绝对红线提取：提取所有"过敏"、"不吃"、"讨厌"的食材，填入 allergies_and_dislikes。
- 偏好提取：提取"减脂"、"清淡"、"要辣"等偏好，填入 flavor_preferences。

3.【全量召回与红线校验策略 (Full-Recall Query Engineering) - 核心任务】
为了最大化搜索范围并严守用户底线，你必须推导并输出 4 到 8 个 `search_queries`。这些 query 必须按以下两种维度混合生成，且每一个 query 都必须绑定用户的特殊偏好（如减脂、不辣），并绝对排除忌口！

- 维度一（原始食材广撒网）：很多优秀菜谱不写具体菜名。你必须直接用原始食材进行两两或三三组合，加上烹饪目的。
  例（土豆+茄子+减脂）：["土豆 茄子 神仙吃法 减脂", "茄子 土豆 做法 少油"]

- 维度二（精准菜名击打）：根据食材组合猜想经典菜品，并加上修饰词。
   例（土豆+茄子+减脂）：["少油版 地三鲜", "空气炸锅 地三鲜"]

- 维度三（宏观场景补足）：如果用户有"两菜一汤"等需求，需专门生成场景词。
   例（一荤一素）：["快手 纯素菜 清淡", "下饭 荤菜 不辣"]

警告：
- 搜索词必须是"关键词空格组合"，绝对不能是完整的句子！
- 在生成任何 query 前进行内部红线校验：绝不生成违背 allergies_and_dislikes 的内容（如用户不吃辣，绝不能生成包含"水煮肉片"、"麻辣"的词）。

# OUTPUT FORMAT
直接输出有效的 JSON，符合以下 Pydantic Schema：
```json
{{
  "available_ingredients": [
    {{"name": "食材名", "quantity": "数量"}}
  ],
  "allergies_and_dislikes": ["忌口1", "忌口2"],
  "portion_size": 人数,
  "flavor_preferences": ["偏好1"],
  "global_requests": "宏观需求",
  "search_queries": ["query1", "query2", ...]
}}
```

不要输出任何额外的解释性文本，仅输出 JSON。"""


async def node_1_planning_extract(user_input: str) -> UserMenuConstraints:
    """
    Node 1: LLM 解析用户需求，提取结构化规划
    """
    logger.info(f"[Node 1] 开始规划提取: {user_input[:100]}...")
    
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": PLANNING_SYSTEM_PROMPT.format(user_input=user_input),
                },
            ],
            temperature=0.3,  # 降低随机性以获得稳定的结构化输出
        )
        
        json_str = response.choices[0].message.content
        
        # 提取 JSON 部分（处理可能的 markdown 代码块）
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        constraints_dict = json.loads(json_str)
        constraints = UserMenuConstraints(**constraints_dict)
        
        logger.info(f"[Node 1] 规划提取完成: {len(constraints.search_queries)} 个搜索词")
        return constraints
        
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"[Node 1] 规划提取失败: {e}")
        raise ValueError(f"LLM 输出不符合 Schema: {e}")


# ======================== Node 2: 并发检索 ========================

async def node_2_concurrent_retrieval(
    queries: List[str],
) -> tuple[List[RetrievedRecipe], List[dict]]:
    """
    Node 2: 并发多路检索，支持瀑布流降级
    """
    logger.info(f"[Node 2] 开始并发检索: {len(queries)} 个查询词")
    
    try:
        success_results, failed_queries = await retrieve_recipes(queries)
        logger.info(
            f"[Node 2] 检索完成: {len(success_results)} 成功, "
            f"{len(failed_queries)} 失败"
        )
        return success_results, failed_queries
    except CaptchaDetectedError as e:
        logger.error(f"[Node 2] 验证码熔断: {e}")
        return [], [{"query": "all", "reason": "captcha_detected"}]
    except Exception as e:
        logger.error(f"[Node 2] 检索异常: {e}")
        return [], [{"query": "all", "reason": str(e)}]


# ======================== Node 3: 菜谱生成 ========================

CHEF_SYSTEM_PROMPT = """# ROLE
你是一位拥有严密逻辑和极高厨艺水准的米其林行政总厨。你不仅精通烹饪，更是一位"库存管理大师"。

# CURRENT STATE
- 你的核心食材库存：{available_ingredients}（注意看清具体的数量/重量！）
- 就餐人数：{portion_size}
- 用户的全局宏观预期：{global_requests}
- 绝对红线（忌口）：{allergies_and_dislikes}

# REFERENCE DATA
- 下游系统为你找来的参考菜谱灵感：{retrieved_data}

# RULES & CONSTRAINTS

你现在需要设计一套最终的菜单（Meal Plan），你必须严格遵循以下纪律：

1.【绝对零库存超发 (Zero Over-Allocation) - 核心红线】
- 仔细阅读每一项食材的 quantity。
- 如果库存只有 "5个土豆"，你设计的这顿饭里，所有菜品消耗的土豆总和，绝对不可以超过5个！
- 允许你适当保留库存（不用完），但绝不允许凭空变出食材。

2.【参考灵感的去粗取精 (Inspiration Filtering)】
- 参考数据可能包含与用户忌口冲突的内容。你必须像用显微镜一样审查它们，果断剔除任何包含忌口的配方。
- 提取参考数据中最有价值的"酱汁调配比例"和"火候技巧"，融入到你的最终输出中。

3.【全局统筹验证 (Macro Alignment)】
- 回顾 global_requests。如果用户要求"一荤一素"，你的最终菜谱列表中必须明确体现出这个结构。

4.【🌟 强制自我审计机制 (Self-Audit required in plan_summary)】
- 在输出的最开始，你必须向用户汇报你的"算账逻辑"。
- 汇报范例："为了满足您2菜1汤的需求，我做如下分配：5个土豆中，3个用于做干锅土豆片，剩余2个打泥做土豆浓汤；半斤五花肉全部用于干锅中。口味上保证了一辣一咸鲜，完美契合。"

# OUTPUT FORMAT
使用 Markdown 格式输出。
第一部分必须为 ### 👨‍🍳 总厨算账总结，向用户解释你如何分配库存以满足需求。
随后列出每一道菜的结构：
### [菜名]
#### 精确用料
- 食材1：数量
- 食材2：数量
...
#### 烹饪步骤
1. 步骤1
2. 步骤2
...

不要输出 JSON 格式，直接用 Markdown。"""


async def node_3_generate_meal_plan_stream(
    constraints: UserMenuConstraints,
    retrieved_recipes: List[RetrievedRecipe],
) -> AsyncGenerator[str, None]:
    """
    Node 3: 使用流式 API 生成菜谱，逐块 yield 文本
    """
    logger.info("[Node 3] 开始生成菜谱计划...")
    
    # 格式化食材和参考数据
    ingredients_str = json.dumps(
        [
            {"name": ing.name, "quantity": ing.quantity}
            for ing in constraints.available_ingredients
        ],
        ensure_ascii=False,
        indent=2,
    )
    
    retrieved_data_str = json.dumps(
        [
            {
                "title": r.title,
                "ingredients": r.ingredients,
                "instructions": r.instructions_or_snippet,
                "source": r.source_strategy.value,
            }
            for r in retrieved_recipes[:5]  # 仅保留前5条参考
        ],
        ensure_ascii=False,
        indent=2,
    )
    
    prompt = CHEF_SYSTEM_PROMPT.format(
        available_ingredients=ingredients_str,
        portion_size=constraints.portion_size,
        global_requests=constraints.global_requests,
        allergies_and_dislikes=", ".join(constraints.allergies_and_dislikes)
        if constraints.allergies_and_dislikes
        else "无",
        retrieved_data=retrieved_data_str,
    )
    
    try:
        async with client.messages.stream(
            model=MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": "请根据上述信息生成最优的菜单计划",
                }
            ],
            system=prompt,
        ) as stream:
            async for text_chunk in stream.text_stream:
                yield text_chunk
                logger.debug(f"[Node 3] 流 chunk: {text_chunk[:50]}...")
                
    except Exception as e:
        logger.error(f"[Node 3] 菜谱生成失败: {e}")
        raise


# ======================== 完整流程编排 ========================

async def process_agent_stream(
    user_input: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    完整的三阶段 Agent 流程，通过 yield 推送 SSE 事件
    
    事件序列：
    1. planning_done: UserMenuConstraints
    2. retrieval_update: {"query": str, "status": "success|fail"}
    3. recipe_stream: {"chunk": str}
    4. recipe_done: (可选) MealPlan JSON
    """
    
    try:
        # ===== Node 1: 规划提取 =====
        logger.info("[Agent] 启动三阶段流程...")
        
        constraints = await node_1_planning_extract(user_input)
        
        yield {
            "event": "planning_done",
            "data": constraints.model_dump(),
        }
        
        # ===== Node 2: 并发检索 =====
        retrieved_recipes, failed_queries = await node_2_concurrent_retrieval(
            constraints.search_queries
        )
        
        # 推送检索进度更新
        for query in constraints.search_queries:
            is_success = any(r.source_query == query for r in retrieved_recipes)
            yield {
                "event": "retrieval_update",
                "data": {
                    "query": query,
                    "status": "success" if is_success else "fail",
                },
            }
        
        # ===== Node 3: 菜谱生成（流式） =====
        full_recipe_text = ""
        
        async for chunk in node_3_generate_meal_plan_stream(
            constraints, retrieved_recipes
        ):
            yield {
                "event": "recipe_stream",
                "data": {"chunk": chunk},
            }
            full_recipe_text += chunk
        
        logger.info("[Agent] 三阶段流程完成")
        
    except Exception as e:
        logger.error(f"[Agent] 处理异常: {e}")
        yield {
            "event": "error",
            "data": {"message": str(e)},
        }
