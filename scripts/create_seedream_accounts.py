import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Tuple

from playwright.async_api import async_playwright

# Import helper functions from email_helper
from scripts.email_helper import get_temporary_email, wait_for_verification_email

# Constants
SEEDREAM_URL = "https://seedream.pro/ai-photo-editor"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

def load_existing_accounts(env_path: Path) -> int:
    """Return the highest ACCOUNT index currently present in the .env file.
    If none found, returns 0.
    """
    max_index = 0
    if not env_path.is_file():
        return max_index
    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"ACCOUNT_(\d+)_EMAIL", line)
            if m:
                idx = int(m.group(1))
                if idx > max_index:
                    max_index = idx
    return max_index

def append_account_to_env(env_path: Path, index: int, email: str, password: str) -> None:
    """Append a new ACCOUNT_<index> entry to the .env file preserving formatting.
    If the file does not end with a newline, one is added.
    """
    entry = f"ACCOUNT_{index}_EMAIL={email}\nACCOUNT_{index}_PASSWORD={password}\n"
    # Ensure the file ends with a newline before appending
    with env_path.open("a", encoding="utf-8") as f:
        f.write("\n" if not entry.startswith("\n") else "")
        f.write(entry)

async def register_account(page, email: str, password: str) -> bool:
    """Perform the registration flow on Seedream using the provided email/password.
    Returns True if registration form was submitted successfully.
    """
    await page.goto(SEEDREAM_URL)
    # The registration flow may be behind a modal or a separate page. We'll try common selectors.
    # Click on "Sign Up" or similar button if present.
    try:
        # Try to locate a sign‑up link/button
        signup_btn = await page.wait_for_selector("text=Sign Up", timeout=5000)
        await signup_btn.click()
    except Exception:
        # If no explicit sign‑up button, assume the page already shows registration fields.
        pass

    # Fill email
    try:
        await page.fill('input[name="email"]', email)
    except Exception:
        # Fallback selectors
        await page.fill('input[type="email"]', email)

    # Fill password – many sites use name="password" or similar.
    try:
        await page.fill('input[name="password"]', password)
    except Exception:
        await page.fill('input[type="password"]', password)

    # Submit the form – look for a button with type=submit or containing "Register".
    try:
        submit_btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
        await submit_btn.click()
    except Exception:
        # Alternative: button with text Register
        try:
            submit_btn = await page.wait_for_selector('text=Register', timeout=3000)
            await submit_btn.click()
        except Exception as e:
            print(f"[ERROR] Could not locate submit button: {e}")
            return False
    return True

async def process_one_account(context, index: int, password: str) -> Tuple[bool, str]:
    """Create a temporary email, register on Seedream, verify, and update .env.
    Returns (success, email).
    """
    page = await context.new_page()
    # Get temporary email address
    email = await get_temporary_email(page)
    if not email:
        print(f"[ERROR] Failed to obtain temporary email for account {index}")
        await page.close()
        return False, ""
    print(f"[INFO] Account {index}: temporary email obtained: {email}")

    # Register on Seedream
    success = await register_account(page, email, password)
    if not success:
        print(f"[ERROR] Registration failed for {email}")
        await page.close()
        return False, email

    # Wait for verification email – we keep the same page (temp mail) open in a new tab.
    # Open a new tab for the inbox.
    inbox_page = await context.new_page()
    await inbox_page.goto("https://tempmail100.com/")
    # The inbox page may already have the address loaded; we just poll for verification email.
    verification_link = await wait_for_verification_email(inbox_page)
    await inbox_page.close()
    if not verification_link:
        print(f"[ERROR] Verification email not received for {email}")
        await page.close()
        return False, email
    print(f"[INFO] Verification link found: {verification_link}")

    # Visit verification link to activate account
    try:
        await page.goto(verification_link)
        # Some services show a success message; we just wait a bit.
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"[ERROR] Visiting verification link failed: {e}")
        await page.close()
        return False, email

    await page.close()
    return True, email

async def main(count: int, password: str):
    max_existing = load_existing_accounts(ENV_PATH)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        for i in range(1, count + 1):
            idx = max_existing + i
            success, email = await process_one_account(context, idx, password)
            if success:
                append_account_to_env(ENV_PATH, idx, email, password)
                print(f"[SUCCESS] Account {idx} added to .env")
            else:
                print(f"[FAIL] Account {idx} could not be created.")
        await context.close()
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate temporary Seedream accounts and store them in .env")
    parser.add_argument("--count", type=int, default=5, help="Number of accounts to create (default: 5)")
    parser.add_argument("--password", type=str, default="seedream_Pass_2026!", help="Password to use for all accounts")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.count, args.password))
    except KeyboardInterrupt:
        sys.exit(0)
