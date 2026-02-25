import argparse
import json
import logging
import sys
from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Seedream batch pipeline: generate styled images for players"
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max players to process (0 = all)",
    )
    parser.add_argument(
        "--player-ids", type=str, default=None,
        help="Comma-separated api_player_ids to process",
    )
    parser.add_argument(
        "--filter", type=str, default=None,
        help='JSON MongoDB query filter (e.g. \'{"position": "Goalkeeper"}\')',
    )
    parser.add_argument(
        "--style", default="Photo",
        help="Style preset (default: Photo)",
    )
    parser.add_argument(
        "--mode", default="General",
        help="Edit mode (default: General)",
    )
    parser.add_argument(
        "--prompt-file", default="MASTER_PROMPT.txt",
        help="Path to prompt file",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory (overrides OUTPUT_DIR env var)",
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Retry previously failed players instead of fetching new",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max retry attempts for failed players (default: 3)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Parse player IDs
    player_ids = None
    if args.player_ids:
        player_ids = [int(x.strip()) for x in args.player_ids.split(",")]

    # Parse custom filter
    custom_filter = None
    if args.filter:
        try:
            custom_filter = json.loads(args.filter)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON filter: {e}")
            sys.exit(1)

    from pipeline.runner import run_pipeline

    summary = run_pipeline(
        limit=args.limit,
        player_ids=player_ids,
        custom_filter=custom_filter,
        style=args.style,
        mode=args.mode,
        prompt_file=args.prompt_file,
        output_dir=args.output_dir,
        max_retries=args.max_retries,
        retry_failed=args.retry_failed,
    )

    # Print summary
    print("\n" + "=" * 50)
    print("PIPELINE SUMMARY")
    print("=" * 50)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("=" * 50)


if __name__ == "__main__":
    main()
