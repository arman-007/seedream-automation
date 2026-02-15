import argparse
import os
import time
import requests
from playwright.sync_api import sync_playwright

def download_image(url, save_path):
    print(f"Downloading image from {url}...")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Image saved to {save_path}")
        return True
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
        return False

def generate_image(image_path, prompt, output_path="generated_image.png"):
    with sync_playwright() as p:
        # Launch browser (headless=False for debugging visibility, can serve headless later)
        browser = p.chromium.launch(headless=False) 
        if os.path.exists("state.json"):
            print("Using saved session state.")
            context = browser.new_context(storage_state="state.json")
        else:
            print("No session state found. Running without login (might fail).")
            context = browser.new_context()
        page = context.new_page()

        try:
            print("Navigating to Seedream...")
            page.goto("https://seedream.pro/ai-photo-editor")

            # Scroll to generator section to ensure elements are interactive
            print("Scrolling to generator...")
            # Try to find the generator anchor or just scroll down
            try:
                page.click('a[href="#generator"]', timeout=5000)
            except:
                print("Could not click anchor, scrolling manually...")
                page.mouse.wheel(0, 1000)
            
            # Locate file input
            print("Uploading image...")
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(image_path)
            
            # Wait for upload processing if necessary (look for image preview or similar change)
            # For now, just a small sleep or check for the prompt area to be active/visible
            page.wait_for_timeout(2000)

            # Enter prompt
            print(f"Entering prompt: {prompt[:50]}...")
            # The analyze step found a textarea. We'll target it specifically.
            textarea = page.locator('textarea')
            textarea.fill(prompt)

            # Click Generate / Apply Edits
            print("Clicking 'Apply Edits'...")
            apply_button = page.locator('button:has-text("Apply Edits")')
            apply_button.click()

            # Wait for generation to complete
            # We need to look for the result image. 
            # Usually these sites show a loading spinner then replace it with the image.
            print("Waiting for generation...")
            # Wait for some time or a specific element change. 
            # Since we don't know the exact success selector yet, we'll wait for a new image source 
            # or a specific 'Download' button that appears after generation.
            
            # Heuristic: Wait for the "Download" button to appear or become enabled
            try:
                download_button = page.locator('button:has-text("Download")', has_text="Download").first
                download_button.wait_for(state="visible", timeout=60000) # 60s timeout for generation
                print("Generation complete!")
                
                # Click download or extract image src
                # If clicking download triggers a download event:
                with page.expect_download() as download_info:
                    download_button.click()
                
                download = download_info.value
                download.save_as(output_path)
                print(f"Saved generated image to {output_path}")

            except Exception as e:
                print(f"Error waiting for result: {e}")
                # Fallback: Take a screenshot if download fails
                page.screenshot(path="debug_error.png")
                print("Saved debug_error.png")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="debug_exception.png")
        finally:
            browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seedream AI Image Generator Automation")
    parser.add_argument("--url", required=True, help="URL of the input image")
    parser.add_argument("--prompt", required=True, help="Prompt for image generation")
    parser.add_argument("--output", default="result.png", help="Output filename")

    args = parser.parse_args()

    temp_image = "temp_input.jpg"
    if download_image(args.url, temp_image):
        generate_image(temp_image, args.prompt, args.output)
        # Cleanup
        if os.path.exists(temp_image):
            os.remove(temp_image)
