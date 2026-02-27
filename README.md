# Seedream Automation

Automate AI-powered stylized portrait generation for football players using [Seedream.pro](https://seedream.pro) and Playwright browser automation. Connects to a MongoDB source database of players, generates stylized face-only portraits, uploads results to DigitalOcean Spaces, and tracks every step in a separate tracking database.

## How It Works

```
MongoDB (players) ──> Pipeline Runner ──> Seedream.pro (AI editor) ──> DO Spaces (CDN)
                           │                                               │
                           └──── Tracking DB (status per player) <────────┘
```

1. **Source**: Player data lives in a MongoDB database (`Fantasy_Global_Livescore.players`). Each document has an `api_player_id` and an `image` URL pointing to a headshot photo.
2. **Session**: The pipeline checks if the Seedream session is valid before starting. If expired, it logs in automatically using `EMAIL`/`PASSWORD` from `.env` and saves a fresh session.
3. **Pipeline**: The runner fetches unprocessed players, downloads each source image, uploads it to Seedream's AI photo editor via headless Chromium, applies the stylization prompt, and waits for generation to complete.
4. **Upload**: Generated portraits are uploaded to DigitalOcean Spaces (`image_pipeline/{api_player_id}.png`) and the CDN URL is stored in the tracking record.
5. **Tracking**: A separate MongoDB database records the status of every player — `pending`, `processing`, `completed`, or `failed` — along with error logs, retry counts, duration, and the Spaces CDN URL.

## Features

- **Fully Unattended**: Runs headless end-to-end with no manual steps. Auto-login refreshes expired sessions automatically.
- **Browser Reuse**: One browser instance is shared across the entire batch — no per-player launch overhead.
- **Safe Restart**: Completed players are always skipped. Players stuck in `processing` from a crashed run are automatically reset on startup.
- **Explicit Retry**: Failed players are excluded from normal runs and only re-processed when you explicitly pass `--retry-failed`.
- **DO Spaces Upload**: Generated images are uploaded to a CDN-backed DigitalOcean Spaces bucket. The public CDN URL is saved to the tracking record.
- **Filterable Batches**: Process specific players by ID, apply MongoDB query filters, or cap with `--limit`.
- **Robust Download**: Multi-stage fallback to retrieve results (direct download → modal button → base64 extraction → static URL scraping).
- **Per-Player Error Isolation**: A failure on one player is logged and the batch continues.
- **Debug Artifacts**: Screenshots and HTML dumps are saved automatically on failure.

## Project Structure

```
seedream-automation/
├── run_pipeline.py            # CLI entry point
├── generate_image.py          # Playwright automation for Seedream.pro
│                              #   check_session()         — validates saved session
│                              #   run_generation_on_page() — generation on open page
│                              #   generate_image()         — standalone single-image wrapper
├── login_helper.py            # Headless login, saves state.json
├── verify_login.py            # Check if saved session is valid
├── MASTER_PROMPT.txt          # AI stylization prompt applied to every generation
├── .env                       # Credentials and config (gitignored)
├── .env.example               # Template for .env
├── state.json                 # Saved browser session (gitignored)
├── requirements.txt           # Python dependencies
├── db/
│   ├── connection.py          # MongoDB connection factory (retry logic)
│   ├── source.py              # Read players from source collection
│   ├── tracking.py            # CRUD for tracking collection
│   └── schemas.py             # Tracking document schema reference
├── pipeline/
│   ├── runner.py              # Batch orchestration loop
│   ├── image_downloader.py    # Download player image URLs to disk
│   └── uploader.py            # Upload generated images to DO Spaces
└── output/                    # Generated images (gitignored)
```

## Installation

### 1. Clone and enter the repo

```bash
git clone https://github.com/arman-007/seedream-automation.git
cd seedream-automation
```

### 2. Set up virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Seedream credentials (used for headless auto-login)
EMAIL=your-email@example.com
PASSWORD=your-password

# Source database (player data)
SOURCE_DB_URL=mongodb://localhost:27017
SOURCE_DB_NAME=Fantasy_Global_Livescore
SOURCE_COLLECTION=players

# Tracking database (pipeline progress)
# Supports embedded credentials: mongodb://user:pass@host:port
TRACKING_DB_URL=mongodb://localhost:27017
TRACKING_DB_NAME=seedream_tracking
TRACKING_COLLECTION=generation_tracking

# Output directory for generated images
OUTPUT_DIR=./output

# DigitalOcean Spaces
DO_ACCESS_KEY_ID=your-access-key
DO_BUCKET_SECRET_KEY=your-secret-key
DO_BUCKET_NAME=your-bucket-name
DO_ORIGIN_ENDPOINT=https://your-bucket.region.digitaloceanspaces.com
DO_CDN_ENDPOINT=https://your-bucket.region.cdn.digitaloceanspaces.com
```

The source and tracking databases are configured separately so they can point to different servers.

For the tracking database, credentials can be embedded directly in the URL (`mongodb://user:pass@host:port`) or supplied via separate `TRACKING_DB_USER` / `TRACKING_DB_PASSWORD` env vars.

### 5. Session

The pipeline handles session management automatically. On first run (or after expiry), it logs in headlessly using `EMAIL`/`PASSWORD` from `.env` and saves `state.json`. No manual browser interaction is required.

To login or re-login manually:

```bash
python login_helper.py
```

To check if the current session is valid:

```bash
python verify_login.py
```

Sessions typically expire after ~5 days. The pipeline detects expiry at startup and refreshes automatically.

## Usage

### Batch Pipeline

#### Basic runs

```bash
# Process all pending players (skips completed and previously failed)
python run_pipeline.py

# Cap the number of players processed in this run
python run_pipeline.py --limit 50

# Enable verbose / debug logging
python run_pipeline.py -v
python run_pipeline.py --limit 10 -v
```

#### Targeting specific players

```bash
# Process one or more specific players by api_player_id
python run_pipeline.py --player-ids 23730717
python run_pipeline.py --player-ids 23730717,37672209,1065

# Apply any MongoDB query filter against the source collection
python run_pipeline.py --filter '{"position": "Goalkeeper"}'
python run_pipeline.py --filter '{"league_id": 8}'
python run_pipeline.py --filter '{"position": "Goalkeeper"}' --limit 20
```

#### Style and prompt

```bash
# Use a different style preset
python run_pipeline.py --style "Watercolor"
python run_pipeline.py --style "Anime"

# Use a different edit mode
python run_pipeline.py --mode "General"

# Use a custom prompt file
python run_pipeline.py --prompt-file MY_PROMPT.txt

# Style + mode + prompt together
python run_pipeline.py --style "Watercolor" --mode "General" --prompt-file MY_PROMPT.txt
```

#### Output

```bash
# Override the output directory (also overrides OUTPUT_DIR in .env)
python run_pipeline.py --output-dir /data/portraits
python run_pipeline.py --limit 10 --output-dir ./test_output
```

#### Retrying failed players

```bash
# Retry all failed players (up to default max of 3 attempts each)
python run_pipeline.py --retry-failed

# Retry but skip any player that has already failed 5 or more times
python run_pipeline.py --retry-failed --max-retries 5

# Retry with verbose logging to see what went wrong
python run_pipeline.py --retry-failed -v
```

#### Common combinations

```bash
# Test run: 1 player, verbose, custom output dir
python run_pipeline.py --limit 1 -v --output-dir ./test_output

# Process all goalkeepers, anime style
python run_pipeline.py --filter '{"position": "Goalkeeper"}' --style "Anime" -v

# Retry failed with a higher retry ceiling
python run_pipeline.py --retry-failed --max-retries 5 -v

# Reprocess specific players with a different style
python run_pipeline.py --player-ids 23730717,37672209 --style "Watercolor" --prompt-file alt_prompt.txt
```

### CLI Arguments

| Argument | Description | Default |
|:--|:--|:--|
| `--limit N` | Max players to fetch and process (0 = all) | `0` |
| `--player-ids` | Comma-separated `api_player_id` values to process | — |
| `--filter` | JSON MongoDB query filter | — |
| `--style` | Style preset (e.g. Photo, Watercolor, Anime) | `Photo` |
| `--mode` | Edit mode | `General` |
| `--prompt-file` | Path to prompt text file | `MASTER_PROMPT.txt` |
| `--output-dir` | Output directory (overrides `OUTPUT_DIR` env) | `./output` |
| `--retry-failed` | Process only previously failed players | off |
| `--max-retries N` | Skip failed players that have already been attempted N or more times | `3` |
| `--verbose`, `-v` | Enable debug logging | off |

### Pipeline Summary Output

```
==================================================
PIPELINE SUMMARY
==================================================
  total_fetched:      100
  skipped_completed:   42
  skipped_failed:       3
  skipped_no_image:     1
  processed:           54
  succeeded:           52
  failed:               2
==================================================
```

| Field | Meaning |
|:--|:--|
| `total_fetched` | Players returned from the source DB (before any filtering) |
| `skipped_completed` | Already done — skipped |
| `skipped_failed` | Previously failed — skipped in this run, use `--retry-failed` |
| `skipped_no_image` | No source image URL — cannot be processed |
| `processed` | Players that were attempted this run |
| `succeeded` | Successfully generated and uploaded |
| `failed` | Failed this run (see tracking DB for error details) |

### Single Image (standalone)

```bash
# From a local file
python generate_image.py --file input.png --output result.png

# From a URL
python generate_image.py --url https://example.com/player.png --output result.png

# With custom style and mode
python generate_image.py --file input.png --style "Watercolor" --mode "General"
```

## Restart and Recovery Behaviour

The pipeline is designed to be safely stopped and restarted at any time:

| Player state when stopped | On restart |
|:--|:--|
| `completed` | Skipped automatically |
| `processing` (mid-generation when killed) | Reset to `failed` at startup, then retried via `--retry-failed` |
| `failed` (previous error) | Skipped in normal runs, only retried with `--retry-failed` |
| Not yet started | Picked up and processed normally |

To re-run failed players after fixing an issue:

```bash
python run_pipeline.py --retry-failed
```

Players that have been retried `--max-retries` times or more are excluded even from `--retry-failed` runs, to avoid endlessly hammering permanently broken entries.

## Tracking Database

Every player processed by the pipeline gets a document in `seedream_tracking.generation_tracking`:

```json
{
    "api_player_id": 23730717,
    "status": "completed",
    "source_image_url": "https://cdn.sportmonks.com/images/soccer/players/29/23730717.png",
    "style": "Photo",
    "mode": "General",
    "created_at": "2026-02-25T12:00:00.000Z",
    "updated_at": "2026-02-25T12:01:34.000Z",
    "retry_count": 0,
    "error_log": [],
    "output_path": "/app/output/23730717_generated.png",
    "generation_duration_seconds": 50.28,
    "spaces_url": "https://fantasyfootball.sgp1.cdn.digitaloceanspaces.com/image_pipeline/23730717.png"
}
```

**Status flow:**

```
pending ──> processing ──> completed
                      └──> failed
```

**Failed record example:**

```json
{
    "status": "failed",
    "retry_count": 2,
    "error_log": [
        "TimeoutError: Generation timed out - 120s",
        "Interrupted: found in processing state at pipeline startup"
    ]
}
```

Indexes are automatically created on `api_player_id` (unique) and `status`.

## DigitalOcean Spaces

Generated images are uploaded to:

```
{DO_BUCKET_NAME}/image_pipeline/{api_player_id}.png
```

Files are set to `public-read`. The CDN URL is stored in the tracking record under `spaces_url` and is immediately accessible after upload.

## Master Prompt

`MASTER_PROMPT.txt` controls the AI stylization. The current prompt generates **face-only stylized vector portraits** with cel shading, bold outlines, and a clean gradient background — no shoulders or jerseys.

Edit this file to change the visual style applied to all future generations.

## Troubleshooting

**Session expired**
Handled automatically — the pipeline logs in headlessly at startup if `state.json` is missing or expired. If auto-login fails, check `EMAIL`/`PASSWORD` in `.env` and look at `debug_login_failed.png`.

**High demand errors from Seedream**
Seedream occasionally returns "High demand right now" errors. Affected players are marked `failed`. Run `python run_pipeline.py --retry-failed` once demand eases.

**Generation timeout**
Generation can take up to 2 minutes per image. If the download button never appears, the player is marked failed and a `run_debug_generation_timeout.png` screenshot is saved.

**Players stuck in `processing`**
Automatically recovered — `reset_stuck_processing()` runs at every pipeline startup and resets any stuck records.

**Debug artifacts**
On failure, the following are saved to the project root (or `output/` for per-player errors):
- `run_debug_*.png` — screenshots at each pipeline stage
- `debug_page_failure.html` — full page HTML dump
- `{pid}_error.png` — screenshot at the moment of failure for that player

**Test DB connectivity**

```bash
source venv/bin/activate
python -c "from db.connection import get_source_db; c, db = get_source_db(); print(db.list_collection_names())"
python -c "from db.connection import get_tracking_db; c, db = get_tracking_db(); print(db.list_collection_names())"
```

## Tech Stack

- **Python 3.10+**
- **Playwright** — headless Chromium browser automation
- **PyMongo** — MongoDB driver
- **boto3** — DigitalOcean Spaces uploads (S3-compatible)
- **requests** — HTTP image downloads
- **python-dotenv** — environment configuration
