"""
项目架构文档
"""

# 美食排菜 Agent - 项目架构

## 文件结构

```
cook-agent/
├── .env.example              # 环境变量配置模板（【必须】复制为 .env）
├── .gitignore                # Git 忽略文件
├── requirements.txt          # Python 依赖清单
│
├── models.py                 # ✨ Pydantic v2 数据模型
│   ├── IngredientItem        # 单个食材
│   ├── UserMenuConstraints   # Node 1 输出：规划约束
│   ├── RetrievedRecipe       # Node 2 输出：检索结果
│   ├── MealPlan              # Node 3 输出：菜谱计划
│   └── SSEEvent              # SSE 事件定义
│
├── retrieval.py              # 🔍 多策略检索瀑布流
│   ├── MCPRetrievalStrategy     # 策略1：小红书 MCP
│   ├── SchemaExtractionStrategy # 策略2：网站 JSON-LD Schema
│   ├── BingSearchStrategy       # 策略3：Bing 搜索
│   ├── PlaywrightStrategy       # 策略4：动态爬取
│   ├── FallbackRetriever        # 瀑布流编排器
│   └── retrieve_recipes()       # 便捷函数
│
├── agent.py                  # 🧠 AI 编排核心
│   ├── node_1_planning_extract()           # Node 1：LLM 规划提取
│   ├── node_2_concurrent_retrieval()       # Node 2：并发检索
│   ├── node_3_generate_meal_plan_stream()  # Node 3：流式菜谱生成
│   └── process_agent_stream()              # 完整流程：三阶段编排 + SSE
│
├── main.py                   # 🌐 FastAPI 后端服务
│   ├── /health               # 健康检查
│   └── /api/v1/stream_meal_plan  # ✨ 核心 API：SSE 流式端点
│
├── app.py                    # 🎨 Streamlit 前端应用
│   ├── 侧边栏                  # API 配置、关于
│   ├── 输入区域                # 用户需求文本框
│   └── 进度展示                # 3 个折叠面板 (Node 1/2/3)
│
├── QUICKSTART.md             # 📖 快速开始指南
├── README.md                 # 📚 完整文档
├── ARCHITECTURE.md           # 📐 本文件
│
├── start.bat                 # 🚀 Windows 启动脚本
├── start.sh                  # 🚀 Linux/Mac 启动脚本
├── test_workflow.py          # 🧪 工作流测试
│
└── .vscode/
    ├── tasks.json            # VS Code 任务定义
    └── settings.json         # VS Code 设置
```

## 核心工作流（三阶段）

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面 (Streamlit)                      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📝 输入: "我有5个土豆、半斤五花肉，要做2菜不吃辣"              │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP GET /api/v1/stream_meal_plan
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI 后端 (main.py)                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ event_generator(user_input) → StreamingResponse (SSE)      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                             │
│  ┌──────────────────────────▼──────────────────────────────────┐ │
│  │  process_agent_stream(user_input) [agent.py]               │ │
│  │                                                             │ │
│  │  ╔═══════════════════════════════════════════════════════╗ │ │
│  │  ║ Node 1: 规划提取 [node_1_planning_extract]            ║ │ │
│  │  ║ ─────────────────────────────────────────────────────║ │ │
│  │  ║ Input:  "我有5个土豆、半斤五花肉，要做2菜不吃辣"        ║ │ │
│  │  ║ LLM:    OpenAI GPT-4 Turbo (Structured Output)       ║ │ │
│  │  ║ Output: UserMenuConstraints {                        ║ │ │
│  │  ║   available_ingredients: [土豆 5个, 五花肉 250g],    ║ │ │
│  │  ║   allergies_and_dislikes: [辣],                      ║ │ │
│  │  ║   search_queries: [6-8个搜索词]                      ║ │ │
│  │  ║ }                                                    ║ │ │
│  │  ║ Yield: planning_done event                           ║ │ │
│  │  ╚═══════════════════════════════════════════════════════╝ │ │
│  │                           │                                 │ │
│  │  ╔═══════════════════════▼════════════════════════════════╗ │ │
│  │  ║ Node 2: 并发检索 [node_2_concurrent_retrieval]        ║ │ │
│  │  ║ ─────────────────────────────────────────────────────║ │ │
│  │  ║ queries: [6-8个搜索词]                                ║ │ │
│  │  ║ Fallback Cascade:                                    ║ │ │
│  │  ║   1. MCP (小红书) → 2. Schema (下厨房) →             ║ │ │
│  │  ║   3. Bing → 4. Playwright (动态爬取)                 ║ │ │
│  │  ║ Output: RetrievedRecipe[] (4-5条参考菜谱)            ║ │ │
│  │  ║ Yield: retrieval_update 事件 (逐个查询进度)            ║ │ │
│  │  ╚═══════════════════════════════════════════════════════╝ │ │
│  │                           │                                 │ │
│  │  ╔═══════════════════════▼════════════════════════════════╗ │ │
│  │  ║ Node 3: 菜谱生成 [node_3_generate_meal_plan_stream]   ║ │ │
│  │  ║ ─────────────────────────────────────────────────────║ │ │
│  │  ║ Input:                                               ║ │ │
│  │  ║   - available_ingredients (食材库存)                 ║ │ │
│  │  ║   - retrieved_recipes (参考菜谱)                    ║ │ │
│  │  ║   - global_requests (宏观需求: 2菜1汤)              ║ │ │
│  │  ║   - allergies_and_dislikes (忌口: 辣)               ║ │ │
│  │  ║ LLM: OpenAI (stream=True)                            ║ │ │
│  │  ║ Prompt: 行政总厨角色，执行库存精准分配和菜谱生成     ║ │ │
│  │  ║ Output: Markdown 格式菜谱 (实时流)                  ║ │ │
│  │  ║ Yield: recipe_stream 事件 (逐块文本流)                ║ │ │
│  │  ╚═══════════════════════════════════════════════════════╝ │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  SSE 事件序列:                                                   │
│  data: {"event": "planning_done", "data": {...}}               │
│  data: {"event": "retrieval_update", "data": {...}}            │
│  data: {"event": "recipe_stream", "data": {"chunk": "..."}}    │
└─────────────────────────────────────────────────────────────────┘
                             │ SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    前端 (Streamlit - app.py)                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ [status "Node 1: 规划提取"]                                  │ │
│ │ ✅ 食材：土豆 5个，五花肉 250g                                │ │
│ │ 🚫 忌口：辣                                                   │ │
│ │ 搜索词：6个                                                   │ │
│ │                                                              │ │
│ │ [status "Node 2: 检索菜谱"]                                  │ │
│ │ ✅ 土豆番茄清淡做法                                           │ │
│ │ ✅ 五花肉豆角咸香                                             │ │
│ │ ❌ 水煮鱼 (不符合)                                            │ │
│ │                                                              │ │
│ │ [status "Node 3: 生成菜单"]                                  │ │
│ │ ### 👨‍🍳 总厨算账总结                                        │ │
│ │ 为了满足您2菜1汤的需求，我做如下分配：...                    │ │
│ │                                                              │ │
│ │ ### 番茄土豆汤                                                │ │
│ │ #### 精确用料                                                │ │
│ │ - 番茄：2个                                                  │ │
│ │ - 土豆：3个                                                  │ │
│ │ #### 烹饪步骤                                                │ │
│ │ 1. 番茄冷水下锅...                                           │ │
│ │ ...                                                          │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 关键设计决策

### 1️⃣ 为什么采用 SSE 而不是 WebSocket？

- **SSE 优势**:
  - ✅ HTTP/1.1 标准，无需额外协议升级
  - ✅ 自动重连机制
  - ✅ Streamlit 原生支持
  - ✅ FastAPI 轻松支持 (StreamingResponse)

- **缺点**:
  - ❌ 单向通信（前端无法直接发送消息，需重新请求）
  - ❌ 某些企业防火墙可能不支持

### 2️⃣ 为什么采用四层瀑布流而不是单一策略？

- **鲁棒性**: 任何单一策略失败都不会影响整体
- **覆盖广**: MCP 获取原始数据，Playwright 覆盖动态网站
- **成本低**: Bing 比爬虫更便宜，优先使用
- **防反爬**: Playwright 验证码熔断，不会陷入死循环

### 3️⃣ 为什么使用 Pydantic v2 而不是其他验证库？

- ✅ **结构化输出**: 直接配合 OpenAI Structured Output
- ✅ **类型安全**: 自动类型检查和转换
- ✅ **JSON 序列化**: 完美支持 SSE 事件推送
- ✅ **文档生成**: 自动生成 FastAPI 文档

### 4️⃣ 为什么将"库存精算"放在 Node 3 而不是 Node 1？

- **原因 1**: Node 3 有参考菜谱，能做出基于真实菜谱的分配
- **原因 2**: Node 3 是生成最终菜单的地方，确保一致性
- **原因 3**: 通过 Self-Audit 向用户说明分配逻辑

### 5️⃣ 为什么 Streamlit 前端而不是 React？

- ✅ **快速开发**: 无需前端框架学习，纯 Python
- ✅ **原生 SSE 支持**: `requests.stream` 原生支持
- ✅ **组件丰富**: 表格、图表、状态管理都有
- ✅ **部署简单**: 单个 Python 文件即可运行

## 运行时依赖关系

```
app.py (Streamlit 前端)
  │
  └─→ requests.stream (连接 SSE)
       │
       └─→ main.py (FastAPI 后端)
            │
            ├─→ agent.py (编排逻辑)
            │    │
            │    ├─→ Node 1: 调用 OpenAI (结构化输出)
            │    ├─→ Node 2: 调用 retrieval.py
            │    └─→ Node 3: 调用 OpenAI (流式)
            │
            └─→ retrieval.py (多策略检索)
                 │
                 ├─→ MCP SDK (需配置 XHS_COOKIE)
                 ├─→ httpx + BeautifulSoup4 (Schema 提取)
                 ├─→ Bing Search API (需 API Key)
                 └─→ Playwright + stealth (动态爬取)
```

## 环境变量配置

### 必需
- `OPENAI_API_KEY`: OpenAI API Key

### 推荐
- `BING_SEARCH_API_KEY`: Bing 搜索 API Key

### 可选
- `XHS_COOKIE`: 小红书 Cookie (MCP)
- `A1`: 小红书 A1 Token (MCP)

## 错误处理策略

```
Node 1 错误 (规划提取失败)
  └─→ 直接返回错误事件给前端，无降级
      (规划是基础，无法跳过)

Node 2 错误 (检索失败)
  ├─→ 单个查询失败 → 标记为失败，继续下一个
  ├─→ 验证码熔断 → 立即停止爬取，其他策略可继续
  └─→ 所有查询失败 → 通知 Node 3 使用空参考数据

Node 3 错误 (菜谱生成失败)
  └─→ 返回错误事件给前端，中断流程
```

## 性能优化点

1. **Node 1**: 使用 `temperature=0.3` 降低随机性
2. **Node 2**: `asyncio.gather()` 限制并发为 3
3. **Node 3**: 流式推送，避免等待完整生成

## 扩展点

### 新增检索策略

在 `retrieval.py` 中添加新类：

```python
class MyNewStrategy(RetrievalStrategy_ABC):
    async def retrieve(self, query: str) -> Optional[RetrievedRecipe]:
        # 实现检索逻辑
        pass

# 在 FallbackRetriever.__init__ 中添加
self.strategies.append(MyNewStrategy())
```

### 自定义提示词

编辑 `agent.py` 中的全局常量：
- `PLANNING_SYSTEM_PROMPT`: Node 1 规划提示词
- `CHEF_SYSTEM_PROMPT`: Node 3 菜谱生成提示词

### 集成新的 LLM

修改 `agent.py`：
```python
# 改用其他 LLM (如 Claude, Gemini)
client = SomeOtherLLMClient()
```

## 测试策略

### 单元测试
```bash
pytest tests/test_models.py      # 数据模型测试
pytest tests/test_retrieval.py   # 检索策略测试
pytest tests/test_agent.py       # Agent 逻辑测试
```

### 集成测试
```bash
python test_workflow.py          # 完整工作流测试
```

### 端到端测试
```bash
# 终端1: 启动后端
python main.py

# 终端2: 启动前端
streamlit run app.py

# 浏览器测试
open http://localhost:8501
```

---

**架构文档版本**: 1.0  
**最后更新**: 2024-03-29  
**维护者**: AI Assistant
