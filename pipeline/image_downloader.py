import os
import logging
import requests

logger = logging.getLogger(__name__)


def download_player_image(url, output_dir, api_player_id):
    """
    Download a player's source image to output_dir.
    Saves as {api_player_id}_source.png.
    Returns the local file path.
    Raises requests.RequestException on failure.
    """
    filename = f"{api_player_id}_source.png"
    save_path = os.path.join(output_dir, filename)

    logger.info(f"Downloading source image for player {api_player_id}...")
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)

    logger.info(f"Source image saved to {save_path}")
    return save_path
