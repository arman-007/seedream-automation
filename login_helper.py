from playwright.sync_api import sync_playwright
import time
import os
from dotenv import load_dotenv

load_dotenv()


def _perform_login(context, output_path, email, password):
    """
    Core login logic: fills credentials on an existing browser context,
    verifies success, and saves session state to output_path.
    Returns True on success, False on failure.
    """
    page = context.new_page()
    try:
        page.goto("https://seedream.pro/login", timeout=30000)

        page.fill("#email", email)
        page.fill("#password", password)
        page.click('button[type="submit"]')

        # Wait until we leave the login page
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
        page.close()


def login_with_browser(browser, output_path="state.json", email=None, password=None):
    """
    Log in using an already-running Playwright browser instance.
    Use this when calling from inside a sync_playwright() block (e.g. during
    account rotation in runner.py) to avoid nested playwright instances.

    Returns True on success, False on failure.
    """
    email = email or os.getenv("EMAIL")
    password = password or os.getenv("PASSWORD")

    if not email or not password:
        print("ERROR: No credentials provided. Pass email/password args or set EMAIL/PASSWORD in .env.")
        return False

    print(f"Logging in to Seedream as {email} (headless)...")
    context = browser.new_context()
    try:
        return _perform_login(context, output_path, email, password)
    finally:
        context.close()


def login_and_save_state(output_path="state.json", email=None, password=None):
    """
    Log in to Seedream and save the session state to output_path.
    Launches its own Playwright instance — use login_with_browser() instead
    when already inside a sync_playwright() block.

    Credentials are resolved in this order:
      1. Explicit email / password arguments (used for account rotation)
      2. EMAIL / PASSWORD environment variables (legacy fallback)

    Returns True on success, False on failure.
    """
    email = email or os.getenv("EMAIL")
    password = password or os.getenv("PASSWORD")

    if not email or not password:
        print("ERROR: No credentials provided. Pass email/password args or set EMAIL/PASSWORD in .env.")
        return False

    print(f"Logging in to Seedream as {email} (headless)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            return _perform_login(context, output_path, email, password)
        finally:
            browser.close()


if __name__ == "__main__":
    success = login_and_save_state()
    exit(0 if success else 1)
