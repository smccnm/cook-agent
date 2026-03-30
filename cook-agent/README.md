# Cook Agent

全局统筹私人排菜 Agent，包含：

1. `Node 1` 统筹规划
2. `Node 2` 多策略检索瀑布流
3. `Node 3` 流式总厨生成

后端使用 FastAPI + SSE，前端使用 Streamlit。

## 当前默认能力

- 主模型：Gemini
- 兜底：本地规则规划与本地规则菜单生成
- 检索瀑布流：
  - Xiaohongshu MCP 本地服务
  - Schema JSON-LD 提取
  - Bing 搜索摘要
  - Playwright 动态后备

## 小红书登录

应用支持手动登录小红书：

1. 启动后端与前端
2. 在 Streamlit 侧边栏点击“打开小红书登录窗口”
3. 在弹出的官方登录窗口中手动登录
4. 点击“刷新登录状态”
5. 登录成功后，应用会同步本地 cookies，并可启动本地 xiaohongshu-mcp 服务

## 快速开始

### Windows

```powershell
start.bat
```

### Linux / macOS

```bash
./start.sh
```

## 手动启动

```powershell
pip install -r requirements.txt
python main.py
streamlit run app.py
```

## 关键环境变量

见 `.env.example`，重点包括：

- `GEMINI_API_KEY`
- `GEMINI_PLANNING_MODEL`
- `GEMINI_GENERATION_MODEL`
- `BING_SEARCH_API_KEY`
- `XHS_COOKIE`
- `A1`
- `XHS_MCP_BINARY_PATH`
- `XHS_LOGIN_BINARY_PATH`
- `XHS_COOKIES_PATH`

## 测试

```powershell
pytest tests/test_settings_and_models.py tests/test_planning.py tests/test_retrieval.py tests/test_generation.py tests/test_api.py tests/test_stream_client.py tests/test_xhs_service.py -q -p no:cacheprovider
python -m py_compile settings.py xhs_service.py planning.py generation.py retrieval.py agent.py main.py stream_client.py app.py tests/test_settings_and_models.py tests/test_planning.py tests/test_retrieval.py tests/test_generation.py tests/test_api.py tests/test_stream_client.py tests/test_xhs_service.py
```
