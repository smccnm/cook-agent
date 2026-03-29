# 🍳 美食排菜 Agent - 全局统筹私人排菜 AI 系统

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

> 🚀 一个具备全局资源分配能力、底层数据检索极度健壮的美食 Agent 后端服务，配套基于 Streamlit 的流式 Web 交互前端。

## 📋 项目概述

### 核心能力

- **🧠 三阶段 AI 编排**: Node 1 规划提取 → Node 2 并发检索 → Node 3 菜谱生成
- **🔗 多策略检索瀑布流**: MCP → Schema提取 → Bing搜索 → Playwright爬取（四层降级）
- **📡 SSE 流式推送**: 实时推送规划、检索、生成进度
- **📊 库存精准计算**: 绝对零库存超发，完美消耗食材
- **🎨 现代化 Web 交互**: Streamlit 前端，打字机流式展示菜谱

### 业务场景

接收用户高度非结构化的自然语言输入（食材数量、排菜预期、忌口等），Agent 通过：

1. **LLM 意图理解** - 精准量化库存，推导搜索关键词
2. **并发多源检索** - 从官方数据、网站 Schema、搜索引擎等获取菜谱灵感
3. **智能菜单规划** - 融合参考数据，确保零库存超发，生成完美消耗菜单

## 🏗️ 技术栈

| 层级 | 技术选型 |
|-----|--------|
| **后端框架** | FastAPI 0.104+ |
| **前端框架** | Streamlit 1.28+ |
| **大模型** | OpenAI GPT-4 Turbo Preview |
| **网络爬虫** | Playwright + BeautifulSoup4 + httpx |
| **API集成** | Bing Search API |
| **协议** | MCP（小红书数据源） |
| **数据验证** | Pydantic v2 |
| **异步编程** | asyncio |

## 📦 快速开始

### 1️⃣ 环境准备

#### 克隆项目
```bash
cd d:/Appdata/Agent/cook-agent
```

#### 创建虚拟环境（推荐）
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

#### 安装依赖
```bash
pip install -r requirements.txt
```

### 2️⃣ 配置环境变量

复制 `.env.example` 为 `.env`，填入实际的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`，填入以下必要项：

```env
# OpenAI API 配置（必需）
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview

# Bing Search API（可选，建议配置以获得最佳检索效果）
BING_SEARCH_API_KEY=your_bing_search_api_key_here

# MCP 配置（可选，用于小红书数据源）
XHS_COOKIE=your_xiaohongshu_cookie_here
A1=your_a1_token_here

# 后端配置
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 前端配置
STREAMLIT_SERVER_PORT=8501
BACKEND_URL=http://localhost:8000
```

### 3️⃣ 启动服务

#### 终端 1: 启动后端服务
```bash
python main.py
```

后端将在 `http://localhost:8000` 启动
- API 文档: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/health`

#### 终端 2: 启动前端应用
```bash
streamlit run app.py
```

前端将在 `http://localhost:8501` 打开

## 🎯 使用示例

### 场景 1: 晚餐排菜

**用户输入:**
```
我家里有：5个中等土豆、250克五花肉、3个番茄、半斤豆角、1棵小白菜。
今晚要招待一家人4个人吃饭，想做2菜1汤。
我和爸爸不能吃辣，妈妈喜欢清淡。
请帮我规划一下怎么做最好吃～
```

**系统输出 (3阶段):**

1. **📋 阶段 1: 规划提取**
   - 提取食材：土豆 5个、五花肉 250g、番茄 3个、豆角 250g、白菜 1棵
   - 识别忌口：辣
   - 识别偏好：清淡
   - 生成搜索词 6 个：
     - 土豆 番茄 清淡做法
     - 不辣 地三鲜 少油版
     - 五花肉 豆角 咸香
     - ...

2. **🔍 阶段 2: 并发检索**
   - MCP 搜索 (未启用)
   - Schema 提取 (下厨房) ✅
   - Bing 搜索 ✅
   - Playwright 爬取 (超时)
   - 共获取 4 条参考菜谱

3. **👨‍🍳 阶段 3: 生成菜单**
   ```markdown
   ### 👨‍🍳 总厨算账总结
   
   为了满足您4人、2菜1汤的需求，我做如下分配：
   - 3个番茄 + 5个土豆 → **番茄土豆汤**
   - 250g五花肉 + 豆角 → **五花肉炒豆角**
   - 白菜 + 番茄 → **清汤白菜汤**（补充）
   
   这样不仅完美避开了辣，还能兼顾妈妈的清淡需求。
   
   ### 番茄土豆汤
   #### 精确用料
   - 番茄：2个（切块）
   - 土豆：3个（切块）
   - 清水：800ml
   - 盐：适量
   
   #### 烹饪步骤
   1. 番茄、土豆洗净切块
   2. ...
   ```

### 场景 2: 快手菜

**用户输入:**
```
只有2个番茄、1根黄瓜、2个鸡蛋，需要快速做1菜，要能下饭的
```

**系统输出:**
- 快速生成 2 道方案：番茄炒蛋、黄瓜鸡蛋汤

## 📡 API 文档

### SSE 流式端点

**GET** `/api/v1/stream_meal_plan`

#### 参数
```json
{
  "user_input": "string (required) - 用户的自然语言需求"
}
```

#### 响应 (SSE 事件流)

```
data: {"event": "planning_done", "data": {...UserMenuConstraints...}}

data: {"event": "retrieval_update", "data": {"query": "土豆番茄清淡做法", "status": "success"}}
data: {"event": "retrieval_update", "data": {"query": "...", "status": "fail"}}

data: {"event": "recipe_stream", "data": {"chunk": "### 番茄"}}
data: {"event": "recipe_stream", "data": {"chunk": "土豆汤\n"}}
...

data: {"event": "recipe_done", "data": {...MealPlan...}}
```

#### 示例
```bash
curl "http://localhost:8000/api/v1/stream_meal_plan?user_input=我有5个土豆和半斤五花肉"
```

## 🔍 多策略检索瀑布流详解

### 四层降级架构

```
查询词 (query)
  │
  ├─→ 策略 1: MCP (小红书爬虫)
  │   └─ 失败或超时? ↓
  │
  ├─→ 策略 2: Schema 提取 (下厨房、美食杰、豆果美食)
  │   └─ 无结果? ↓
  │
  ├─→ 策略 3: Bing 搜索 (site:xiaohongshu.com)
  │   └─ 无结果? ↓
  │
  └─→ 策略 4: Playwright 爬取 (带反爬熔断)
      └─ 验证码熔断 ❌ (停止本查询)
```

### 各策略特性

| 策略 | 优点 | 缺点 | 触发条件 |
|-----|-----|-----|---------|
| **MCP** | 原始数据、高质量 | 需要配置 Cookie | 环境变量齐全 |
| **Schema** | 结构化、速度快 | 需要网站支持 LD-JSON | MCP 失败 |
| **Bing** | 稳定、无爬虫限制 | 仅摘要 | Schema 无结果 |
| **Playwright** | 动态内容、覆盖广 | 易触发反爬验证码 | Bing 无结果 |

### 防反爬机制

- ✅ **User-Agent 随机化**: `fake-useragent` 库
- ✅ **动作延迟**: `asyncio.sleep(random.uniform(1.5, 4.3))`
- ✅ **Stealth 注入**: 隐藏 `navigator.webdriver` 标识
- ✅ **验证码熔断**: 检测到 `secsdk-captcha` 或 `verify-bar` 立即停止

## 📊 数据模型

### Node 1: UserMenuConstraints
```python
{
  "available_ingredients": [
    {"name": "土豆", "quantity": "5个"},
    {"name": "五花肉", "quantity": "250g"}
  ],
  "allergies_and_dislikes": ["辣"],
  "portion_size": 4,
  "flavor_preferences": ["清淡"],
  "global_requests": "2菜1汤",
  "search_queries": ["土豆番茄清淡做法", "五花肉豆角咸香", ...]
}
```

### Node 3: MealPlan (生成结果)
```markdown
### 👨‍🍳 总厨算账总结
[库存分配说明]

### [菜名1]
#### 精确用料
- 食材: 数量
#### 烹饪步骤
1. 步骤1
2. 步骤2
```

## 🛠️ 项目结构

```
cook-agent/
├── requirements.txt          # 依赖清单
├── .env.example              # 环境变量模板（必须配置！）
├── models.py                 # Pydantic 数据模型 (Node 1/2/3)
├── retrieval.py              # 多策略检索瀑布流 (Node 2)
├── agent.py                  # AI 编排核心逻辑 (Node 1/2/3)
├── main.py                   # FastAPI 后端服务
├── app.py                    # Streamlit 前端应用
└── README.md                 # 本文件
```

## ⚙️ 核心实现细节

### Node 1: 规划提取提示词

系统提示词使用"三维度混合搜索词生成":

1. **维度一**: 原始食材两两/三三组合 + 烹饪目的
   - 例: "土豆 茄子 神仙吃法 减脂"

2. **维度二**: 经典菜名 + 修饰词
   - 例: "少油版 地三鲜", "空气炸锅 地三鲜"

3. **维度三**: 宏观场景词
   - 例: "快手 纯素菜 清淡"

### Node 2: 并发检索编排

```python
asyncio.gather(
    retrieve_with_fallback(query1),
    retrieve_with_fallback(query2),
    retrieve_with_fallback(query3),
    ...
)
```

支持最多 3 个并发任务（可调整）

### Node 3: 库存管理红线

**绝对零库存超发规则：**

```
用户库存: 土豆 5个
所有菜品消耗: 土豆 3个 + 土豆 2个 = 5个 ✅ (允许)
所有菜品消耗: 土豆 4个 + 土豆 2个 = 6个 ❌ (禁止)
```

系统提示词中明确要求总厨进行 **Self-Audit**，向用户汇报库存分配逻辑。

## 🐛 故障排除

### 问题 1: "无法连接到后端"
- 检查后端是否启动: `python main.py`
- 检查 API 地址: `http://localhost:8000`
- 检查防火墙

### 问题 2: "OPENAI_API_KEY not found"
- 确保 `.env` 文件存在且配置正确
- 检查 Python 是否已激活虚拟环境

### 问题 3: "MCP 策略未启用"
- MCP 为可选策略，可以没有 XHS_COOKIE 和 A1
- 系统会自动降级到其他策略

### 问题 4: "检测到验证码，熔断查询"
- 这是正常的反爬保护，系统会自动尝试其他策略
- 可以在 `.env` 中调整 `RANDOM_DELAY_MIN` 和 `RANDOM_DELAY_MAX` 来增加延迟

## 📈 性能指标

- **规划提取**: ~3-5 秒 (取决于 LLM 响应时间)
- **并发检索**: ~10-30 秒 (6-8 个查询词，考虑降级时间)
- **菜谱生成**: ~5-10 秒 (流式推送，实时显示)
- **总耗时**: ~20-45 秒

## 🚀 后续优化方向

- [ ] MCP 小红书 SDK 完整集成
- [ ] 动态料理时间计算（优化菜品搭配顺序）
- [ ] 营养成分分析（蛋白质、碳水、脂肪比例）
- [ ] 成本计算（按市价估算花费）
- [ ] 多语言支持（英文、日文等）
- [ ] 语音输入支持
- [ ] 历史菜单保存与智能推荐
- [ ] WebSocket 替代 SSE（更好的双向通信）

## 📝 许可证

MIT License

## 👨‍💻 开发指南

### 本地开发

```bash
# 启用代码热重载
python main.py  # FastAPI auto-reload enabled
streamlit run app.py --logger.level=debug
```

### 调试模式

```bash
# .env 中设置
DEBUG=true
LOG_LEVEL=DEBUG
```

### 单元测试（待实现）

```bash
pytest tests/
```

## 📚 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Streamlit 官方文档](https://docs.streamlit.io/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [MCP 官方文档](https://modelcontextprotocol.io/)

---

**Made with ❤️ by AI Assistant**

如有问题或建议，欢迎提交 Issue 或 Pull Request！
