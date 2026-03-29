# 🍳 美食排菜 Agent - 快速参考卡

## ⚡ 30 秒快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 2. 一键启动
start.bat              # Windows
# 或
bash start.sh          # Linux/Mac

# 3. 打开浏览器
open http://localhost:8501
```

---

## 🎯 核心概念

```
用户输入 (食材 + 需求)
    ↓
┌─────────────────────────────┐
│ Node 1: LLM 规划提取        │  ← 提取食材、忌口、搜索词
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Node 2: 并发多源检索        │  ← MCP → Schema → Bing → Playwright
└─────────────────────────────┘
    ↓
┌─────────────────────────────┐
│ Node 3: LLM 菜谱生成        │  ← 精准分配库存，生成菜单
└─────────────────────────────┘
    ↓
完整菜谱 (流式推送到前端)
```

---

## 🌐 服务地址

| 服务 | 地址 |
|------|------|
| **前端** | http://localhost:8501 |
| **后端 API** | http://localhost:8000 |
| **API 文档** | http://localhost:8000/docs |

---

## 📝 典型用户输入

```
我家里有：5个土豆、250克五花肉、3个番茄、半斤豆角
今晚4个人吃饭，想做2菜1汤
我不吃辣，想要清淡的味道
请帮我规划一下
```

系统输出：
```
### 👨‍🍳 总厨算账总结
为了满足您4人、2菜1汤的需求，我做如下分配：
...

### 番茄土豆汤
#### 精确用料
- 番茄：2个
- 土豆：3个
...

### 五花肉炒豆角
...
```

---

## 🔧 常见任务

### 启动后端
```bash
python main.py
```
访问 http://localhost:8000/docs 查看 API 文档

### 启动前端
```bash
streamlit run app.py
```
自动打开 http://localhost:8501

### 运行测试
```bash
python test_workflow.py
```

### 安装依赖
```bash
pip install -r requirements.txt
```

---

## 🛠️ 环境变量速查

```env
# 必需
OPENAI_API_KEY=sk-xxx...

# 推荐
BING_SEARCH_API_KEY=xxx...

# 可选（小红书 MCP）
XHS_COOKIE=xxx...
A1=xxx...

# 服务地址
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_URL=http://localhost:8000
```

---

## 📊 工作流时间

| 阶段 | 耗时 |
|-----|------|
| Node 1 规划 | 3-5 秒 |
| Node 2 检索 | 10-30 秒 |
| Node 3 生成 | 5-10 秒 |
| **总计** | **20-45 秒** |

---

## ❌ 常见问题速解

| 问题 | 解决 |
|-----|------|
| 无法连接后端 | `python main.py` 启动后端 |
| API Key 错误 | 编辑 `.env`，检查 `OPENAI_API_KEY` |
| MCP 未启用 | 正常，会自动降级到其他策略 |
| 请求超时 | 等待 30-60 秒，或检查网络 |
| 验证码熔断 | 正常防反爬机制，系统会尝试其他策略 |

---

## 📂 文件速查

```
models.py       - 数据模型
retrieval.py    - 检索瀑布流
agent.py        - AI 编排逻辑
main.py         - FastAPI 后端
app.py          - Streamlit 前端
```

---

## 🎓 学习路径

```
初级: QUICKSTART.md      (5 分钟快速上手)
中级: README.md          (功能全览)
高级: ARCHITECTURE.md    (系统设计)
专家: 源代码注释         (深入理解)
```

---

## 🚀 API 端点

### SSE 流式菜单规划
```
GET /api/v1/stream_meal_plan?user_input=我有5个土豆...

响应示例：
data: {"event": "planning_done", "data": {...}}
data: {"event": "retrieval_update", "data": {"query": "...", "status": "success"}}
data: {"event": "recipe_stream", "data": {"chunk": "### 菜名"}}
```

### 健康检查
```
GET /health

响应：
{"status": "ok", "service": "meal-plan-agent"}
```

---

## 💡 最佳实践

### ✅ 好的输入
```
我有5个中等土豆、250克五花肉、3个番茄
4个人吃饭，做2菜1汤
不吃辣，要清淡
```

### ❌ 不好的输入
```
我有一些土豆和肉
随便做点吃的
有些忌口
```

---

## 🔍 调试模式

在 `.env` 中设置：
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

然后启动服务，查看详细日志。

---

## 📱 前端功能速览

| 功能 | 说明 |
|------|------|
| **输入框** | 输入您的食材和需求 |
| **Node 1 面板** | 显示提取的食材和搜索词 |
| **Node 2 面板** | 显示检索进度 |
| **Node 3 面板** | 流式显示生成的菜谱 |
| **下载按钮** | 导出菜谱为 Markdown/Text |

---

## 🔐 API Key 获取

### OpenAI
1. 访问 https://platform.openai.com/api-keys
2. 登录账号
3. Create new secret key
4. 复制到 `.env` 的 `OPENAI_API_KEY`

### Bing Search
1. 访问 https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
2. 申请订阅
3. 获取 API Key
4. 复制到 `.env` 的 `BING_SEARCH_API_KEY`

---

## 🎉 项目特色

- ✅ **全局资源分配** - 库存精准计算
- ✅ **多源数据** - 四层检索瀑布流
- ✅ **流式交互** - 实时推送进度
- ✅ **AI 编排** - 三阶段 LLM 流程
- ✅ **开发友好** - 完整文档和示例

---

## 📞 获取帮助

- **快速问题**: 查看 `QUICKSTART.md`
- **架构问题**: 查看 `ARCHITECTURE.md`
- **API 问题**: 访问 http://localhost:8000/docs
- **其他**: 查看 `README.md`

---

## 📚 文档导航

```
QUICKSTART.md      ← 开始这里 (5 分钟)
    ↓
README.md          ← 了解全部功能
    ↓
ARCHITECTURE.md    ← 深入理解设计
    ↓
源代码注释         ← 专家级学习
```

---

## ✨ 快速示例

### 示例 1: 晚餐规划
```
输入: 5个土豆, 250g五花肉, 3个番茄, 不吃辣, 4人, 2菜1汤
输出: ✅ 番茄土豆汤
      ✅ 五花肉炒豆角
      (详细菜谱...)
```

### 示例 2: 快手菜
```
输入: 番茄2个, 鸡蛋2个, 黄瓜2根, 5分钟
输出: ✅ 番茄炒蛋
      ✅ 清炒黄瓜
```

### 示例 3: 减脂餐
```
输入: 鸡胸肉200g, 西兰花, 减脂, 高蛋白
输出: ✅ 清蒸鸡胸肉
      ✅ 清炒西兰花
      (营养分析...)
```

---

## 🎯 下一步

1. ✅ 配置 `.env` 文件
2. ✅ 启动服务 (`start.bat` 或 `start.sh`)
3. ✅ 打开 http://localhost:8501
4. ✅ 输入您的食材和需求
5. ✅ 享受 AI 生成的菜谱！

---

**Made with ❤️ by AI Assistant**  
**快速参考版本**: 1.0  
**最后更新**: 2024-03-29
