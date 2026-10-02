"""Gemini ClientError uses ``code``, not ``status_code``."""

import pytest
from google.genai import errors as genai_errors

from anki_bot.gemini_review import (
    _api_error_code,
    _call_gemini,
    _http_options,
    _raise_gemini_api_error,
)


def _client_error(code: int, message: str) -> genai_errors.ClientError:
    return genai_errors.ClientError(
        code,
        {"error": {"code": code, "message": message, "status": "ERROR"}},
    )


def test_client_error_has_code_not_status_code() -> None:
    exc = _client_error(429, "Resource exhausted")
    assert exc.code == 429
    assert not hasattr(exc, "status_code")
    assert _api_error_code(exc) == 429


def test_raise_gemini_api_error_reports_code() -> None:
    exc = _client_error(429, "Resource exhausted")
    with pytest.raises(RuntimeError, match=r"Gemini API error \(429\)"):
        _raise_gemini_api_error(exc, "gemini-3.1-pro-preview")


def test_raise_gemini_api_error_missing_model() -> None:
    exc = genai_errors.ClientError(
        404,
        {"error": {"message": "models/gemini-2.5-pro is not found", "status": "NOT_FOUND"}},
    )
    with pytest.raises(RuntimeError, match="not available on your API key"):
        _raise_gemini_api_error(exc, "gemini-2.5-pro")


def test_call_gemini_does_not_touch_status_code() -> None:
    class _Models:
        def generate_content(self, **kwargs):  # noqa: ANN003
            raise _client_error(429, "Resource exhausted")

    class _Client:
        models = _Models()

    with pytest.raises(RuntimeError, match=r"Gemini API error \(429\)") as caught:
        _call_gemini(
            _Client(),  # type: ignore[arg-type]
            "gemini-3.1-pro-preview",
            static_parts=["static"],
            dynamic_parts=["dynamic"],
            cache_kind="question",
        )
    assert "status_code" not in str(caught.value)


def test_server_error_uses_code() -> None:
    exc = genai_errors.ServerError(
        503,
        {"error": {"code": 503, "message": "unavailable", "status": "UNAVAILABLE"}},
    )
    with pytest.raises(RuntimeError, match=r"Gemini API error \(503\)"):
        _raise_gemini_api_error(exc, "gemini-3.1-pro-preview")


def test_http_options_enable_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANKI_BOT_GEMINI_TIMEOUT_S", "180")
    options = _http_options()
    assert options.timeout == 180_000
    assert options.retry_options is not None
