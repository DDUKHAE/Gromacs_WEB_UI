import json

from web.llm_runner import strip_ansi


def test_strip_ansi_removes_terminal_sequences():
    assert strip_ansi("\x1b[31mAllow? [y/n]\x1b[0m") == "Allow? [y/n]"


def test_permission_event_is_json_serializable():
    payload = {"type": "permission_request", "detail": "Allow? [y/n]"}
    assert json.loads(json.dumps(payload))["type"] == "permission_request"
