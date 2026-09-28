"""Unit tests: structured logging and secret redaction."""

import json

import structlog

from app.logging import REDACTED, configure_logging, redact_sensitive


def test_redacts_common_sensitive_keys():
    event = {
        "password": "hunter2",
        "token": "tok-123",
        "access_token": "at-123",
        "refresh_token": "rt-123",
        "api_key": "ak-123",
        "apikey": "ak-123",
        "authorization": "Bearer abc",
        "client_secret": "cs-123",
        "private_key": "-----BEGIN",
        "database_url": "postgresql://u:p@h/db",
        "webhook_secret": "wh-123",
        "cookie": "session=1",
    }
    result = redact_sensitive(None, "info", event)
    for key in event:
        assert result[key] == REDACTED, f"{key} was not redacted"


def test_leaves_safe_keys_untouched():
    event = {
        "environment": "test",
        "version": "0.1.0",
        "path": "/health",
        "author": "someone",
        "status": 200,
    }
    result = redact_sensitive(None, "info", event)
    assert result == event


def test_redacts_nested_structures():
    event = {
        "request": {"headers": {"authorization": "Bearer abc"}, "path": "/x"},
        "items": [{"password": "p1"}, {"name": "safe"}],
    }
    result = redact_sensitive(None, "info", event)
    assert result["request"]["headers"]["authorization"] == REDACTED
    assert result["request"]["path"] == "/x"
    assert result["items"][0]["password"] == REDACTED
    assert result["items"][1] == {"name": "safe"}


def test_json_output_redacts_and_stays_parseable(capsys):
    configure_logging(level="INFO", json_output=True)
    log = structlog.get_logger("test")
    log.info("user.login", password="hunter2", username="alice")

    out = capsys.readouterr().out
    record = json.loads(out.strip().splitlines()[-1])
    assert record["event"] == "user.login"
    assert record["username"] == "alice"
    assert record["password"] == REDACTED
    assert "hunter2" not in out


def test_json_output_includes_timestamp_and_level(capsys):
    configure_logging(level="INFO", json_output=True)
    log = structlog.get_logger("test")
    log.info("app.event", safe="value")

    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "timestamp" in record
    assert record["level"] == "info"


def test_level_filtering(capsys):
    configure_logging(level="WARNING", json_output=True)
    log = structlog.get_logger("test")
    log.info("not.emitted")
    log.warning("emitted")

    out = capsys.readouterr().out
    assert "not.emitted" not in out
    assert "emitted" in out


def test_invalid_log_level_fails():
    import pytest

    with pytest.raises(ValueError):
        configure_logging(level="NOT_A_LEVEL")
