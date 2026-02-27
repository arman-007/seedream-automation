import os
import logging
from urllib.parse import urlparse
import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

SPACES_FOLDER = "image_pipeline"


def _get_spaces_client():
    origin_endpoint = os.getenv("DO_ORIGIN_ENDPOINT", "")
    hostname = urlparse(origin_endpoint).hostname or ""
    # hostname: fantasyfootball.sgp1.digitaloceanspaces.com → region: sgp1
    parts = hostname.split(".")
    region = parts[1] if len(parts) >= 2 else "sgp1"
    regional_endpoint = f"https://{region}.digitaloceanspaces.com"

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=regional_endpoint,
        aws_access_key_id=os.getenv("DO_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("DO_BUCKET_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
    )


def upload_image_to_spaces(local_path, api_player_id):
    """
    Upload a generated player image to DO Spaces.

    Args:
        local_path: Path to the local PNG file.
        api_player_id: Player ID used as the filename.

    Returns:
        CDN URL string for the uploaded object.
    """
    bucket = os.getenv("DO_BUCKET_NAME")
    cdn_endpoint = os.getenv("DO_CDN_ENDPOINT", "").rstrip("/")
    object_key = f"{SPACES_FOLDER}/{api_player_id}.png"

    client = _get_spaces_client()
    client.upload_file(
        local_path,
        bucket,
        object_key,
        ExtraArgs={"ACL": "public-read", "ContentType": "image/png"},
    )

    cdn_url = f"{cdn_endpoint}/{object_key}"
    logger.info(f"Uploaded player {api_player_id} → {cdn_url}")
    return cdn_url
