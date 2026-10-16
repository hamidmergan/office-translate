import pytest

from office_translate import ConfigError
from office_translate.config import PLACEHOLDER_API_KEY, resolve


def test_missing_base_url_and_model():
    with pytest.raises(ConfigError) as exc:
        resolve()
    assert "base_url" in str(exc.value)
    assert "model" in str(exc.value)


def test_env_values(monkeypatch):
    monkeypatch.setenv("OFFICE_TRANSLATE_BASE_URL", "http://localhost:1/v1")
    monkeypatch.setenv("OFFICE_TRANSLATE_MODEL", "m")
    monkeypatch.setenv("OFFICE_TRANSLATE_BATCH_SIZE", "5")
    s = resolve()
    assert s.base_url == "http://localhost:1/v1"
    assert s.batch_size == 5
    assert s.api_key == PLACEHOLDER_API_KEY


def test_argument_wins_over_env(monkeypatch):
    monkeypatch.setenv("OFFICE_TRANSLATE_MODEL", "env-model")
    s = resolve(base_url="http://x/v1", model="arg-model")
    assert s.model == "arg-model"


def test_api_key_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert resolve(base_url="http://x/v1", model="m").api_key == "sk-test"
    assert resolve(base_url="http://x/v1", model="m", api_key="own").api_key == "own"


def test_invalid_env_value(monkeypatch):
    monkeypatch.setenv("OFFICE_TRANSLATE_TIMEOUT", "soon")
    with pytest.raises(ConfigError, match="OFFICE_TRANSLATE_TIMEOUT"):
        resolve(base_url="http://x/v1", model="m")


def test_invalid_limit():
    with pytest.raises(ConfigError, match="batch_size"):
        resolve(base_url="http://x/v1", model="m", batch_size=0)
