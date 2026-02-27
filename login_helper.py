from playwright.sync_api import sync_playwright
import time
import os
from dotenv import load_dotenv

load_dotenv()

def login_and_save_state(output_path="state.json"):
    """
    Log in to Seedream using EMAIL/PASSWORD from env and save session state.
    Returns True on success, False on failure.
    """
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    if not email or not password:
        print("ERROR: EMAIL and PASSWORD must be set in environment.")
        return False

    print(f"Logging in to Seedream as {email} (headless)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto("https://seedream.pro/login", timeout=30000)

            page.fill("#email", email)
            page.fill("#password", password)
            page.click('button[type="submit"]')

            # Wait until we leave the login page (any redirect = submit was accepted)
            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=15000)
            except Exception:
                pass  # fall through and check the sign-in button instead

            page.wait_for_timeout(2000)

            # Verify by checking if sign-in button is absent
            sign_in_btn = page.locator('a:has-text("Sign in"), button:has-text("Sign in")')
            if sign_in_btn.count() > 0:
                print("Login failed — sign-in button still visible after submit.")
                page.screenshot(path="debug_login_failed.png")
                return False

            context.storage_state(path=output_path)
            print(f"Login successful. Session saved to {os.path.abspath(output_path)}")
            return True

        except Exception as e:
            print(f"Login error: {e}")
            try:
                page.screenshot(path="debug_login_error.png")
            except Exception:
                pass
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    success = login_and_save_state()
    exit(0 if success else 1)
