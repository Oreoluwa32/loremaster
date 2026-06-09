from openai import OpenAI

from .config import Settings, load_settings


def get_client(settings: Settings | None = None) -> OpenAI:
    settings = settings or load_settings()
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def chat(
    messages: list[dict],
    model: str,
    client: OpenAI | None = None,
    **kwargs,
) -> str:
    """Send a chat completion and return the assistant's text reply."""
    client = client or get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content
