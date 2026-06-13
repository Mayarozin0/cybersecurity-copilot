"""Pydantic schema for the incident summarization pipeline output."""

from pydantic import BaseModel
from typing import Optional, List


class VehicleContext(BaseModel):
    """OEM, model, year range, and fleet size of the affected vehicle(s)."""

    oem: Optional[str] = None
    model: Optional[str] = None
    year_range: Optional[str] = None
    affected_count: Optional[int] = None


class AttackDetail(BaseModel):
    """Structured breakdown of the attack type, vector, entry point, and targets."""

    type: Optional[str] = None
    vector: Optional[str] = None
    entry_point: Optional[str] = None
    target_systems: Optional[List[str]] = None
    affected_parts: Optional[List[str]] = None


class IncidentSummary(BaseModel):
    """Top-level structured output of the summarization pipeline."""

    incident_datetime: Optional[str] = None
    vehicle_context: VehicleContext
    attack: AttackDetail
    safety_impact: Optional[str] = None
    outcome: Optional[str] = None
    iocs: Optional[List[str]] = None
    summary_reasoning: str
    summary: str
