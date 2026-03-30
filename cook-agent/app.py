"""Streamlit frontend for the streaming meal-plan workflow."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Generator

import requests
import streamlit as st

from stream_client import parse_sse_lines

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
STREAM_PATH = "/api/v1/stream_meal_plan"
XHS_LOGIN_START_PATH = "/api/v1/xhs/login/start"
XHS_LOGIN_STATUS_PATH = "/api/v1/xhs/login/status"
XHS_MCP_START_PATH = "/api/v1/xhs/mcp/start"

st.set_page_config(page_title="Cook Agent", page_icon="🍳", layout="wide")


def init_state() -> None:
    st.session_state.setdefault("input_text", "")
    st.session_state.setdefault("latest_input", "")
    st.session_state.setdefault("latest_result", "")
    st.session_state.setdefault("planning_data", None)
    st.session_state.setdefault("retrieval_updates", [])
    st.session_state.setdefault("last_error", "")
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("xhs_status", {})


def reset_current_result() -> None:
    st.session_state["latest_input"] = ""
    st.session_state["latest_result"] = ""
    st.session_state["planning_data"] = None
    st.session_state["retrieval_updates"] = []
    st.session_state["last_error"] = ""


def backend_post(api_url: str, path: str) -> dict:
    response = requests.post(f"{api_url}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def backend_get(api_url: str, path: str) -> dict:
    response = requests.get(f"{api_url}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def refresh_xhs_status(api_url: str) -> None:
    try:
        payload = backend_get(api_url, XHS_LOGIN_STATUS_PATH)
        st.session_state["xhs_status"] = payload.get("data", {})
    except Exception as exc:
        st.session_state["last_error"] = f"小红书登录状态获取失败: {exc}"


def render_xhs_controls(api_url: str) -> None:
    with st.sidebar:
        st.subheader("小红书")
        if st.button("打开小红书登录窗口", use_container_width=True):
            try:
                backend_post(api_url, XHS_LOGIN_START_PATH)
                st.success("已尝试打开登录窗口，请在弹出的界面中手动登录。")
            except Exception as exc:
                st.error(f"无法打开登录窗口: {exc}")

        if st.button("刷新登录状态", use_container_width=True):
            refresh_xhs_status(api_url)

        if st.button("启动小红书 MCP 服务", use_container_width=True):
            try:
                payload = backend_post(api_url, XHS_MCP_START_PATH)
                st.success(f"MCP 已启动: {payload.get('data', {}).get('base_url', '')}")
            except Exception as exc:
                st.error(f"MCP 启动失败: {exc}")

        status = st.session_state.get("xhs_status", {})
        if status:
            st.json(status)


def render_planning_status(slot) -> None:
    with slot.container():
        with st.status("Node 1: 统筹规划", expanded=True) as status:
            if st.session_state["planning_data"]:
                st.json(st.session_state["planning_data"])
                status.update(label="Node 1: 统筹规划完成", state="complete")
            else:
                st.info("等待规划结果...")


def render_retrieval_status(slot) -> None:
    with slot.container():
        with st.status("Node 2: 检索瀑布流", expanded=True) as status:
            updates = st.session_state["retrieval_updates"]
            if updates:
                for item in updates:
                    strategy = item.get("strategy", "")
                    title = item.get("title", "")
                    st.write(f"- {item.get('query')} | {item.get('status')} | {strategy} | {title}")
                status.update(label="Node 2: 检索中 / 已更新", state="running")
            else:
                st.info("等待检索进度...")


def render_recipe_status(slot) -> None:
    with slot.container():
        st.markdown("### Node 3: 总厨流式输出")
        if st.session_state["latest_result"]:
            st.markdown(st.session_state["latest_result"])
        else:
            st.info("等待菜谱生成...")


def add_history_record() -> None:
    st.session_state["history"].append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input": st.session_state["latest_input"],
            "result": st.session_state["latest_result"],
            "error": st.session_state["last_error"],
        }
    )


def render_history() -> None:
    if not st.session_state["history"]:
        return
    with st.expander("最近运行记录", expanded=False):
        for item in reversed(st.session_state["history"][-5:]):
            st.markdown(f"**{item['time']}**")
            st.write(f"输入: {item['input']}")
            if item["error"]:
                st.error(item["error"])
            else:
                st.write(item["result"][:300] + ("..." if len(item["result"]) > 300 else ""))
            st.markdown("---")


def recipe_chunk_stream(response: requests.Response, planning_slot, retrieval_slot) -> Generator[str, None, None]:
    for event in parse_sse_lines(response.iter_lines(decode_unicode=True)):
        event_name = event.get("event", "message")
        data = event.get("data", {})

        if event_name == "planning_done":
            st.session_state["planning_data"] = data
            render_planning_status(planning_slot)
            continue

        if event_name == "retrieval_update":
            st.session_state["retrieval_updates"].append(data)
            render_retrieval_status(retrieval_slot)
            continue

        if event_name == "recipe_stream":
            chunk = data.get("chunk", "")
            if chunk:
                yield chunk
            continue

        if event_name == "error":
            st.session_state["last_error"] = data.get("message", "未知错误")
            return

        if event_name == "recipe_done":
            return


def run_stream_request(api_url: str, user_input: str, planning_slot, retrieval_slot, recipe_slot) -> None:
    st.session_state["latest_input"] = user_input
    st.session_state["latest_result"] = ""
    st.session_state["planning_data"] = None
    st.session_state["retrieval_updates"] = []
    st.session_state["last_error"] = ""

    try:
        response = requests.get(
            f"{api_url}{STREAM_PATH}",
            params={"user_input": user_input},
            stream=True,
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        st.session_state["last_error"] = "无法连接后端，请先运行 python main.py。"
        return
    except requests.exceptions.Timeout:
        st.session_state["last_error"] = "请求超时，请稍后重试。"
        return
    except requests.exceptions.RequestException as exc:
        st.session_state["last_error"] = f"后端请求失败: {exc}"
        return

    with recipe_slot.container():
        st.markdown("### Node 3: 总厨流式输出")
        streamed_text = st.write_stream(
            recipe_chunk_stream(
                response=response,
                planning_slot=planning_slot,
                retrieval_slot=retrieval_slot,
            )
        )

    if isinstance(streamed_text, str):
        st.session_state["latest_result"] = streamed_text
    add_history_record()


def main() -> None:
    init_state()

    st.title("Cook Agent")
    st.caption("Gemini + SSE + 小红书 MCP + Streamlit 的私人排菜 Agent")

    with st.sidebar:
        st.subheader("连接")
        api_url = st.text_input("Backend URL", value=DEFAULT_BACKEND_URL)
        st.caption("主接口: GET /api/v1/stream_meal_plan")

    render_xhs_controls(api_url.strip() or DEFAULT_BACKEND_URL)

    st.markdown("### 你的需求")
    st.text_area(
        "描述食材、人数、忌口与预期。",
        key="input_text",
        height=120,
        label_visibility="collapsed",
        placeholder="例如：我有3个番茄、2个鸡蛋，2个人吃，不吃辣，想做两菜一汤。",
    )

    col_generate, col_clear = st.columns(2)
    with col_generate:
        submit = st.button("生成排菜方案", use_container_width=True)
    with col_clear:
        clear = st.button("清空当前结果", use_container_width=True)

    planning_slot = st.empty()
    retrieval_slot = st.empty()
    recipe_slot = st.empty()

    render_planning_status(planning_slot)
    render_retrieval_status(retrieval_slot)
    render_recipe_status(recipe_slot)

    if clear:
        reset_current_result()
        st.rerun()

    if submit:
        user_input = st.session_state["input_text"].strip()
        if not user_input:
            st.warning("请先输入需求。")
        else:
            run_stream_request(
                api_url=api_url.strip() or DEFAULT_BACKEND_URL,
                user_input=user_input,
                planning_slot=planning_slot,
                retrieval_slot=retrieval_slot,
                recipe_slot=recipe_slot,
            )
            render_planning_status(planning_slot)
            render_retrieval_status(retrieval_slot)
            render_recipe_status(recipe_slot)

    if st.session_state["last_error"]:
        st.error(st.session_state["last_error"])

    render_history()


if __name__ == "__main__":
    main()
