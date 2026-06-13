"""Write-back module: persists new incidents to data/raw.json after the mitigation pipeline completes."""

import json
import uuid

from settings import settings


def save_incident(summary: str, mitigation: str, raw_path: str = None) -> str:
    """Append a new incident to raw.json and return the generated uuid.

    Args:
        summary: The structured incident summary text.
        mitigation: The mitigation plan produced by the pipeline.
        raw_path: Override path to data/raw.json; defaults to settings.raw_json_path.
    """
    raw_path = raw_path or settings.raw_json_path

    with open(raw_path) as f:
        raw = json.load(f)

    new_uuid = str(uuid.uuid4())
    raw[new_uuid] = {"summary": summary, "mitigation": mitigation}

    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=2)

    return new_uuid
