"""Application settings and secret loading from environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default: str | None = None) -> str | None:
    """Load a secret from environment variables; returns default if absent."""
    return os.getenv(key) or default


@dataclass
class Settings:
    """Holds all application configuration and secrets loaded from the environment."""

    gemini_api_key: str = get_secret("GEMINI-API-KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    anthropic_api_key: str | None = get_secret("ANTHROPIC_API_KEY")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    summarize_prompt_path: str = os.path.join(
        os.path.dirname(__file__), "prompts", "summarize.md"
    )
    query_gen_prompt_path: str = os.path.join(
        os.path.dirname(__file__), "prompts", "query_gen.md"
    )
    mitigate_prompt_path: str = os.path.join(
        os.path.dirname(__file__), "prompts", "mitigate.md"
    )


settings = Settings()
