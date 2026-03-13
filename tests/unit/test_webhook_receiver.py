import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test-queue")


@pytest.fixture(autouse=True)
def _mock_sqs():
    with patch("boto3.client") as mock_client:
        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs
        # Need to reload the module so module-level boto3.client call uses mock
        import importlib
        import lambdas.webhook_receiver.handler as mod
        importlib.reload(mod)
        yield mod, mock_sqs


def _event(body):
    return {"body": json.dumps(body) if isinstance(body, dict) else body}


def test_valid_payload_returns_200(_mock_sqs):
    mod, sqs = _mock_sqs
    body = {"data": {"metrics": [{"name": "step_count", "data": []}]}}
    result = mod.lambda_handler(_event(body), None)
    assert result["statusCode"] == 200
    resp = json.loads(result["body"])
    assert resp["status"] == "received"
    assert resp["metrics_count"] == 1
    sqs.send_message.assert_called_once()


def test_invalid_json_returns_400(_mock_sqs):
    mod, _ = _mock_sqs
    result = mod.lambda_handler({"body": "not json{{"}, None)
    assert result["statusCode"] == 400
    assert "Invalid JSON" in result["body"]


def test_missing_data_metrics_returns_400(_mock_sqs):
    mod, _ = _mock_sqs
    result = mod.lambda_handler(_event({"foo": "bar"}), None)
    assert result["statusCode"] == 400
    assert "Missing data.metrics" in result["body"]


def test_empty_metrics_returns_400(_mock_sqs):
    mod, _ = _mock_sqs
    result = mod.lambda_handler(_event({"data": {"metrics": []}}), None)
    assert result["statusCode"] == 400
    assert "non-empty" in result["body"]
