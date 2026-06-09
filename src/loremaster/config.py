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


def load_settings() -> Settings:
    api_key = os.environ.get("QWEN_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "QWEN_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return Settings(
        api_key=api_key,
        base_url=os.environ.get(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ).strip(),
        gm_model=os.environ.get("QWEN_GM_MODEL", "qwen-plus").strip(),
        memory_model=os.environ.get("QWEN_MEMORY_MODEL", "qwen-flash").strip(),
    )
