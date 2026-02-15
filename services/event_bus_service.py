"""
Event bus service for pub/sub pattern
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
import logging

from schemas.events import UserEventSchema

logger = logging.getLogger(__name__)


class EventBusService:
    """
    Event bus for pub/sub pattern with local and optional Redis support.

    This service provides a publish/subscribe mechanism for distributing
    events to multiple subscribers. It supports both synchronous and
    asynchronous event handlers.

    Features:
    - Local in-memory pub/sub
    - Optional Redis pub/sub for distributed systems
    - Async and sync handler support
    - Error isolation (one handler error doesn't affect others)
    """

    def __init__(self):
        """Initialize the event bus"""
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._redis_client = None
        self._use_redis = False

    async def initialize_redis(self, redis_url: str):
        """
        Initialize Redis client for distributed pub/sub.

        Args:
            redis_url: Redis connection URL
        """
        try:
            import redis.asyncio as redis

            self._redis_client = redis.from_url(redis_url, decode_responses=True)
            self._use_redis = True
            logger.info("Redis event bus initialized")
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis: {e}, using local subscribers only"
            )
            self._use_redis = False

    def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to handle events
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to event type: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """
        Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Callback function to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from event type: {event_type}")
            except ValueError:
                # Handler not in list
                pass

    async def publish(self, event: UserEventSchema):
        """
        Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        # Local subscribers
        for handler in self._subscribers.get(event.event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type}: {e}")

        # Redis pub/sub for distributed systems (optional)
        if self._use_redis and self._redis_client:
            try:
                await self._redis_client.publish(
                    f"events:{event.user_id}:{event.event_type}", event.json()
                )
            except Exception as e:
                logger.warning(f"Failed to publish to Redis: {e}")

    async def publish_batch(self, events: List[UserEventSchema]):
        """
        Publish multiple events in batch.

        Args:
            events: List of events to publish
        """
        for event in events:
            await self.publish(event)

    def get_subscriber_count(self, event_type: str) -> int:
        """
        Get number of subscribers for an event type.

        Args:
            event_type: Event type to check

        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))

    def get_all_subscribers(self) -> Dict[str, List[Callable]]:
        """
        Get all subscribers (for debugging/monitoring).

        Returns:
            Dictionary mapping event types to handler lists
        """
        return dict(self._subscribers)
