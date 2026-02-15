"""
Event models for event-driven context system
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, Float, JSON, Index
from sqlalchemy.dialects.sqlite import INTEGER

from models.database import Base


class UserEvent(Base):
    """
    Database model for user events in the event-driven context system.

    Stores all user activity events (weight recording, meal logging,
    exercise, water intake, sleep) with importance scoring and metadata.
    """

    __tablename__ = "user_events"

    # Primary key
    id = Column(INTEGER, primary_key=True, autoincrement=True, comment="Event ID")

    # User identifier
    user_id = Column(String(64), nullable=False, index=True, comment="User identifier")

    # Event type
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Event type (weight_recorded, meal_recorded, etc.)",
    )

    # Event data payload
    event_data = Column(
        JSON, nullable=False, default=dict, comment="Event-specific data in JSON format"
    )

    # Importance score (0.0-1.0)
    importance_score = Column(
        Float, default=0.5, nullable=False, comment="Initial importance score (0.0-1.0)"
    )

    # Event timestamp
    timestamp = Column(
        DateTime, default=datetime.utcnow, nullable=False, comment="Event timestamp"
    )

    # Expiration time for automatic cleanup
    expires_at = Column(
        DateTime, nullable=True, comment="Expiration time for automatic cleanup"
    )

    # Additional metadata
    event_metadata = Column(
        JSON,
        default=dict,
        comment="Additional metadata (frequency_count, has_feedback, etc.)",
    )

    # Creation time
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Record creation time",
    )

    # Database indexes for performance
    __table_args__ = (
        # Index for fast user+timestamp queries
        Index("idx_user_timestamp", "user_id", "timestamp"),
        # Index for fast user+type+timestamp queries
        Index("idx_user_type_timestamp", "user_id", "event_type", "timestamp"),
        # Index for expiration cleanup
        Index("idx_expires_at", "expires_at"),
    )

    def __repr__(self):
        return (
            f"<UserEvent("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.event_type}, "
            f"score={self.importance_score:.2f}, "
            f"timestamp={self.timestamp}"
            f")>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "importance_score": self.importance_score,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
