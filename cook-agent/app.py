"""Streamlit frontend for the stable streaming meal-plan workflow."""

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

st.set_page_config(
    page_title="Cook Agent",
    page_icon="🍳",
    layout="wide",
)


def init_state() -> None:
    st.session_state.setdefault("input_text", "")
    st.session_state.setdefault("latest_input", "")
    st.session_state.setdefault("latest_result", "")
    st.session_state.setdefault("planning_data", None)
    st.session_state.setdefault("retrieval_updates", [])
    st.session_state.setdefault("last_error", "")
    st.session_state.setdefault("history", [])


def reset_current_result() -> None:
    st.session_state["latest_input"] = ""
    st.session_state["latest_result"] = ""
    st.session_state["planning_data"] = None
    st.session_state["retrieval_updates"] = []
    st.session_state["last_error"] = ""


def render_planning_status(planning_slot: st.delta_generator.DeltaGenerator) -> None:
    with planning_slot.container():
        st.markdown("### Node 1: Planning Status")
        if st.session_state["planning_data"]:
            st.success("Planning completed.")
            st.json(st.session_state["planning_data"])
        else:
            st.info("Waiting for planning results.")


def render_retrieval_status(retrieval_slot: st.delta_generator.DeltaGenerator) -> None:
    with retrieval_slot.container():
        st.markdown("### Node 2: Retrieval Status")
        updates = st.session_state["retrieval_updates"]
        if updates:
            for item in updates:
                query = item.get("query", "(unknown query)")
                status = item.get("status", "unknown")
                icon = "✅" if status == "success" else "⚠️"
                st.write(f"{icon} `{query}` - {status}")
        else:
            st.info("Waiting for retrieval updates.")


def render_recipe_status(recipe_slot: st.delta_generator.DeltaGenerator) -> None:
    with recipe_slot.container():
        st.markdown("### Node 3: Streamed Markdown")
        if st.session_state["latest_result"]:
            st.markdown(st.session_state["latest_result"])
        else:
            st.info("Waiting for streamed recipe output.")


def render_status_panels(
    planning_slot: st.delta_generator.DeltaGenerator,
    retrieval_slot: st.delta_generator.DeltaGenerator,
    recipe_slot: st.delta_generator.DeltaGenerator,
) -> None:
    render_planning_status(planning_slot)
    render_retrieval_status(retrieval_slot)
    render_recipe_status(recipe_slot)


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

    with st.expander("Recent Runs", expanded=False):
        for item in reversed(st.session_state["history"][-5:]):
            st.markdown(f"**{item['time']}**")
            st.write(f"Input: {item['input']}")
            if item["error"]:
                st.error(item["error"])
            else:
                st.write(item["result"][:300] + ("..." if len(item["result"]) > 300 else ""))
            st.markdown("---")


def recipe_chunk_stream(
    response: requests.Response,
    planning_slot: st.delta_generator.DeltaGenerator,
    retrieval_slot: st.delta_generator.DeltaGenerator,
) -> Generator[str, None, None]:
    for event in parse_sse_lines(response.iter_lines(decode_unicode=True)):
        event_name = event.get("event", "message")
        payload = event.get("data", {})
        data = payload if isinstance(payload, dict) else {}

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
            st.session_state["last_error"] = data.get(
                "message",
                "Backend returned an unknown error.",
            )
            return

        if event_name == "recipe_done":
            return


def run_stream_request(
    api_url: str,
    user_input: str,
    planning_slot: st.delta_generator.DeltaGenerator,
    retrieval_slot: st.delta_generator.DeltaGenerator,
    recipe_slot: st.delta_generator.DeltaGenerator,
) -> None:
    st.session_state["latest_input"] = user_input
    st.session_state["latest_result"] = ""
    st.session_state["planning_data"] = None
    st.session_state["retrieval_updates"] = []
    st.session_state["last_error"] = ""
    render_status_panels(planning_slot, retrieval_slot, recipe_slot)

    request_url = f"{api_url}{STREAM_PATH}"
    try:
        response = requests.get(
            request_url,
            params={"user_input": user_input},
            stream=True,
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        st.session_state["last_error"] = (
            "Cannot connect to backend. Start it with `python main.py` and confirm the API URL."
        )
        render_status_panels(planning_slot, retrieval_slot, recipe_slot)
        add_history_record()
        return
    except requests.exceptions.Timeout:
        st.session_state["last_error"] = (
            "Request timed out. Please try again and keep the backend running."
        )
        render_status_panels(planning_slot, retrieval_slot, recipe_slot)
        add_history_record()
        return
    except requests.exceptions.RequestException:
        st.session_state["last_error"] = (
            "Backend request failed. Verify `/api/v1/stream_meal_plan` is reachable."
        )
        render_status_panels(planning_slot, retrieval_slot, recipe_slot)
        add_history_record()
        return

    with recipe_slot.container():
        st.markdown("### Node 3: Streamed Markdown")
        streamed_text = st.write_stream(
            recipe_chunk_stream(
                response=response,
                planning_slot=planning_slot,
                retrieval_slot=retrieval_slot,
            )
        )

    if isinstance(streamed_text, str):
        st.session_state["latest_result"] = streamed_text

    render_status_panels(planning_slot, retrieval_slot, recipe_slot)
    add_history_record()


def main() -> None:
    init_state()

    st.title("Cook Agent")
    st.caption("SSE streaming frontend for three-stage meal-plan generation.")

    with st.sidebar:
        st.subheader("Connection")
        api_url = st.text_input("Backend URL", value=DEFAULT_BACKEND_URL)
        st.caption("Streaming endpoint: GET /api/v1/stream_meal_plan")

    st.markdown("### Your Request")
    st.text_area(
        "Describe your ingredients and requirements.",
        key="input_text",
        height=120,
        label_visibility="collapsed",
        placeholder="Example: 2 potatoes, 300g pork, no spicy food, 2 dishes and 1 soup.",
    )

    col_generate, col_clear = st.columns(2)
    with col_generate:
        submit = st.button("Generate Meal Plan", use_container_width=True)
    with col_clear:
        clear = st.button("Clear Current Result", use_container_width=True)

    planning_slot = st.empty()
    retrieval_slot = st.empty()
    recipe_slot = st.empty()

    if clear:
        reset_current_result()
        render_status_panels(planning_slot, retrieval_slot, recipe_slot)
    elif submit:
        user_input = st.session_state["input_text"].strip()
        if not user_input:
            st.warning("Please enter your request first.")
            render_status_panels(planning_slot, retrieval_slot, recipe_slot)
        else:
            run_stream_request(
                api_url=api_url.strip() or DEFAULT_BACKEND_URL,
                user_input=user_input,
                planning_slot=planning_slot,
                retrieval_slot=retrieval_slot,
                recipe_slot=recipe_slot,
            )
    else:
        render_status_panels(planning_slot, retrieval_slot, recipe_slot)

    if st.session_state["last_error"]:
        st.error(st.session_state["last_error"])
        st.info(
            "If backend is not running, open a terminal in this project and run: `python main.py`."
        )

    render_history()


if __name__ == "__main__":
    main()
