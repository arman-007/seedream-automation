import asyncio
from playwright.async_api import async_playwright
import time
import re

TEMPMAIL_URL = "https://tempmail100.com/"

async def get_temporary_email(page):
    """Navigate to tempmail100.com and retrieve the generated email address."""
    await page.goto(TEMPMAIL_URL)
    # The email address is usually inside an input field with id or class. Adjust selector if needed.
    # Here we try common selectors.
    email_selector_candidates = ["#email", "input#email", "input.email", "#mail", "input#mail"]
    email = None
    for selector in email_selector_candidates:
        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            email = await element.input_value()
            if email:
                break
        except Exception:
            continue
    if not email:
        # Fallback: try to read from the page text that looks like an email.
        content = await page.content()
        match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", content)
        email = match.group(0) if match else None
    return email

async def wait_for_verification_email(page, timeout=120):
    """Poll the inbox for a verification email and return the verification link.
    Returns None if not found within timeout seconds.
    """
    start = time.time()
    while time.time() - start < timeout:
        # Refresh the inbox page.
        await page.reload()
        # Look for email rows that contain "Seedream" or "Verify" in subject.
        rows = await page.query_selector_all("tr")
        for row in rows:
            text = await row.inner_text()
            if "seedream" in text.lower() and "verify" in text.lower():
                # Click the row to open email content.
                await row.click()
                # Wait for email body to load.
                await page.wait_for_selector("body")
                body_html = await page.content()
                # Extract first URL that looks like verification link.
                match = re.search(r"https?://[^\s\"']+", body_html)
                if match:
                    return match.group(0)
        await asyncio.sleep(5)
    return None

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        email = await get_temporary_email(page)
        print(f"Temporary email: {email}")
        # Close tempmail page; we'll keep the context for later verification.
        await page.close()
        # Return email and the context for later use.
        return email, context

if __name__ == "__main__":
    asyncio.run(main())
