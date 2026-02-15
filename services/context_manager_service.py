"""
Context manager service for event-driven context system

This service provides hybrid storage (memory cache + database persistence)
with intelligent importance scoring and time decay algorithms.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import logging
import asyncio

from schemas.events import UserEventSchema

logger = logging.getLogger(__name__)


class ContextManagerService:
    """
    Hybrid context manager: memory cache + database persistence

    Uses existing importance scoring algorithm:
    - Recency: 40%
    - Importance: 30%
    - Frequency: 20%
    - Feedback: 10%

    Features:
    - In-memory cache for fast access
    - Time decay for event importance
    - LRU cache eviction
    - Cache TTL management
    """

    def __init__(
        self,
        max_events_per_user: int = 100,
        decay_half_life_days: float = 7.0,
        cache_ttl_minutes: int = 30,
    ):
        """
        Initialize context manager

        Args:
            max_events_per_user: Maximum number of events to cache per user
            decay_half_life_days: Half-life for time decay calculation (days)
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.max_events_per_user = max_events_per_user
        self.decay_half_life_days = decay_half_life_days
        self.cache_ttl_minutes = cache_ttl_minutes

        # In-memory cache (recent events)
        self._user_events: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_events_per_user)
        )

        # Cache timestamps for TTL
        self._cache_timestamps: Dict[str, datetime] = defaultdict(datetime.utcnow)

        logger.info(
            f"ContextManagerService initialized: max_events={max_events_per_user}, "
            f"decay_half_life={decay_half_life_days}days, ttl={cache_ttl_minutes}min"
        )

    def calculate_time_decay(
        self, event_time: datetime, current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate time decay factor using exponential decay

        Decay factor = 2^(-hours_passed / half_life_hours)

        Args:
            event_time: Event timestamp
            current_time: Current time (default: now)

        Returns:
            Decay factor between 0.0 and 1.0
        """
        if current_time is None:
            current_time = datetime.utcnow()

        hours_passed = (current_time - event_time).total_seconds() / 3600
        half_life_hours = self.decay_half_life_days * 24

        # Exponential decay
        decay_factor = 2 ** (-hours_passed / half_life_hours)
        return max(0.0, min(1.0, decay_factor))

    def add_event(self, user_id: str, event: UserEventSchema):
        """
        Add event to context manager with importance scoring

        Uses existing importance scoring algorithm:
        - Recency: 40% (time decay)
        - Base importance: 30% (from event)
        - Frequency: 20% (count of similar events)
        - Feedback: 10% (from metadata)

        Args:
            user_id: User identifier
            event: Event to add
        """
        events_queue = self._user_events[user_id]

        # Calculate time decay (40% recency)
        time_decay = self.calculate_time_decay(event.timestamp)

        # Count similar events for frequency (20% frequency)
        similar_events = [
            e for e in events_queue if e.get("event_type") == event.event_type
        ]
        frequency_factor = min(len(similar_events) / 10, 1.0)

        # Base importance (30%)
        base_importance = event.importance_score

        # User feedback (10%)
        feedback_factor = event.metadata.get("has_feedback", False) * 0.1

        # Combined importance score
        adjusted_importance = (
            base_importance * 0.3
            + time_decay * 0.4
            + frequency_factor * 0.2
            + feedback_factor * 0.1
        )

        # Store with adjusted importance
        event_dict = event.dict()
        event_dict["adjusted_importance"] = adjusted_importance
        event_dict["added_at"] = datetime.utcnow()
        event_dict["frequency_count"] = len(similar_events)

        events_queue.append(event_dict)
        self._cache_timestamps[user_id] = datetime.utcnow()

        logger.debug(
            f"Added event for user {user_id}: type={event.event_type}, "
            f"adjusted_importance={adjusted_importance:.2f}"
        )

    def get_context(
        self, user_id: str, max_events: int = 10, min_importance: float = 0.1
    ) -> Dict[str, Any]:
        """
        Get user context with events filtered by importance

        Args:
            user_id: User identifier
            max_events: Maximum number of events to return
            min_importance: Minimum importance threshold

        Returns:
            Dictionary with recent events, summary, and metadata
        """
        # Check cache TTL
        if user_id in self._cache_timestamps:
            age = datetime.utcnow() - self._cache_timestamps[user_id]
            if age.total_seconds() > self.cache_ttl_minutes * 60:
                # Cache expired, load from database
                logger.info(f"Cache expired for user {user_id}, loading from database")
                # This will be implemented when EventStorageService is ready
                pass

        if user_id not in self._user_events:
            return {
                "user_id": user_id,
                "recent_events": [],
                "event_count": 0,
                "summary": "No recent activity recorded.",
                "retrieved_at": datetime.utcnow().isoformat(),
            }

        events = list(self._user_events[user_id])

        # Sort by adjusted importance (descending)
        events.sort(key=lambda x: x.get("adjusted_importance", 0), reverse=True)

        # Filter by minimum importance and limit
        filtered_events = [
            event
            for event in events
            if event.get("adjusted_importance", 0) >= min_importance
        ][:max_events]

        # Generate summary
        summary = self._generate_summary(user_id, filtered_events)

        return {
            "user_id": user_id,
            "recent_events": filtered_events,
            "event_count": len(filtered_events),
            "summary": summary,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    def _generate_summary(self, user_id: str, events: List[Dict]) -> str:
        """
        Generate human-readable summary of events

        Args:
            user_id: User identifier
            events: List of events

        Returns:
            Summary string
        """
        if not events:
            return "No recent activity recorded."

        # Group by event type
        event_counts = defaultdict(int)
        for event in events:
            event_type = event.get("event_type", "unknown")
            event_counts[event_type] += 1

        summary_parts = []
        for event_type, count in sorted(
            event_counts.items(), key=lambda x: x[1], reverse=True
        ):
            if count == 1:
                summary_parts.append(f"1 {event_type.replace('_', ' ')}")
            else:
                summary_parts.append(f"{count} {event_type.replace('_', ' ')}s")

        return f"Recent activity: {', '.join(summary_parts)}."

    def get_events_by_type(
        self, user_id: str, event_type: str, limit: int = 10
    ) -> List[Dict]:
        """
        Get events of a specific type for a user

        Args:
            user_id: User identifier
            event_type: Event type to filter
            limit: Maximum number of events

        Returns:
            List of events
        """
        if user_id not in self._user_events:
            return []

        events = [
            e for e in self._user_events[user_id] if e.get("event_type") == event_type
        ]

        # Sort by adjusted importance
        events.sort(key=lambda x: x.get("adjusted_importance", 0), reverse=True)

        return events[:limit]

    def get_cache_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get cache statistics for a user

        Args:
            user_id: User identifier

        Returns:
            Dictionary with cache statistics
        """
        if user_id not in self._user_events:
            return {
                "user_id": user_id,
                "event_count": 0,
                "cache_age_seconds": 0,
                "is_expired": True,
            }

        age = datetime.utcnow() - self._cache_timestamps[user_id]
        is_expired = age.total_seconds() > self.cache_ttl_minutes * 60

        return {
            "user_id": user_id,
            "event_count": len(self._user_events[user_id]),
            "cache_age_seconds": age.total_seconds(),
            "is_expired": is_expired,
            "max_events": self.max_events_per_user,
        }

    def clear_cache(self, user_id: str):
        """
        Clear cache for a specific user

        Args:
            user_id: User identifier
        """
        if user_id in self._user_events:
            del self._user_events[user_id]
        if user_id in self._cache_timestamps:
            del self._cache_timestamps[user_id]

        logger.info(f"Cleared cache for user {user_id}")

    def clear_all_cache(self):
        """Clear all caches"""
        self._user_events.clear()
        self._cache_timestamps.clear()

        logger.info("Cleared all caches")

    def get_all_cached_users(self) -> List[str]:
        """
        Get list of all users with cached events

        Returns:
            List of user IDs
        """
        return list(self._user_events.keys())
