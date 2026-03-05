"""Announcement endpoints for the High School Management System API."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from ..database import announcements_collection, teachers_collection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _validate_teacher(teacher_username: Optional[str]) -> Dict[str, Any]:
    """Validate teacher identity for write and management operations."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def _parse_iso_date(value: Optional[str], field_name: str, required: bool = False) -> Optional[str]:
    """Validate a YYYY-MM-DD date and return normalized value."""
    if not value:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return None

    try:
        normalized = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        return normalized
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format"
        ) from exc


def _validate_announcement_payload(
    title: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """Validate and normalize announcement payload fields."""
    clean_title = title.strip()
    clean_message = message.strip()

    if not clean_title:
        raise HTTPException(status_code=400, detail="title is required")

    if not clean_message:
        raise HTTPException(status_code=400, detail="message is required")

    normalized_start = _parse_iso_date(start_date, "start_date", required=False)
    normalized_expiration = _parse_iso_date(
        expiration_date,
        "expiration_date",
        required=True
    )

    if normalized_start and normalized_start > normalized_expiration:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be later than expiration_date"
        )

    return {
        "title": clean_title,
        "message": clean_message,
        "start_date": normalized_start,
        "expiration_date": normalized_expiration
    }


def _parse_object_id(announcement_id: str) -> ObjectId:
    """Validate ObjectId input from path parameter."""
    try:
        return ObjectId(announcement_id)
    except InvalidId as exc:
        raise HTTPException(status_code=400, detail="Invalid announcement id") from exc


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_active_announcements() -> List[Dict[str, Any]]:
    """Get active announcements for public display in the banner."""
    today = datetime.utcnow().date().isoformat()
    query = {
        "$and": [
            {"expiration_date": {"$gte": today}},
            {
                "$or": [
                    {"start_date": None},
                    {"start_date": {"$lte": today}}
                ]
            }
        ]
    }

    try:
        announcements: List[Dict[str, Any]] = []
        for item in announcements_collection.find(query).sort("expiration_date", 1):
            item["id"] = str(item.pop("_id"))
            announcements.append(item)
        return announcements
    except PyMongoError:
        logger.exception("Failed to fetch active announcements")
        raise HTTPException(
            status_code=500,
            detail="Unable to load announcements right now"
        )


@router.get("/manage", response_model=List[Dict[str, Any]])
def list_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements for management UI. Requires authentication."""
    _validate_teacher(teacher_username)

    try:
        announcements: List[Dict[str, Any]] = []
        for item in announcements_collection.find().sort("expiration_date", 1):
            item["id"] = str(item.pop("_id"))
            announcements.append(item)
        return announcements
    except PyMongoError:
        logger.exception("Failed to fetch announcements for management")
        raise HTTPException(
            status_code=500,
            detail="Unable to load announcements right now"
        )


@router.post("")
def create_announcement(
    title: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Create a new announcement. Requires authentication."""
    _validate_teacher(teacher_username)
    payload = _validate_announcement_payload(
        title=title,
        message=message,
        start_date=start_date,
        expiration_date=expiration_date
    )

    try:
        result = announcements_collection.insert_one(payload)
        return {
            "message": "Announcement created",
            "id": str(result.inserted_id)
        }
    except PyMongoError:
        logger.exception("Failed to create announcement")
        raise HTTPException(
            status_code=500,
            detail="Unable to save announcement right now"
        )


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    title: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Update an existing announcement. Requires authentication."""
    _validate_teacher(teacher_username)
    payload = _validate_announcement_payload(
        title=title,
        message=message,
        start_date=start_date,
        expiration_date=expiration_date
    )
    object_id = _parse_object_id(announcement_id)

    try:
        result = announcements_collection.update_one(
            {"_id": object_id},
            {"$set": payload}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Announcement not found")

        return {"message": "Announcement updated"}
    except HTTPException:
        raise
    except PyMongoError:
        logger.exception("Failed to update announcement")
        raise HTTPException(
            status_code=500,
            detail="Unable to update announcement right now"
        )


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement. Requires authentication."""
    _validate_teacher(teacher_username)
    object_id = _parse_object_id(announcement_id)

    try:
        result = announcements_collection.delete_one({"_id": object_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Announcement not found")

        return {"message": "Announcement deleted"}
    except HTTPException:
        raise
    except PyMongoError:
        logger.exception("Failed to delete announcement")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete announcement right now"
        )
