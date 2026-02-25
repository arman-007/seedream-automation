import os
import time
import logging
from dotenv import load_dotenv

from generate_image import generate_image, read_master_prompt
from db.connection import get_source_db, get_tracking_db
from db.source import get_all_players, get_players_by_ids
from db.tracking import (
    get_tracking_collection,
    get_completed_player_ids,
    create_pending_record,
    mark_processing,
    mark_completed,
    mark_failed,
    get_failed_players,
)
from pipeline.image_downloader import download_player_image

logger = logging.getLogger(__name__)


def run_pipeline(
    *,
    limit=0,
    player_ids=None,
    custom_filter=None,
    style="Photo",
    mode="General",
    prompt_file="MASTER_PROMPT.txt",
    output_dir=None,
    max_retries=3,
    retry_failed=False,
):
    """
    Main pipeline function. Fetches players from source DB,
    generates styled images, and tracks progress in tracking DB.

    Returns a summary dict with counts.
    """
    load_dotenv()

    # Resolve output directory
    output_dir = output_dir or os.getenv("OUTPUT_DIR", "./output")
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Read prompt
    prompt_text = read_master_prompt(prompt_file)
    if not prompt_text:
        logger.error(f"Empty prompt or file not found: {prompt_file}")
        return {"error": "Empty prompt"}

    # Connect to databases
    source_collection_name = os.getenv("SOURCE_COLLECTION", "players")
    tracking_collection_name = os.getenv("TRACKING_COLLECTION", "generation_tracking")

    logger.info("Connecting to source database...")
    source_client, source_db = get_source_db()

    logger.info("Connecting to tracking database...")
    tracking_client, tracking_db = get_tracking_db()
    tracking_col = get_tracking_collection(tracking_db, tracking_collection_name)

    try:
        # Build work list
        if retry_failed:
            logger.info(f"Fetching failed players (max_retries={max_retries})...")
            work_list = get_failed_players(tracking_col, max_retries)
            total_fetched = len(work_list)
            skipped = 0
            # Convert tracking records to player-like dicts for uniform processing
            for item in work_list:
                item["image"] = item.get("source_image_url", "")
        else:
            # Fetch from source
            if player_ids:
                logger.info(f"Fetching {len(player_ids)} specific players...")
                players = get_players_by_ids(source_db, source_collection_name, player_ids)
            else:
                logger.info("Fetching players from source...")
                players = get_all_players(
                    source_db,
                    source_collection_name,
                    filter_query=custom_filter,
                    limit=limit,
                )

            total_fetched = len(players)

            # Filter out completed
            completed_ids = get_completed_player_ids(tracking_col)
            work_list = [p for p in players if p.get("api_player_id") not in completed_ids]
            skipped = total_fetched - len(work_list)

        logger.info(
            f"Found {len(work_list)} players to process "
            f"({skipped} skipped as already completed)"
        )

        if not work_list:
            logger.info("Nothing to do.")
            return {
                "total_fetched": total_fetched,
                "skipped_completed": skipped,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
            }

        succeeded = 0
        failed = 0

        for i, player in enumerate(work_list, 1):
            pid = player.get("api_player_id")
            image_url = player.get("image", "")
            player_name = player.get("display_name") or player.get("name", "Unknown")

            logger.info(f"[{i}/{len(work_list)}] Processing player {pid} ({player_name})")
            start_time = time.time()

            try:
                # Create/update tracking record
                create_pending_record(tracking_col, pid, image_url, style, mode)
                mark_processing(tracking_col, pid)

                # Download source image
                source_path = download_player_image(image_url, output_dir, pid)

                # Generate styled image
                output_path = os.path.join(output_dir, f"{pid}_generated.png")
                generate_image(source_path, prompt_text, output_path, style, mode)

                # Verify output exists
                if not os.path.exists(output_path):
                    raise FileNotFoundError(f"Output file not created: {output_path}")

                duration = time.time() - start_time
                mark_completed(tracking_col, pid, output_path, round(duration, 2))

                # Clean up source image
                if os.path.exists(source_path):
                    os.remove(source_path)

                succeeded += 1
                logger.info(f"Completed player {pid} in {duration:.1f}s")

            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"{type(e).__name__}: {str(e)}"
                mark_failed(tracking_col, pid, error_msg)
                failed += 1
                logger.warning(f"Failed player {pid}: {error_msg}")

        summary = {
            "total_fetched": total_fetched,
            "skipped_completed": skipped,
            "processed": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
        }
        logger.info(f"Pipeline complete: {summary}")
        return summary

    finally:
        source_client.close()
        tracking_client.close()
        logger.debug("Database connections closed.")
