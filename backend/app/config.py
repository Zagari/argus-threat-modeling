"""Configuração + estado de provider de LLM em runtime.

A chave de API é mantida apenas em memória no servidor e NUNCA é exposta em
`GET /settings` nem logada. Defaults vêm de `.env` (procurado a partir do cwd
para cima, então funciona rodando de backend/ com o .env na raiz do repo).
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(find_dotenv(usecwd=True))

Provider = Literal["gemini", "anthropic", "openai"]

DEFAULT_MODELS: dict[str, str] = {
    # gemini-2.5-flash com thinking DESLIGADO no código (ver provider.py) → ~2-3s
    # e ótima qualidade. Alternativa rápida/barata: gemini/gemini-2.5-flash-lite.
    # Modelo trocável em runtime (aba Configurações).
    "gemini": "gemini/gemini-2.5-flash",
    "anthropic": "anthropic/claude-sonnet-4-5",
    "openai": "openai/gpt-4o",
}

KEY_ENV: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUS_", extra="ignore")

    llm_provider: Provider = "gemini"
    llm_model: str = "gemini/gemini-2.5-flash"
    llm_temperature: float = 0.2
    llm_timeout: float = 90.0   # segundos; abaixo do limite ~100s do Cloudflare
    llm_mock: bool = False
    cors_origins: str = "http://localhost:5173"
    usd_brl_rate: float = 6.0   # cotação USD→BRL p/ exibir custo em R$ na UI


class RuntimeConfig:
    """Estado mutável do provider de LLM (trocável em runtime via /settings)."""

    def __init__(self, env: EnvSettings) -> None:
        self.provider: str = env.llm_provider
        self.model: str = env.llm_model
        self.temperature: float = env.llm_temperature
        self.timeout: float = env.llm_timeout
        self.mock: bool = env.llm_mock
        self.usd_brl_rate: float = env.usd_brl_rate
        self.cors_origins: list[str] = [o.strip() for o in env.cors_origins.split(",") if o.strip()]
        # chaves carregadas do ambiente (uma por provider, se presente)
        self.api_keys: dict[str, str] = {}
        for prov, env_name in KEY_ENV.items():
            val = os.getenv(env_name)
            if val:
                self.api_keys[prov] = val

    def active_key(self) -> str | None:
        return self.api_keys.get(self.provider)

    def update(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        api_key: str | None = None,
        mock: bool | None = None,
        usd_brl_rate: float | None = None,
    ) -> None:
        if provider:
            if provider not in DEFAULT_MODELS:
                raise ValueError(f"provider inválido: {provider}")
            self.provider = provider
            if not model:
                self.model = DEFAULT_MODELS[provider]
        if model:
            self.model = model
        if temperature is not None:
            self.temperature = temperature
        if mock is not None:
            self.mock = mock
        if usd_brl_rate is not None and usd_brl_rate > 0:
            self.usd_brl_rate = usd_brl_rate
        if api_key:
            self.api_keys[self.provider] = api_key

    def public_snapshot(self) -> dict:
        """Estado seguro p/ a UI — NUNCA inclui a chave em si."""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "mock": self.mock,
            "usd_brl_rate": self.usd_brl_rate,
            "has_key": bool(self.active_key()),
            "providers_with_key": sorted(self.api_keys.keys()),
            "available_providers": sorted(DEFAULT_MODELS.keys()),
            "default_models": DEFAULT_MODELS,
        }


_config: RuntimeConfig | None = None


def get_config() -> RuntimeConfig:
    global _config
    if _config is None:
        _config = RuntimeConfig(EnvSettings())
    return _config
