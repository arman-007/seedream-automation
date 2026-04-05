import argparse
import os
import time
import requests
import base64
import re
from playwright.sync_api import sync_playwright


class DailyLimitReachedException(Exception):
    """Raised when a Seedream account has hit its daily generation limit."""
    pass

def download_image(url, save_path):
    print(f"Downloading image from {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Image saved to {save_path}")
            return True
        else:
            print(f"Failed to download image. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False

def read_master_prompt(file_path="MASTER_PROMPT.txt"):
    try:
        with open(file_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: {file_path} not found.")
        return ""

def check_session(state_path="state.json"):
    """
    Check if the Seedream session stored in state_path is still valid.
    Returns True if logged in, False if expired or state file missing.
    """
    if not os.path.exists(state_path):
        print(f"Session check: {state_path} not found.")
        return False
    print("Checking Seedream session validity...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=state_path)
            page = context.new_page()
            page.goto("https://seedream.pro/ai-photo-editor", timeout=30000)
            page.wait_for_timeout(3000)
            sign_in_btn = page.locator('a:has-text("Sign in"), button:has-text("Sign in")')
            logged_in = sign_in_btn.count() == 0
            print(f"Session check result: {'valid' if logged_in else 'EXPIRED'}")
            return logged_in
        except Exception as e:
            print(f"Session check failed with error: {e}")
            return False
        finally:
            browser.close()

def run_generation_on_page(page, image_path, prompt, output_path, style="Photo"):
    """
    Run image generation on an already-open Playwright page.
    Raises exceptions on failure — caller is responsible for error handling
    and browser lifecycle management.
    """
    print("Navigating to Seedream Editor...")
    page.goto("https://seedream.pro/ai-photo-editor", timeout=60000)

    # 1. Upload Image
    print(f"Uploading image: {image_path}")
    file_input = page.locator('input[type="file"]')
    file_input.wait_for(state="attached")
    file_input.set_input_files(image_path)

    # Wait for upload to react (preview appears or prompt becomes interactive)
    page.wait_for_timeout(5000)
    page.screenshot(path="run_debug_1_after_upload.png")
    print(f"After upload URL: {page.url}")

    # 2. Select Style Preset
    print(f"Selecting Style Preset: {style}")
    # Map common styles to website values
    style_map = {
        "Photo": "photo",
        "Anime": "anime",
        "Fantasy": "fantasy",
        "Portrait": "portrait",
        "Landscape": "landscape",
        "Sci-Fi": "scifi",
        "Cinematic": "cinematic",
        "Oil Painting": "oil",
        "Pixel Art": "pixel",
        "Watercolor": "watercolor",
        "Ghibli": "ghibli",
        "Vintage": "vintage",
        "Raw Film": "raw-film",
        "Ink Splash": "ink-splash"
    }
    style_value = style_map.get(style, style.lower())
    
    try:
        # The style selector is a <select> element inside a label with text "Styles"
        style_selector = 'label:has-text("Styles") select'
        page.wait_for_selector(style_selector, timeout=10000)
        page.select_option(style_selector, value=style_value)
    except Exception as e:
        print(f"Warning: Failed to select {style} preset (value={style_value}): {e}")
        page.screenshot(path=f"debug_failed_{style}_selection.png")

    # 3. Enter Prompt
    print(f"Entering prompt (length: {len(prompt)} chars)...")
    # Using more specific selector for the textarea
    textarea = page.locator('textarea[placeholder*="Describe"]')
    textarea.wait_for(state="visible")
    textarea.fill(prompt)

    page.screenshot(path="run_debug_2_before_apply.png")

    # 4. Click Apply Edits / Generate
    # The button text changes to "Edit image" after upload, or "Generate" initially.
    # We target the primary brand button.
    print("Clicking 'Edit image'...")
    apply_button = page.locator('button.bg-brand-green, button:has-text("Edit image"), button:has-text("Generate")').first
    if apply_button.count() > 0:
        apply_button.click(force=True)
    else:
        print("CRITICAL: Apply/Edit button NOT FOUND!")
        page.screenshot(path="debug_no_apply_button.png")

    # Check state immediately after click
    page.wait_for_timeout(5000)
    print(f"After apply URL: {page.url}")
    page.screenshot(path="run_debug_3_after_apply.png")

    # 6. Wait for Generation & Download
    print("Waiting for generation to complete...")

    error_locator = page.locator('div:has-text("Edit Failed"), div:has-text("High demand right now"), div:has-text("Daily limit reached"), div:has-text("today\'s limit"), div:has-text("used all image edits")')
    download_locator = page.locator('button:has-text("Download")')

    start_time = time.time()
    generation_success = False

    while time.time() - start_time < 120:  # 2 minute total timeout
        if error_locator.first.is_visible():
            print("DETECTED: Edit Failed modal!")
            error_text = error_locator.first.inner_text()
            error_text_clean = error_text.replace('\n', ' ')
            print(f"Error details: {error_text_clean}")
            page.screenshot(path="run_debug_edit_failed.png")

            close_button = page.locator('button:has-text("✕"), .modal-close, [aria-label="Close"]').first
            if close_button.count() > 0:
                print("Attempting to close error modal...")
                close_button.click()

            if "today's limit" in error_text.lower() or "daily limit" in error_text.lower():
                raise DailyLimitReachedException(f"Generation failed on website: {error_text}")
            raise Exception(f"Generation failed on website: {error_text}")

        if download_locator.first.is_visible():
            print("Generation complete! (Download button visible)")
            generation_success = True
            break

        page.wait_for_timeout(2000)

    if not generation_success:
        page.screenshot(path="run_debug_generation_timeout.png")
        with open("debug_generation_timeout.html", "w") as f:
            f.write(page.content())
        raise TimeoutError("Generation timed out - neither download button nor error modal appeared in 120s")

    download_button = download_locator.first

    # Debug: List all images
    images = page.eval_on_selector_all("img", "elements => elements.map(e => e.src)")
    print("Found images:", images)

    print(f"Download button HTML: {download_button.evaluate('el => el.outerHTML')}")

    try:
        print("Attempting to click download button...")
        with page.expect_download(timeout=30000) as download_info:
            download_button.click(force=True)

        download = download_info.value
        download.save_as(output_path)
        print(f"Saved generated image to {os.path.abspath(output_path)}")
    except Exception as e:
        print(f"Direct download failed or timed out: {e}")
        print("Checking for alternative download buttons or modals...")
        page.screenshot(path="run_debug_after_click.png")

        modal_download = page.locator('button:has-text("Download Image"), a:has-text("Download Image"), button:has-text("Download High Res")').first
        if modal_download.count() > 0:
            print(f"Found modal option: {modal_download.evaluate('el => el.innerText')}")
            try:
                with page.expect_download(timeout=10000) as download_info:
                    modal_download.click(force=True)
                download = download_info.value
                download.save_as(output_path)
                print(f"Saved generated image (from modal) to {os.path.abspath(output_path)}")
                return  # Success
            except Exception as me:
                print(f"Modal download also failed: {me}")

        # FALLBACK: Try to find the image in the page as a base64 string or static URL
        print("Attempting fallback: searching for result image in the page...")
        image_elements = page.query_selector_all("img")
        found_fallback = False
        
        # We'll collect candidates and pick the best one
        candidates = []

        for img in image_elements:
            src = img.get_attribute("src")
            if not src:
                continue

            # Case 1: Static result URL (e.g. static.seedream.pro/.../outputs/output_...)
            # Relaxed string check to catch /outputs/ or /output/
            if "seedream.pro" in src and "/output" in src:
                print(f"Found potential result image URL: {src}")
                candidates.append({"type": "url", "src": src})

            # Case 2: Base64 (often used for previews or direct inline data)
            elif src.startswith("data:image/"):
                size_kb = len(src) / 1024
                if size_kb > 10:  # Any image over 10KB is a candidate
                    print(f"Found potential base64 image (size: {size_kb:.1f} KB)")
                    candidates.append({"type": "base64", "src": src, "size": size_kb})

        # Process candidates: prioritize static URLs with "output" in them
        for candidate in candidates:
            if candidate["type"] == "url":
                if download_image(candidate["src"], output_path):
                    print(f"Saved generated image from URL to {os.path.abspath(output_path)}")
                    found_fallback = True
                    break
            elif candidate["type"] == "base64":
                # Only use base64 if it's the only option or reasonably large
                if candidate["size"] > 30 or len(candidates) == 1:
                    try:
                        header, data = candidate["src"].split(",", 1)
                        with open(output_path, "wb") as f:
                            f.write(base64.b64decode(data))
                        print(f"Saved generated image from base64 string ({candidate['size']:.1f} KB) to {os.path.abspath(output_path)}")
                        found_fallback = True
                        break
                    except Exception as b64e:
                        print(f"Failed to decode base64 image: {b64e}")

        if not found_fallback:
            with open("debug_page_no_image_found.html", "w") as f:
                f.write(page.content())
            page.screenshot(path="debug_page_no_image_found.png")
            raise Exception("Generation succeeded but failed to capture the result image via download or fallback.")


def generate_image(image_path, prompt, output_path="result.png", style="Photo"):
    """
    Standalone wrapper: launches its own browser, runs generation, closes browser.
    Used when calling generate_image.py directly (CLI or single-image use).
    """
    print("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        if os.path.exists("state.json"):
            print("Loading session state...")
            context = browser.new_context(storage_state="state.json")
        else:
            print("Warning: state.json not found. Logging in might be required.")
            context = browser.new_context()

        page = context.new_page()
        page.on("console", lambda msg: print(f"Browser Console: {msg.text}"))

        try:
            run_generation_on_page(page, image_path, prompt, output_path, style)
        except Exception as e:
            print(f"Error during generation: {e}")
            page.screenshot(path="run_debug_generation_error.png")
            print("Saved run_debug_generation_error.png")
            try:
                images = page.eval_on_selector_all("img", "elements => elements.map(e => e.src)")
                print("Found images (on failure):", images)
                with open("debug_page_failure.html", "w") as f:
                    f.write(page.content())
                print("Saved debug_page_failure.html")
            except Exception as dump_e:
                print(f"Failed to dump debug info: {dump_e}")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seedream AI Image Generator Automation")
    parser.add_argument("--url", help="URL of the input image")
    parser.add_argument("--file", help="Path to local input image")
    parser.add_argument("--prompt-file", default="MASTER_PROMPT.txt", help="Path to prompt file")
    parser.add_argument("--output", default="result.png", help="Output filename")
    parser.add_argument("--style", default="Photo", help="Style preset to apply")
    parser.add_argument("--style", default="Photo", help="Style preset to apply")

    args = parser.parse_args()

    prompt_text = read_master_prompt(args.prompt_file)
    if not prompt_text:
        print("Error: Empty prompt or file not found. Please check MASTER_PROMPT.txt")
        exit(1)

    if args.file:
        if os.path.exists(args.file):
            generate_image(args.file, prompt_text, args.output, args.style)
        else:
            print(f"Error: File {args.file} not found.")
    elif args.url:
        temp_image = "temp_input.png"
        if download_image(args.url, temp_image):
            generate_image(temp_image, prompt_text, args.output, args.style)
            if os.path.exists(temp_image):
                os.remove(temp_image)
    else:
        print("Error: Must provide either --url or --file")
