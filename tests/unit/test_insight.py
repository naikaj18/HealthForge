import json
from unittest.mock import patch, MagicMock

import pytest


def _reload_module():
    import importlib
    import lambdas.insight.handler as m
    m._cached_api_key = None
    importlib.reload(m)
    return m


# --- lambda_handler ---

def test_handler_passthrough_when_send_email_false():
    m = _reload_module()
    event = {"send_email": False, "sleep": {"avg_score": 70}}
    result = m.lambda_handler(event, None)
    assert result is event
    assert "insights" not in result


# --- generate_sleep_insight fallback ---

def test_sleep_insight_fallback_high_score():
    m = _reload_module()
    with patch.object(m, "call_gemini", return_value=""):
        data = {"sleep": {"avg_score": 85, "details": {}}}
        result = m.generate_sleep_insight(data)
        assert "Strong sleep" in result


def test_sleep_insight_fallback_mid_score():
    m = _reload_module()
    with patch.object(m, "call_gemini", return_value=""):
        data = {"sleep": {"avg_score": 65, "details": {}}}
        result = m.generate_sleep_insight(data)
        assert "65" in result


def test_sleep_insight_fallback_low_score():
    m = _reload_module()
    with patch.object(m, "call_gemini", return_value=""):
        data = {"sleep": {"avg_score": 40, "details": {}}}
        result = m.generate_sleep_insight(data)
        assert "40" in result
        assert "bedtime" in result.lower()
