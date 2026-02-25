import os
import time
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)

DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 2


def get_mongo_client(
    uri,
    *,
    retry_attempts=DEFAULT_RETRY_ATTEMPTS,
    retry_delay=DEFAULT_RETRY_DELAY_SECONDS,
    server_selection_timeout_ms=5000,
):
    """
    Create a MongoClient with retry logic.
    Pings the server to verify connectivity.
    Raises ConnectionFailure after all retries exhausted.
    """
    for attempt in range(1, retry_attempts + 1):
        try:
            client = MongoClient(
                uri,
                serverSelectionTimeoutMS=server_selection_timeout_ms,
            )
            client.admin.command("ping")
            logger.info(f"DB connected to {uri}")
            return client
        except ConnectionFailure as e:
            logger.warning(
                f"DB connection failed (attempt {attempt}/{retry_attempts}): {e}"
            )
            if attempt < retry_attempts:
                time.sleep(retry_delay)
            else:
                raise ConnectionFailure(
                    f"Failed to connect to {uri} after {retry_attempts} attempts: {e}"
                )


def get_source_db():
    """
    Returns (MongoClient, Database) for the source player database.
    Reads SOURCE_DB_URL and SOURCE_DB_NAME from environment.
    """
    uri = os.getenv("SOURCE_DB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("SOURCE_DB_NAME", "Fantasy_Global_Livescore")
    client = get_mongo_client(uri)
    return client, client[db_name]


def get_tracking_db():
    """
    Returns (MongoClient, Database) for the tracking database.
    Reads TRACKING_DB_URL and TRACKING_DB_NAME from environment.
    """
    uri = os.getenv("TRACKING_DB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("TRACKING_DB_NAME", "seedream_tracking")
    client = get_mongo_client(uri)
    return client, client[db_name]
