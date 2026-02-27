import os
import time
import logging
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from generate_image import run_generation_on_page, check_session, read_master_prompt
from login_helper import login_and_save_state
from db.connection import get_source_db, get_tracking_db
from db.source import get_all_players, get_players_by_ids
from db.tracking import (
    get_tracking_collection,
    get_completed_player_ids,
    get_failed_player_ids,
    create_pending_record,
    mark_processing,
    mark_completed,
    mark_failed,
    get_failed_players,
    reset_stuck_processing,
)
from pipeline.image_downloader import download_player_image
from pipeline.uploader import upload_image_to_spaces

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

    # 1. Validate session — auto-login if expired
    logger.info("Checking Seedream session...")
    if not check_session():
        logger.warning("Session expired or missing. Attempting automatic login...")
        if not login_and_save_state():
            logger.error(
                "Automatic login failed. "
                "Check EMAIL/PASSWORD in .env and verify the account is accessible."
            )
            return {"error": "Login failed"}
        # Re-check after login
        if not check_session():
            logger.error("Session still invalid after login attempt.")
            return {"error": "Session invalid after login"}
        logger.info("Auto-login succeeded.")
    else:
        logger.info("Session is valid.")

    # Connect to databases
    source_collection_name = os.getenv("SOURCE_COLLECTION", "players")
    tracking_collection_name = os.getenv("TRACKING_COLLECTION", "generation_tracking")

    logger.info("Connecting to source database...")
    source_client, source_db = get_source_db()

    logger.info("Connecting to tracking database...")
    tracking_client, tracking_db = get_tracking_db()
    tracking_col = get_tracking_collection(tracking_db, tracking_collection_name)

    try:
        # 2. Reset any records stuck in 'processing' from a previous crashed run
        reset_stuck_processing(tracking_col)

        # Build work list
        if retry_failed:
            logger.info(f"Fetching failed players (max_retries={max_retries})...")
            work_list = get_failed_players(tracking_col, max_retries)
            total_fetched = len(work_list)
            skipped_completed = 0
            skipped_failed = 0
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

            # Filter out completed and failed — failed only retry via --retry-failed
            completed_ids = get_completed_player_ids(tracking_col)
            failed_ids = get_failed_player_ids(tracking_col)
            skip_ids = completed_ids | failed_ids
            work_list = [p for p in players if p.get("api_player_id") not in skip_ids]
            skipped_completed = len([p for p in players if p.get("api_player_id") in completed_ids])
            skipped_failed = len([p for p in players if p.get("api_player_id") in failed_ids])
            skipped = skipped_completed + skipped_failed

        # 3. Filter out players with no image URL
        no_image = [p for p in work_list if not p.get("image", "").strip()]
        for p in no_image:
            logger.warning(
                f"Skipping player {p.get('api_player_id')} "
                f"({p.get('display_name') or p.get('name', 'Unknown')}): no image URL"
            )
        work_list = [p for p in work_list if p.get("image", "").strip()]
        skipped_no_image = len(no_image)

        logger.info(
            f"Found {len(work_list)} players to process "
            f"({skipped} skipped as already completed, "
            f"{skipped_no_image} skipped: no image URL)"
        )

        if not work_list:
            logger.info("Nothing to do.")
            return {
                "total_fetched": total_fetched,
                "skipped_completed": skipped_completed,
                "skipped_failed": skipped_failed,
                "skipped_no_image": skipped_no_image,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
            }

        succeeded = 0
        failed = 0

        # 4. Launch one browser for the entire batch
        state_path = "state.json"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=state_path if os.path.exists(state_path) else None
            )
            try:
                for i, player in enumerate(work_list, 1):
                    pid = player.get("api_player_id")
                    image_url = player.get("image", "")
                    player_name = player.get("display_name") or player.get("name", "Unknown")

                    logger.info(f"[{i}/{len(work_list)}] Processing player {pid} ({player_name})")
                    start_time = time.time()

                    page = context.new_page()
                    page.on("console", lambda msg: logger.debug(f"Browser: {msg.text}"))

                    try:
                        # Create/update tracking record
                        create_pending_record(tracking_col, pid, image_url, style, mode)
                        mark_processing(tracking_col, pid)

                        # Download source image
                        source_path = download_player_image(image_url, output_dir, pid)

                        # Generate styled image
                        output_path = os.path.join(output_dir, f"{pid}_generated.png")
                        run_generation_on_page(page, source_path, prompt_text, output_path, style, mode)

                        # Verify output exists
                        if not os.path.exists(output_path):
                            raise FileNotFoundError(f"Output file not created: {output_path}")

                        # Upload to DO Spaces
                        logger.info(f"Uploading player {pid} image to DO Spaces...")
                        spaces_url = upload_image_to_spaces(output_path, pid)

                        duration = time.time() - start_time
                        mark_completed(tracking_col, pid, output_path, round(duration, 2), spaces_url)

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
                        try:
                            page.screenshot(path=os.path.join(output_dir, f"{pid}_error.png"))
                        except Exception:
                            pass

                    finally:
                        page.close()

            finally:
                browser.close()

        summary = {
            "total_fetched": total_fetched,
            "skipped_completed": skipped_completed,
            "skipped_failed": skipped_failed,
            "skipped_no_image": skipped_no_image,
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
