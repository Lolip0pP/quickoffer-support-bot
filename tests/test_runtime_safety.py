"""Safety checks for configuration and internal API boundaries."""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.core.config import Settings
from src.services.handoff_engine import CollectedFact


def test_settings_can_load_without_secrets_but_bot_cannot_start() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        settings.validate_runtime("bot")


def test_collected_fact_serializes_its_value() -> None:
    fact = CollectedFact("tool_failure", "test", "timeout")

    assert fact.to_dict()["value"] == "timeout"


def test_internal_webhooks_fail_closed_without_configured_secret() -> None:
    response = TestClient(app).post(
        "/api/v1/webhooks/approval",
        json={"action_id": "action-1", "status": "approved"},
    )

    assert response.status_code == 401
