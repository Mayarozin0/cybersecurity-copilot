"""Claude API client wrapper using structured output via Pydantic schemas."""
from anthropic import Anthropic
from pydantic import BaseModel
from typing import Type, TypeVar

from settings import settings

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    """Client for interacting with the Claude API with structured JSON output."""

    def __init__(self):
        """Initialize the Claude client using API key and model from settings."""
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def close(self):
        """Release the underlying client."""
        self._client = None

    def invoke(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call the model with a prompt and return a validated Pydantic response object.

        Note: temperature is not supported on claude-opus-4-8 and later and is ignored.
        """
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            output_format=response_schema,
        )

        return response.parsed_output

