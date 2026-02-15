from playwright.sync_api import sync_playwright
import time
import os

def login_and_save_state(output_path="state.json"):
    print("Launching browser...")
    with sync_playwright() as p:
        # Launch browser (headless=False so you can see it)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print(f"Navigating to https://seedream.pro/ai-photo-editor")
        page.goto("https://seedream.pro/ai-photo-editor")
        
        print("\n" + "="*50)
        print("ACTION REQUIRED:")
        print("1. In the browser window that opened, log in to Seedream.")
        print("2. Navigate back to the editor page if redirected.")
        print("3. When you are ready, press ENTER in this terminal.")
        print("="*50 + "\n")
        
        input("Press Enter to save session and close...")
        
        context.storage_state(path=output_path)
        print(f"Session saved to {os.path.abspath(output_path)}")
        browser.close()

if __name__ == "__main__":
    login_and_save_state()
