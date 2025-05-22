import asyncio
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AUTH_FILE_PATH = "linkedin_auth_state.json"

def run_and_save_auth():
    with sync_playwright() as p:
        # IMPORTANT: Change headless to False to see the browser and log in
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        )
        page = context.new_page()

        logger.info("Navigating to LinkedIn login page...")
        page.goto("https://www.linkedin.com/login", wait_until='networkidle')

        logger.info("PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW.")
        logger.info("After you have successfully logged in and see your LinkedIn feed, press Enter in this console to continue...")
        
        # Simple way to pause: wait for user input. 
        # For a more robust pause, you can use page.pause() if you prefer the Playwright Inspector.
        input("Press Enter here after you have logged in on the browser...")

        logger.info(f"Current URL after login attempt: {page.url}")

        # Check if already on the feed page or a page indicating successful login
        login_confirmed = False
        if "feed" in page.url:
            logger.info("Already on the feed page. Login assumed successful.")
            login_confirmed = True
        else:
            # If not on feed, try a gentle navigation or wait for a known feed element
            logger.info("Not on feed page yet. Attempting to verify by waiting for feed URL or navigating...")
            try:
                # Wait for the URL to become the feed URL, in case of slow redirects
                page.wait_for_url("**/feed/**", timeout=15000) # Wait up to 15 seconds for feed URL
                logger.info(f"Navigated/redirected to feed URL: {page.url}")
                login_confirmed = True
            except PlaywrightTimeoutError:
                logger.warning("Timed out waiting for feed URL. Trying one more navigation to /feed/.")
                try:
                    page.goto("https://www.linkedin.com/feed/", wait_until='domcontentloaded', timeout=20000)
                    if "feed" in page.url:
                        logger.info(f"Successfully navigated to feed URL: {page.url}")
                        login_confirmed = True
                    else:
                        logger.error(f"Still not on feed. Current URL: {page.url}")
                except Exception as e_goto:
                    logger.error(f"Error during final goto to /feed/: {e_goto}")
        
        if login_confirmed:
            logger.info("Login confirmed. Saving authentication state...")
            context.storage_state(path=AUTH_FILE_PATH)
            logger.info(f"Authentication state saved to {AUTH_FILE_PATH}")
            logger.info("You can now close the browser window.")
        else:
            logger.error(f"Could not confirm login. Current URL: {page.url}. Auth state NOT saved.")
            logger.error("Please ensure you are fully logged in and on the feed page before pressing Enter.")

        logger.info("Closing browser in 10 seconds...")
        page.wait_for_timeout(10000) # Give some time to see messages before it closes
        browser.close()

if __name__ == "__main__":
    logger.info("This script will help you save your LinkedIn authentication state.")
    logger.info("A browser window will open. Please log in to LinkedIn as you normally would.")
    logger.info("Once logged in, come back to this terminal and press Enter.")
    run_and_save_auth() 