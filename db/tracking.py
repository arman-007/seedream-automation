import logging
from datetime import datetime, timezone
from pymongo import ASCENDING
from db.schemas import new_tracking_document

logger = logging.getLogger(__name__)

# Status constants
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def ensure_indexes(collection):
    """Create indexes on the tracking collection if they don't exist."""
    collection.create_index([("api_player_id", ASCENDING)], unique=True)
    collection.create_index([("status", ASCENDING)])
    logger.debug(f"Indexes ensured on {collection.name}")


def get_tracking_collection(db, collection_name):
    """Return the tracking Collection with indexes ensured."""
    collection = db[collection_name]
    ensure_indexes(collection)
    return collection


def get_completed_player_ids(collection):
    """Return set of api_player_ids with status == 'completed'."""
    cursor = collection.find(
        {"status": STATUS_COMPLETED},
        {"api_player_id": 1, "_id": 0},
    )
    return {doc["api_player_id"] for doc in cursor}


def get_failed_player_ids(collection):
    """Return set of api_player_ids with status == 'failed'."""
    cursor = collection.find(
        {"status": STATUS_FAILED},
        {"api_player_id": 1, "_id": 0},
    )
    return {doc["api_player_id"] for doc in cursor}


def create_pending_record(collection, api_player_id, source_image_url, style, mode):
    """
    Insert or update a tracking document to 'pending' status.
    Uses upsert on api_player_id so reruns are idempotent.
    """
    now = datetime.now(timezone.utc)
    result = collection.update_one(
        {"api_player_id": api_player_id},
        {
            "$set": {
                "status": STATUS_PENDING,
                "source_image_url": source_image_url,
                "style": style,
                "mode": mode,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "retry_count": 0,
                "error_log": [],
                "output_path": None,
                "generation_duration_seconds": None,
                "spaces_url": None,
            },
        },
        upsert=True,
    )
    if result.upserted_id:
        logger.debug(f"Created pending record for player {api_player_id}")
    else:
        logger.debug(f"Updated existing record for player {api_player_id} to pending")


def mark_processing(collection, api_player_id):
    """Set status to 'processing' and update timestamp."""
    collection.update_one(
        {"api_player_id": api_player_id},
        {
            "$set": {
                "status": STATUS_PROCESSING,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


def mark_completed(collection, api_player_id, output_path, duration_seconds, spaces_url=None):
    """Set status to 'completed', record output_path, duration, and spaces_url."""
    fields = {
        "status": STATUS_COMPLETED,
        "output_path": output_path,
        "generation_duration_seconds": duration_seconds,
        "updated_at": datetime.now(timezone.utc),
    }
    if spaces_url is not None:
        fields["spaces_url"] = spaces_url
    collection.update_one(
        {"api_player_id": api_player_id},
        {"$set": fields},
    )


def mark_failed(collection, api_player_id, error_message):
    """
    Set status to 'failed', increment retry_count,
    push error_message into error_log array.
    """
    collection.update_one(
        {"api_player_id": api_player_id},
        {
            "$set": {
                "status": STATUS_FAILED,
                "updated_at": datetime.now(timezone.utc),
            },
            "$inc": {"retry_count": 1},
            "$push": {"error_log": error_message},
        },
    )


def get_failed_players(collection, max_retries=3):
    """Return failed records with retry_count < max_retries."""
    cursor = collection.find({
        "status": STATUS_FAILED,
        "retry_count": {"$lt": max_retries},
    })
    return list(cursor)


def reset_stuck_processing(collection):
    """
    Reset any records stuck in 'processing' state back to 'failed'.
    This recovers from a previous pipeline run that crashed mid-execution.
    """
    result = collection.update_many(
        {"status": STATUS_PROCESSING},
        {
            "$set": {
                "status": STATUS_FAILED,
                "updated_at": datetime.now(timezone.utc),
            },
            "$inc": {"retry_count": 1},
            "$push": {"error_log": "Interrupted: found in processing state at pipeline startup"},
        },
    )
    if result.modified_count:
        logger.warning(
            f"Reset {result.modified_count} stuck 'processing' record(s) to 'failed'"
        )
    else:
        logger.debug("No stuck processing records found.")
