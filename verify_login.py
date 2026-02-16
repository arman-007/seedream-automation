from playwright.sync_api import sync_playwright
import os

def verify_login():
    if not os.path.exists("state.json"):
        print("Error: state.json not found.")
        return

    with sync_playwright() as p:
        print("Launching browser (headless)...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state="state.json")
        page = context.new_page()
        
        print("Navigating to editor with saved state...")
        try:
            page.goto("https://seedream.pro/ai-photo-editor", timeout=30000)
        except Exception as e:
            print(f"Navigation error: {e}")

        print(f"Page loaded: {page.title()}")
        print(f"Current URL: {page.url}")
        
        page.screenshot(path="verify_screenshot.png")
        print("Screenshot saved to verify_screenshot.png")
        
        # Check if we are logged in. Usually 'Sign In' button disappears or 'Account' appears.
        # Let's check for absence of 'Sign In' button or presence of 'Log Out' / Profile icon.
        
        try:
            # Wait a bit for page load
            page.wait_for_timeout(5000)
            
            # Check for generic signs of being logged in
            # Common patterns: Avatar, "My Account", "Logout", absence of "Login"
            
            # Pattern 1: Check if "Sign In" or "Login" button is visible
            login_buttons = page.locator('a:has-text("Sign In"), button:has-text("Sign In"), a:has-text("Login"), button:has-text("Login")')
            if login_buttons.count() > 0 and login_buttons.first.is_visible():
                print("FAILURE: Login button is still visible. Login likely failed.")
            else:
                print("SUCCESS: Login button not found. Likely logged in.")
                
            # Pattern 2: Check for "Account" or "Profile" or "Logout"
            # This is more positive confirmation
            # Based on previous analysis, we didn't identifying profile selectors.
            # But usually there's some indicator.
            
            # Let's verify we are NOT redirected to /login
            if "/login" in page.url:
                 print("FAILURE: Redirected to login page.")
            else:
                 print(f"Current URL: {page.url} (Good)")

        except Exception as e:
            print(f"Error during verification: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_login()
