"""
Event schemas for event-driven context system
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class UserEventSchema(BaseModel):
    """
    Schema for user events in the event-driven context system.

    This schema defines the structure of events that represent user activities
    on the platform (weight recording, meal logging, exercise, etc.).
    """

    user_id: str = Field(..., description="User identifier")

    event_type: str = Field(
        ...,
        description="Type of event (weight_recorded, meal_recorded, exercise_recorded, water_recorded, sleep_recorded)",
    )

    event_data: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data payload"
    )

    importance_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Initial importance score (0.0-1.0)"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )

    expires_at: Optional[datetime] = Field(
        None, description="Expiration time for automatic cleanup"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (frequency_count, has_feedback, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "event_type": "sleep_recorded",
                "event_data": {"duration_hours": 8, "quality": 85, "record_id": 12345},
                "importance_score": 0.75,
                "timestamp": "2026-02-15T08:00:00Z",
                "metadata": {"has_feedback": False},
            }
        }
