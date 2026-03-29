"""Client-side helpers for consuming Server-Sent Events (SSE)."""

from __future__ import annotations

import json
from typing import Any, Generator, Iterable


def parse_sse_lines(lines: Iterable[str]) -> Generator[dict[str, Any], None, None]:
    """Parse raw SSE lines into structured ``{"event": ..., "data": ...}`` objects."""
    event_name = "message"
    data_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line

        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue

        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
            continue

        if line == "":
            if data_lines:
                payload = "".join(data_lines)
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = payload
                yield {"event": event_name, "data": data}

            event_name = "message"
            data_lines = []

    if data_lines:
        payload = "".join(data_lines)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = payload
        yield {"event": event_name, "data": data}
