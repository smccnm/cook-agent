"""
Streamlit 前端应用 - 流式交互界面
"""
import json
import logging
import os
import requests
import streamlit as st
from typing import Generator

# 配置页面
st.set_page_config(
    page_title="🍳 美食排菜 Agent",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 后端 API 地址
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_ENDPOINT = f"{BACKEND_URL}/api/v1/stream_meal_plan"


# ======================== 页面样式 ========================

st.markdown("""
<style>
    .title-container {
        text-align: center;
        margin-bottom: 30px;
    }
    .section-header {
        border-bottom: 2px solid #FF6B35;
        padding-bottom: 10px;
        margin-top: 20px;
    }
    .info-box {
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ======================== 侧边栏配置 ========================

with st.sidebar:
    st.header("⚙️ 配置")
    
    st.markdown("### API 配置")
    api_url = st.text_input(
        "后端 API 地址",
        value=BACKEND_URL,
        help="FastAPI 后端服务地址"
    )
    
    st.markdown("### 提示词优化")
    use_custom_prompt = st.checkbox("使用自定义提示词", value=False)
    if use_custom_prompt:
        st.info("自定义提示词功能开发中...")
    
    st.markdown("### 关于")
    st.markdown("""
    **美食排菜 Agent v1.0**
    
    - 🤖 三阶段 AI 编排
    - 🔗 多策略检索瀑布流
    - 📡 SSE 流式推送
    - 📊 库存精准计算
    """)


# ======================== 主界面 ========================

col_header = st.container()
with col_header:
    st.markdown("""
    <div class="title-container">
        <h1>🍳 美食排菜 Agent</h1>
        <p style="font-size: 18px; color: #666;">
            输入您的食材和需求，AI 将为您规划最优菜单
        </p>
    </div>
    """, unsafe_allow_html=True)


# ======================== 输入区域 ========================

st.markdown("### 📝 您的需求")

user_input = st.text_area(
    "请描述您的食材和排菜需求（例如：我有5个土豆、半斤五花肉、3个番茄，需要做2菜1汤，不吃辣）",
    height=100,
    placeholder="输入自然语言描述...",
    label_visibility="collapsed",
)

col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 2])

with col_btn1:
    submit_button = st.button("🚀 生成菜单", use_container_width=True)

with col_btn2:
    clear_button = st.button("🔄 清空", use_container_width=True)

with col_btn3:
    if st.button("💾 导出方案", use_container_width=True):
        st.info("导出功能开发中...")

if clear_button:
    st.rerun()


# ======================== 流式处理 ========================

if submit_button and user_input:
    try:
        # 创建展示容器
        with st.container():
            # Node 1: 规划提取
            with st.status("📋 **阶段 1: 规划提取**", expanded=True) as status_1:
                planning_placeholder = st.empty()
                planning_placeholder.info("正在解析您的需求...")
                planning_data = None
            
            # Node 2: 并发检索
            with st.status("🔍 **阶段 2: 检索菜谱**", expanded=True) as status_2:
                retrieval_placeholder = st.empty()
                retrieval_placeholder.info("正在从多个数据源检索菜谱...")
                retrieval_list = []
            
            # Node 3: 菜谱生成
            with st.status("👨‍🍳 **阶段 3: 生成菜单**", expanded=True) as status_3:
                recipe_container = st.container()
                recipe_text_placeholder = recipe_container.empty()
        
        # 连接后端 SSE
        logger.info(f"连接 API: {api_url}")
        
        try:
            response = requests.get(
                f"{api_url}/api/v1/stream_meal_plan",
                params={"user_input": user_input},
                stream=True,
                timeout=300,
            )
            response.raise_for_status()
            
            full_recipe_text = ""
            planning_done = False
            retrieval_queries_processed = set()
            
            # 逐行读取 SSE 事件
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    # 解析 SSE 格式
                    if line.startswith("data: "):
                        json_str = line[6:]  # 移除 "data: " 前缀
                        event_data = json.loads(json_str)
                        
                        event_type = event_data.get("event")
                        event_body = event_data.get("data", {})
                        
                        # ===== Node 1: 规划完成 =====
                        if event_type == "planning_done":
                            planning_data = event_body
                            
                            with planning_placeholder.container():
                                st.success("✅ 规划提取完成！")
                                with st.expander("📊 规划详情"):
                                    if isinstance(planning_data, dict):
                                        st.json(planning_data)
                            
                            planning_done = True
                            status_1.update(label="✅ 阶段 1: 规划提取 (完成)", state="complete")
                        
                        # ===== Node 2: 检索更新 =====
                        elif event_type == "retrieval_update":
                            query = event_body.get("query")
                            status = event_body.get("status")
                            
                            if query and query not in retrieval_queries_processed:
                                retrieval_queries_processed.add(query)
                                retrieval_list.append({
                                    "query": query,
                                    "status": status
                                })
                                
                                with retrieval_placeholder.container():
                                    for item in retrieval_list:
                                        status_icon = "✅" if item["status"] == "success" else "❌"
                                        st.text(f"{status_icon} {item['query']}")
                        
                        # ===== Node 3: 菜谱流 =====
                        elif event_type == "recipe_stream":
                            chunk = event_body.get("chunk", "")
                            full_recipe_text += chunk
                            
                            with recipe_text_placeholder.container():
                                st.markdown(full_recipe_text)
                        
                        # ===== 完成 =====
                        elif event_type == "recipe_done":
                            status_3.update(label="✅ 阶段 3: 生成菜单 (完成)", state="complete")
                        
                        # ===== 错误 =====
                        elif event_type == "error":
                            error_msg = event_body.get("message", "未知错误")
                            st.error(f"❌ 发生错误: {error_msg}")
                
                except json.JSONDecodeError:
                    logger.warning(f"无法解析 SSE 行: {line}")
                    continue
            
            # 最终状态更新
            if not planning_done:
                status_1.update(label="❌ 阶段 1: 规划提取 (失败)", state="error")
            
            if not retrieval_list:
                status_2.update(label="⚠️ 阶段 2: 检索菜谱 (无结果)", state="running")
            else:
                status_2.update(label="✅ 阶段 2: 检索菜谱 (完成)", state="complete")
            
            if full_recipe_text:
                status_3.update(label="✅ 阶段 3: 生成菜单 (完成)", state="complete")
                
                # 提供下载按钮
                st.markdown("---")
                st.markdown("### 📥 导出菜单")
                
                col_md, col_txt = st.columns(2)
                with col_md:
                    st.download_button(
                        label="下载 Markdown",
                        data=full_recipe_text,
                        file_name="meal_plan.md",
                        mime="text/markdown",
                    )
                
                with col_txt:
                    st.download_button(
                        label="下载文本",
                        data=full_recipe_text,
                        file_name="meal_plan.txt",
                        mime="text/plain",
                    )
        
        except requests.exceptions.ConnectionError:
            st.error(
                f"❌ 无法连接到后端服务\n\n"
                f"请确保后端服务已启动:\n"
                f"`python main.py`\n\n"
                f"API 地址: {api_url}"
            )
        except requests.exceptions.Timeout:
            st.error("❌ 请求超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ 请求失败: {e}")
    
    except Exception as e:
        st.error(f"❌ 处理异常: {e}")
        logger.exception(e)

elif submit_button and not user_input:
    st.warning("⚠️ 请输入您的需求")


# ======================== 底部帮助 ========================

st.markdown("---")

with st.expander("💡 使用提示"):
    st.markdown("""
    ### 🎯 最佳实践
    
    1. **详细描述食材**：包含具体数量
       - ✅ "我有5个土豆、250克五花肉、3个番茄"
       - ❌ "我有一些土豆和肉"
    
    2. **明确排菜需求**：说明要做多少道菜
       - ✅ "需要做2菜1汤，其中一道要辣，一道清淡"
       - ❌ "随便做点吃的"
    
    3. **注明忌口和偏好**：
       - ✅ "不吃辣、不吃海鲜、想要快手菜"
       - ❌ "随便"
    
    ### 🔧 技术细节
    
    - **实时更新**: 使用 SSE 推送实时进度
    - **三阶段流程**: 规划 → 检索 → 生成
    - **多源检索**: 支持 MCP、Schema、Bing、Playwright 四层降级
    - **库存精算**: 确保菜单不超出食材库存
    """)


with st.expander("📞 故障排除"):
    st.markdown("""
    ### 常见问题
    
    **Q: 显示"无法连接到后端"**
    - 确保已启动后端: `python main.py`
    - 检查 API 地址是否正确
    - 检查防火墙设置
    
    **Q: 请求超时**
    - 这可能需要 30-60 秒，请耐心等待
    - 检查网络连接
    
    **Q: 菜单包含我的忌口食材**
    - 请重新检查您的输入是否清晰描述了忌口
    - 尝试使用"不吃...""过敏..."等更明确的表述
    
    ### 📋 日志
    """)
    
    if st.checkbox("显示实时日志"):
        st.code("日志功能开发中...", language="text")
