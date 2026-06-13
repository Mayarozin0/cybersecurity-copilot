"""Gemini API client wrapper using structured output via Pydantic schemas."""

from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Type, TypeVar

from settings import settings

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Client for interacting with the Gemini API with structured JSON output."""

    def __init__(self):
        """Initialize the Gemini client using API key and model from settings."""
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

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
        """Call the model with a prompt and return a validated Pydantic response object."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
            system_instruction = system_prompt
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        return response_schema.model_validate_json(response.text)
