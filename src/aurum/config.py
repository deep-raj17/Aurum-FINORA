"""Typed runtime configuration with environment-variable overrides."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)
load_dotenv(override=False)


def _first_environment_value(*names: str) -> str | None:
    return next((value for name in names if (value := os.getenv(name))), None)


class CostSettings(BaseModel):
    round_trip_bps: float = Field(default=10, ge=0)
    slippage_bps: float = Field(default=5, ge=0)


class Settings(BaseModel):
    environment: str = "dev"
    model_version: str = "finora-core-1.1"
    annualisation_factor: int = 252
    min_train_size: int = 20
    costs: CostSettings = CostSettings()
    compliance_scope: list[str] = ["research-only", "human-review-required"]
    database_path: str = "data/aurum.sqlite3"
    api_key: str | None = None
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    retrieval_limit: int = Field(default=5, ge=1, le=20)
    sentiment_backend: str = "lexical"
    sentiment_model_id: str = "ProsusAI/finbert"
    chronos_model_id: str = "amazon/chronos-t5-tiny"
    model_cache_dir: str = "model_cache"
    llm_provider: str = "disabled"
    llm_mode: str = "remote"
    llm_endpoint: str | None = None
    llm_model_id: str = "gpt-oss-120b"
    llm_api_key: str | None = Field(default=None, exclude=True, repr=False)
    llm_max_context: int = Field(default=131_072, ge=1024)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_temperature: float = Field(default=0.1, ge=0, le=2)

    @model_validator(mode="after")
    def production_controls(self) -> Settings:
        if self.environment.lower() in {"production", "prod"}:
            if not self.api_key:
                raise ValueError("production requires AURUM_API_KEY or an external auth gateway")
            if self.sentiment_backend != "finbert":
                raise ValueError("production requires sentiment_backend=finbert")
            if "*" in self.cors_origins:
                raise ValueError("wildcard CORS is forbidden in production")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> Settings:
        from .security import SecretManager

        secrets = SecretManager()
        with Path(path).open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        overrides = {
            "environment": os.getenv("AURUM_ENV"),
            "database_path": os.getenv("AURUM_DATABASE_PATH"),
            "api_key": secrets.get("AURUM_API_KEY", required=False),
            "sentiment_backend": os.getenv("AURUM_SENTIMENT_BACKEND"),
            "sentiment_model_id": _first_environment_value(
                "FINORA_FINBERT_MODEL_ID", "AURUM_SENTIMENT_MODEL_ID"
            ),
            "chronos_model_id": os.getenv("FINORA_CHRONOS_MODEL_ID"),
            "model_cache_dir": os.getenv("FINORA_MODEL_CACHE_DIR"),
            "llm_provider": os.getenv("FINORA_LLM_PROVIDER"),
            "llm_mode": os.getenv("FINORA_LLM_MODE"),
            "llm_endpoint": os.getenv("FINORA_LLM_ENDPOINT"),
            "llm_model_id": os.getenv("FINORA_LLM_MODEL_ID"),
            "llm_api_key": secrets.get("FINORA_LLM_API_KEY", required=False)
            or secrets.get("FINORA_LLM_API_TOKEN", required=False),
            "llm_max_context": int(os.getenv("FINORA_LLM_MAX_CONTEXT", "131072")),
            "llm_max_tokens": int(os.getenv("FINORA_LLM_MAX_TOKENS", "4096")),
            "llm_temperature": float(os.getenv("FINORA_LLM_TEMPERATURE", "0.1")),
        }
        data.update({key: value for key, value in overrides.items() if value is not None})
        return cls.model_validate(data)


def validate_api_keys() -> dict[str, bool]:
    """Check which API keys are configured for safe startup validation.

    Returns a dict mapping provider names to availability status.
    Missing keys will log warnings but not block startup.
    """
    providers = {
        "ALPHA_VANTAGE": _first_environment_value("ALPHA_VANTAGE_API_KEY", "ALPHAVANTAGE_API_KEY"),
        "TIINGO": os.getenv("TIINGO_API_KEY"),
        "FINNHUB": os.getenv("FINNHUB_API_KEY"),
        "FRED": os.getenv("FRED_API_KEY"),
        "FINANCIAL_MODELING_PREP": os.getenv("FMP_API_KEY"),
        "NASDAQ_DATA_LINK": os.getenv("NASDAQ_DATA_LINK_API_KEY"),
    }

    status = {}
    for provider, key in providers.items():
        available = bool(key)
        status[provider] = available
        if not available:
            logger.warning("API key for %s is not configured; live tests will be skipped", provider)

    return status
