"""
Event trigger utilities for data recording APIs

This module provides helper functions to easily publish events
when users record data through the API endpoints.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from services.event_bus_service import EventBusService
from schemas.events import UserEventSchema

logger = logging.getLogger(__name__)

# Global event bus instance
event_bus = EventBusService()


def calculate_weight_importance(weight_data: Dict[str, Any]) -> float:
    """
    Calculate importance score for weight recording events.

    Higher importance for:
    - Large weight changes
    - First weight recording
    - Weight goal milestones
    """
    base_score = 0.7

    # Could add logic here for weight change significance
    # For now, use a moderate importance

    return min(base_score, 1.0)


def calculate_meal_importance(meal_data: Dict[str, Any]) -> float:
    """
    Calculate importance score for meal recording events.

    Higher importance for:
    - High calorie meals
    - Meals with photos (AI recognition)
    - Large portions
    """
    base_score = 0.5

    # Adjust based on calories
    calories = meal_data.get("total_calories", 0)
    if calories > 800:
        base_score += 0.2
    elif calories > 500:
        base_score += 0.1

    return min(base_score, 1.0)


def calculate_exercise_importance(exercise_data: Dict[str, Any]) -> float:
    """
    Calculate importance score for exercise recording events.

    Higher importance for:
    - Longer duration exercises
    - Higher intensity exercises
    - More calories burned
    """
    base_score = 0.6

    # Adjust based on duration
    duration = exercise_data.get("duration_minutes", 0)
    if duration > 60:
        base_score += 0.2
    elif duration > 30:
        base_score += 0.1

    return min(base_score, 1.0)


def calculate_water_importance(water_data: Dict[str, Any]) -> float:
    """
    Calculate importance score for water recording events.

    Water recording typically has lower importance.
    """
    return 0.4


def calculate_sleep_importance(sleep_data: Dict[str, Any]) -> float:
    """
    Calculate importance score for sleep recording events.

    Higher importance for:
    - Poor sleep quality
    - Significant sleep duration changes
    """
    base_score = 0.6

    # Adjust based on quality
    quality = sleep_data.get("quality", 0)
    if quality and quality < 60:
        base_score += 0.2
    elif quality and quality >= 80:
        base_score += 0.1

    return min(base_score, 1.0)


async def publish_weight_recorded_event(
    user_id: int,
    weight: float,
    body_fat: Optional[float],
    record_date: datetime,
    record_id: Optional[int] = None,
):
    """
    Publish weight recorded event.

    Args:
        user_id: User ID
        weight: Weight in kg
        body_fat: Body fat percentage (optional)
        record_date: Date of recording
        record_id: Database record ID (optional)
    """
    try:
        event_data = {
            "weight_kg": weight,
            "record_date": record_date.isoformat()
            if hasattr(record_date, "isoformat")
            else str(record_date),
            "record_id": record_id,
        }

        if body_fat is not None:
            event_data["body_fat_percentage"] = body_fat

        importance = calculate_weight_importance(event_data)

        event = UserEventSchema(
            user_id=str(user_id),
            event_type="weight_recorded",
            event_data=event_data,
            importance_score=importance,
            timestamp=datetime.utcnow(),
        )

        await event_bus.publish(event)
        logger.debug(f"Published weight_recorded event for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish weight event: {e}")


async def publish_meal_recorded_event(
    user_id: int,
    meal_type: str,
    total_calories: int,
    food_items: list,
    record_id: Optional[int] = None,
    photo_url: Optional[str] = None,
):
    """
    Publish meal recorded event.

    Args:
        user_id: User ID
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
        total_calories: Total calories
        food_items: List of food items
        record_id: Database record ID (optional)
        photo_url: Photo URL if uploaded (optional)
    """
    try:
        event_data = {
            "meal_type": meal_type,
            "total_calories": total_calories,
            "food_items": food_items,
            "record_id": record_id,
            "has_photo": photo_url is not None,
        }

        importance = calculate_meal_importance(event_data)

        event = UserEventSchema(
            user_id=str(user_id),
            event_type="meal_recorded",
            event_data=event_data,
            importance_score=importance,
            timestamp=datetime.utcnow(),
        )

        await event_bus.publish(event)
        logger.debug(f"Published meal_recorded event for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish meal event: {e}")


async def publish_exercise_recorded_event(
    user_id: int,
    exercise_type: str,
    duration_minutes: int,
    calories_burned: Optional[int] = None,
    intensity: Optional[str] = None,
    record_id: Optional[int] = None,
):
    """
    Publish exercise recorded event.

    Args:
        user_id: User ID
        exercise_type: Type of exercise
        duration_minutes: Duration in minutes
        calories_burned: Calories burned (optional)
        intensity: Exercise intensity (optional)
        record_id: Database record ID (optional)
    """
    try:
        event_data = {
            "exercise_type": exercise_type,
            "duration_minutes": duration_minutes,
            "record_id": record_id,
        }

        if calories_burned is not None:
            event_data["calories_burned"] = calories_burned

        if intensity is not None:
            event_data["intensity"] = intensity

        importance = calculate_exercise_importance(event_data)

        event = UserEventSchema(
            user_id=str(user_id),
            event_type="exercise_recorded",
            event_data=event_data,
            importance_score=importance,
            timestamp=datetime.utcnow(),
        )

        await event_bus.publish(event)
        logger.debug(f"Published exercise_recorded event for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish exercise event: {e}")


async def publish_water_recorded_event(
    user_id: int, amount_ml: int, record_id: Optional[int] = None
):
    """
    Publish water recorded event.

    Args:
        user_id: User ID
        amount_ml: Amount in milliliters
        record_id: Database record ID (optional)
    """
    try:
        event_data = {"amount_ml": amount_ml, "record_id": record_id}

        importance = calculate_water_importance(event_data)

        event = UserEventSchema(
            user_id=str(user_id),
            event_type="water_recorded",
            event_data=event_data,
            importance_score=importance,
            timestamp=datetime.utcnow(),
        )

        await event_bus.publish(event)
        logger.debug(f"Published water_recorded event for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish water event: {e}")


async def publish_sleep_recorded_event(
    user_id: int,
    bed_time: datetime,
    wake_time: datetime,
    total_minutes: int,
    quality: Optional[int] = None,
    record_id: Optional[int] = None,
):
    """
    Publish sleep recorded event.

    Args:
        user_id: User ID
        bed_time: Bed time
        wake_time: Wake time
        total_minutes: Total sleep duration in minutes
        quality: Sleep quality score (optional)
        record_id: Database record ID (optional)
    """
    try:
        event_data = {
            "duration_hours": round(total_minutes / 60, 1),
            "total_minutes": total_minutes,
            "bed_time": bed_time.isoformat()
            if hasattr(bed_time, "isoformat")
            else str(bed_time),
            "wake_time": wake_time.isoformat()
            if hasattr(wake_time, "isoformat")
            else str(wake_time),
            "record_id": record_id,
        }

        if quality is not None:
            event_data["quality"] = quality

        importance = calculate_sleep_importance(event_data)

        event = UserEventSchema(
            user_id=str(user_id),
            event_type="sleep_recorded",
            event_data=event_data,
            importance_score=importance,
            timestamp=datetime.utcnow(),
        )

        await event_bus.publish(event)
        logger.debug(f"Published sleep_recorded event for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish sleep event: {e}")
