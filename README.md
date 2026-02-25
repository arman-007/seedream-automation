# Seedream Automation

Automate AI-powered stylized portrait generation for football players using [Seedream.pro](https://seedream.pro) and Playwright browser automation. Connects to a MongoDB database of players, generates stylized face-only vector portraits from their headshot photos, and tracks progress in a separate tracking database.

## How It Works

```
MongoDB (players) ──> Pipeline Runner ──> Seedream.pro (AI editor) ──> Styled Portraits
                           │                                               │
                           └──── Tracking DB (progress per player) <───────┘
```

1. **Source**: Player data lives in a local MongoDB database (`Fantasy_Global_Livescore.players`). Each player document has an `api_player_id` and an `image` URL pointing to their headshot photo.
2. **Pipeline**: The runner fetches unprocessed players, downloads each source image, uploads it to Seedream's AI photo editor via headless Chromium, applies a stylization prompt, and waits for generation to complete.
3. **Output**: Generated portraits are saved to the `output/` directory as `{api_player_id}_generated.png`.
4. **Tracking**: A separate MongoDB database (`seedream_tracking`) records the status of every player — pending, processing, completed, or failed — along with error logs, retry counts, durations, and output paths.

## Features

- **MongoDB-Driven Batch Processing**: Process hundreds of players automatically from a database source.
- **Progress Tracking**: Dedicated tracking database with per-player status, retry counts, error history, and output paths.
- **Idempotent Reruns**: Already-completed players are skipped automatically. Safe to restart at any time.
- **Retry Failed**: Built-in `--retry-failed` flag to re-process only players that previously failed.
- **Filterable**: Process specific players by ID, apply MongoDB query filters, or set a limit.
- **Robust Download**: Multi-stage fallback to extract results (direct download, modal button, base64 extraction, static URL scraping).
- **Per-Player Error Isolation**: A failure on one player does not stop the rest of the batch.
- **Session Management**: Login once, save session cookies, reuse across headless runs.
- **Debug Artifacts**: Automatic screenshots and HTML dumps on failure for troubleshooting.

## Project Structure

```
seedream_automation/
├── run_pipeline.py            # CLI entry point for batch processing
├── generate_image.py          # Core: browser automation for single image generation
├── login_helper.py            # Login to seedream.pro and save session
├── verify_login.py            # Verify saved session is still valid
├── MASTER_PROMPT.txt          # AI prompt applied to every generation
├── db/                        # Database package
│   ├── connection.py          #   MongoDB connection factory (retry + logging)
│   ├── source.py              #   Query players from source collection
│   ├── tracking.py            #   CRUD for tracking collection
│   └── schemas.py             #   Tracking document schema reference
├── pipeline/                  # Pipeline package
│   ├── runner.py              #   Batch orchestration loop
│   └── image_downloader.py    #   Download player image URLs to local files
├── output/                    # Generated images (gitignored)
├── .env                       # Credentials and DB config (gitignored)
├── .env.example               # Template for .env
├── state.json                 # Saved browser session (gitignored)
├── requirements.txt           # Python dependencies
└── MASTER_PROMPT.txt          # Stylization prompt
```

## Installation

### 1. Clone the repository

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

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

```env
# Seedream credentials
EMAIL=your-email@example.com
PASSWORD=your-password

# Source database (player data)
SOURCE_DB_URL=mongodb://localhost:27017
SOURCE_DB_NAME=Fantasy_Global_Livescore
SOURCE_COLLECTION=players

# Tracking database (pipeline progress)
TRACKING_DB_URL=mongodb://localhost:27017
TRACKING_DB_NAME=seedream_tracking
TRACKING_COLLECTION=generation_tracking

# Output directory
OUTPUT_DIR=./output
```

Source and tracking database URLs are kept separate so they can point to different servers if needed.

### 5. Login to Seedream

Run the login helper to authenticate and save session cookies:

```bash
python login_helper.py
```

This opens a browser window. Log in with your credentials, then press Enter in the terminal. The session is saved to `state.json` and reused for all headless runs.

Verify the session works:

```bash
python verify_login.py
```

## Usage

### Batch Pipeline (recommended)

Process players from the MongoDB source:

```bash
# Process all unprocessed players
python run_pipeline.py

# Process with a limit
python run_pipeline.py --limit 10

# Process specific players by api_player_id
python run_pipeline.py --player-ids 23730717,37672209,1065

# Apply a MongoDB query filter
python run_pipeline.py --filter '{"position": "Goalkeeper"}' --limit 20

# Retry previously failed players
python run_pipeline.py --retry-failed

# Verbose output for debugging
python run_pipeline.py --limit 5 -v
```

#### Pipeline CLI Arguments

| Argument | Description | Default |
|:--|:--|:--|
| `--limit N` | Max players to process (0 = all) | `0` |
| `--player-ids` | Comma-separated `api_player_id` values | None |
| `--filter` | JSON MongoDB query filter | None |
| `--style` | Style preset (Photo, Watercolor, Anime, etc.) | `Photo` |
| `--mode` | Edit mode | `General` |
| `--prompt-file` | Path to prompt text file | `MASTER_PROMPT.txt` |
| `--output-dir` | Output directory (overrides `OUTPUT_DIR` env) | `./output` |
| `--retry-failed` | Retry failed players instead of fetching new | Off |
| `--max-retries N` | Max retry attempts per player | `3` |
| `--verbose`, `-v` | Enable debug logging | Off |

#### Pipeline Output

```
==================================================
PIPELINE SUMMARY
==================================================
  total_fetched: 10
  skipped_completed: 3
  processed: 7
  succeeded: 6
  failed: 1
==================================================
```

### Single Image (standalone)

The original single-image CLI still works independently:

```bash
# From a local file
python generate_image.py --file input.png --output result.png

# From a URL
python generate_image.py --url https://example.com/player.png --output result.png

# With custom style
python generate_image.py --file input.png --style "Watercolor" --mode "General"
```

## Tracking Database

Every player processed by the pipeline gets a tracking record in MongoDB:

```json
{
    "api_player_id": 23730717,
    "status": "completed",
    "created_at": "2026-02-25T12:00:00.000Z",
    "updated_at": "2026-02-25T12:01:34.000Z",
    "retry_count": 0,
    "error_log": [],
    "output_path": "/path/to/output/23730717_generated.png",
    "style": "Photo",
    "mode": "General",
    "generation_duration_seconds": 50.28,
    "source_image_url": "https://cdn.sportmonks.com/images/soccer/players/29/23730717.png"
}
```

Statuses: `pending` > `processing` > `completed` or `failed`

Failed records include an error history:

```json
{
    "status": "failed",
    "retry_count": 2,
    "error_log": [
        "TimeoutError: Generation timed out - 120s",
        "FileNotFoundError: Output file not created"
    ]
}
```

## Master Prompt

The `MASTER_PROMPT.txt` file controls the AI stylization. The current prompt generates **face-only stylized vector portraits** with cel shading, bold outlines, and a clean gradient background. No shoulders or jerseys are added.

Edit this file to change the output style for all future generations.

## Troubleshooting

- **Session Expired**: If generations fail with "Login Required", re-run `python login_helper.py` to refresh the session.
- **High Demand Errors**: Seedream may return "High demand right now" errors. Use `--retry-failed` to re-process failed players later.
- **Timeouts**: Generation can take up to 2 minutes per image. The pipeline polls until a download button appears or an error is detected.
- **Debug Screenshots**: On failure, screenshots are saved as `run_debug_*.png` in the project root.
- **Verify DB Connection**: Run `python -c "from db import get_source_db; get_source_db()"` to test connectivity.

## Tech Stack

- **Python 3.12**
- **Playwright** (headless Chromium browser automation)
- **PyMongo** (MongoDB driver)
- **requests** (HTTP image downloads)
- **python-dotenv** (environment configuration)
