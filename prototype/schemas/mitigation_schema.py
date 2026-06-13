"""Pydantic schema for the mitigation pipeline output."""

from pydantic import BaseModel


class MitigationPlan(BaseModel):
    """Structured mitigation plan produced by the mitigation pipeline."""

    past_cases_analyzation: str  # ≤20 words
    mitigation_reasoning: str    # ≤15 words
    mitigation: str              # markdown string
