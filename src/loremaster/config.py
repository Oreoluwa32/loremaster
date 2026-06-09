"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    gm_model: str
    memory_model: str
    embed_model: str
    embed_dim: int
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.pg_user} password={self.pg_password}"
        )


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()


def load_settings() -> Settings:
    api_key = os.environ.get("QWEN_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "QWEN_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return Settings(
        api_key=api_key,
        base_url=_env(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ),
        gm_model=_env("QWEN_GM_MODEL", "qwen-plus"),
        memory_model=_env("QWEN_MEMORY_MODEL", "qwen-flash"),
        embed_model=_env("QWEN_EMBED_MODEL", "text-embedding-v3"),
        embed_dim=int(_env("QWEN_EMBED_DIM", "1024")),
        pg_host=_env("POSTGRES_HOST", "localhost"),
        pg_port=int(_env("POSTGRES_PORT", "5432")),
        pg_db=_env("POSTGRES_DB", "loremaster"),
        pg_user=_env("POSTGRES_USER", "loremaster"),
        pg_password=_env("POSTGRES_PASSWORD", "loremaster"),
    )
