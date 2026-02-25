from typing import TypedDict, Optional
from datetime import datetime, timezone


class TrackingDocument(TypedDict, total=False):
    """
    Schema reference for tracking collection documents.
    Used for documentation and IDE autocomplete.
    """
    api_player_id: int
    status: str  # pending | processing | completed | failed
    created_at: datetime
    updated_at: datetime
    retry_count: int
    error_log: list[str]
    output_path: Optional[str]
    style: str
    mode: str
    generation_duration_seconds: Optional[float]
    source_image_url: str


def new_tracking_document(api_player_id, source_image_url, style, mode):
    """Create a fresh tracking document dict with default values."""
    now = datetime.now(timezone.utc)
    return {
        "api_player_id": api_player_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "retry_count": 0,
        "error_log": [],
        "output_path": None,
        "style": style,
        "mode": mode,
        "generation_duration_seconds": None,
        "source_image_url": source_image_url,
    }
