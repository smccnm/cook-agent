from xhs_service import build_cookie_header, extract_a1


def test_extract_a1_from_cookie_list():
    cookies = [
        {"name": "web_session", "value": "abc"},
        {"name": "a1", "value": "target-a1"},
    ]

    assert extract_a1(cookies) == "target-a1"


def test_build_cookie_header_from_cookie_list():
    cookies = [
        {"name": "web_session", "value": "abc"},
        {"name": "a1", "value": "target-a1"},
    ]

    assert build_cookie_header(cookies) == "web_session=abc; a1=target-a1"
