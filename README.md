# Seedream Automation

Automate image generation and editing on [Seedream.pro](https://seedream.pro) using Playwright. This tool allows you to upload local images or provide image URLs, apply style presets, and generate new versions based on a master prompt.

## Features

- **Automated Login**: Uses `.env` credentials to manage sessions.
- **URL & File Support**: Generate images from local files or direct web links.
- **Configurable Styles**: Custom `--style` and `--mode` arguments.
- **Robust Extraction**: Multi-stage fallback (Direct Download, Base64 extraction, and Static URL capture) to ensure results are saved even in headless mode.
- **Detailed Debugging**: Automatic screenshots and HTML dumps on failure.

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd seedream-automation
```

### 2. Set up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configuration

### 1. Credentials

Create a `.env` file in the root directory with your Seedream credentials:

```env
EMAIL=your-email@example.com
PASSWORD=your-password
```

### 2. Master Prompt

Update `MASTER_PROMPT.txt` with your desired AI instructions. This prompt will be applied to every generation.

## Usage

### Basic Usage (Local File)

```bash
python generate_image.py --file path/to/your/image.png --output result.png
```

### Usage with Image URL

```bash
python generate_image.py --url https://example.com/player.png --output result.png
```

### Custom Style and Mode

```bash
python generate_image.py --file input.png --style "Watercolor" --mode "General" --output artistic_result.png
```

### Available Arguments

| Argument        | Description                                   | Default             |
| :-------------- | :-------------------------------------------- | :------------------ |
| `--file`        | Path to a local input image                   | None                |
| `--url`         | URL of an input image                         | None                |
| `--prompt-file` | Path to the text file containing instructions | `MASTER_PROMPT.txt` |
| `--output`      | Filename for the generated result             | `result.png`        |
| `--style`       | Style preset (e.g., Photo, Watercolor, Anime) | `Photo`             |
| `--mode`        | Edit mode (e.g., General)                     | `General`           |

## Troubleshooting

- **Session Issues**: If login fails, you can run `python login_helper.py` to manually log in and save the `state.json`.
- **Headless Mode**: The script runs in headless mode by default. To see the browser action, change `headless=True` to `headless=False` in `generate_image.py`.
- **Timeouts**: Image generation can take up to 2 minutes. The script will poll the UI until the "Download" button appears or an error is detected.
