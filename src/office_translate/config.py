"""Default values and resolution of settings.

Order: argument, then environment variable, then default.
"""

import os
from dataclasses import dataclass
from typing import Optional

from .errors import ConfigError

# Limits
MAX_FILE_MB = 100

# Processing
BATCH_SIZE = 20
BATCH_CHARS = 4000
CONCURRENCY = 4
TIMEOUT_SECONDS = 120
MAX_RETRIES = 2
TEMPERATURE = 0.1

# Placeholder, because the OpenAI library requires a value.
# Local servers ignore it.
PLACEHOLDER_API_KEY = "not-needed"

ENV_PREFIX = "OFFICE_TRANSLATE_"


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    api_key: str
    max_file_mb: float
    batch_size: int
    batch_chars: int
    concurrency: int
    timeout: float
    max_retries: int
    temperature: float


def _env(name: str) -> Optional[str]:
    value = os.environ.get(ENV_PREFIX + name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _pick(arg, env_name: str, default, cast):
    if arg is not None:
        return arg
    raw = _env(env_name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except ValueError:
        raise ConfigError(
            f"Environment variable {ENV_PREFIX}{env_name} has an invalid value: {raw!r}"
        )


def resolve(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_file_mb: Optional[float] = None,
    batch_size: Optional[int] = None,
    batch_chars: Optional[int] = None,
    concurrency: Optional[int] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Settings:
    base_url = _pick(base_url, "BASE_URL", None, str)
    model = _pick(model, "MODEL", None, str)
    missing = []
    if not base_url:
        missing.append("base_url (--base-url or OFFICE_TRANSLATE_BASE_URL)")
    if not model:
        missing.append("model (--model or OFFICE_TRANSLATE_MODEL)")
    if missing:
        raise ConfigError(
            "Missing: " + " and ".join(missing) + ". "
            "Example for Ollama: base_url http://localhost:11434/v1 and model qwen2.5:7b."
        )

    key = _pick(api_key, "API_KEY", None, str)
    if not key:
        key = os.environ.get("OPENAI_API_KEY") or PLACEHOLDER_API_KEY

    settings = Settings(
        base_url=base_url,
        model=model,
        api_key=key,
        max_file_mb=_pick(max_file_mb, "MAX_FILE_MB", MAX_FILE_MB, float),
        batch_size=_pick(batch_size, "BATCH_SIZE", BATCH_SIZE, int),
        batch_chars=_pick(batch_chars, "BATCH_CHARS", BATCH_CHARS, int),
        concurrency=_pick(concurrency, "CONCURRENCY", CONCURRENCY, int),
        timeout=_pick(timeout, "TIMEOUT", TIMEOUT_SECONDS, float),
        max_retries=_pick(max_retries, "MAX_RETRIES", MAX_RETRIES, int),
        temperature=_pick(temperature, "TEMPERATURE", TEMPERATURE, float),
    )
    _validate(settings)
    return settings


def _validate(s: Settings) -> None:
    positive = {
        "max_file_mb": s.max_file_mb,
        "batch_size": s.batch_size,
        "batch_chars": s.batch_chars,
        "concurrency": s.concurrency,
        "timeout": s.timeout,
    }
    for name, value in positive.items():
        if value <= 0:
            raise ConfigError(f"{name} must be greater than 0, but is {value}.")
    if s.max_retries < 0:
        raise ConfigError("max_retries must not be negative.")
    if not 0 <= s.temperature <= 2:
        raise ConfigError("temperature must be between 0 and 2.")
