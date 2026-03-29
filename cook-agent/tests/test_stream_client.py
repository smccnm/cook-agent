from stream_client import parse_sse_lines


def test_parse_sse_lines_returns_structured_events():
    lines = [
        "event: planning_done",
        'data: {"portion_size": 2}',
        "",
    ]

    events = list(parse_sse_lines(lines))

    assert events[0]["event"] == "planning_done"
    assert events[0]["data"]["portion_size"] == 2
