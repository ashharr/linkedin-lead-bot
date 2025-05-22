import json
import logging
import time
import os
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AUTH_FILE_PATH = "linkedin_auth_state.json" # Path to the saved auth state
DEBUG_OUTPUT_DIR = "debug_output" # Directory for debug files

# --- CSS Selectors (Revised based on new HTML analysis) ---
# IMPORTANT: These selectors need regular verification due to LinkedIn's dynamic nature.
SELECTORS = {
    # This selector directly targets the main container div for each post that has a data-urn.
    "post_item_list": 'div.feed-shared-update-v2[data-urn*="urn:li:activity:"]',

    # The following selectors are relative to the element matched by "post_item_list"
    "user_name": '.update-components-actor__title span[aria-hidden="true"]',
    "profile_url": 'a.update-components-actor__meta-link', # Gets href from link around user name/meta
    "posted_date_text": '.update-components-actor__sub-description span[aria-hidden="true"]',
    "post_content_full": 'div.feed-shared-inline-show-more-text div.update-components-text span[dir="ltr"]',
    "post_content_see_more_button": 'button.update-components-text-view__see-more-less-toggle',
    # post_url will be constructed from the 'data-urn' attribute of the post_item_list element itself.
}

SELECTORS_FALLBACK = {
    "user_name_alt": '.actor-name',
    "profile_url_alt_from_name": 'a.update-components-actor__image' # CSS for link around profile image
}

class LinkedInScraper:
    """
    A scraper for extracting LinkedIn content search results.
    """
    def __init__(self, headless=True, scroll_pauses=3, scroll_max_attempts=5):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.scroll_pauses = scroll_pauses
        self.scroll_max_attempts = scroll_max_attempts

    def _init_playwright(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        # Load authentication state if it exists
        if os.path.exists(AUTH_FILE_PATH):
            logger.info(f"Loading authentication state from {AUTH_FILE_PATH}")
            self.context = self.browser.new_context(
                storage_state=AUTH_FILE_PATH,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
            )
        else:
            logger.warning(f"Authentication state file not found at {AUTH_FILE_PATH}. Proceeding without saved state (likely will hit auth wall).")
            logger.warning("Run 'python save_auth_state.py' to create the auth state file after manual login.")
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
            )
        
        self.page = self.context.new_page()
        logger.info("Playwright initialized and browser context created.")

    def _close_playwright(self):
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()
        logger.info("Playwright closed.")

    def _navigate_to_url(self, url: str):
        logger.info(f"Navigating to URL: {url}")
        try:
            self.page.goto(url, wait_until='networkidle', timeout=60000)
            self.page.wait_for_timeout(5000) 
            logger.info(f"Successfully navigated to {url}")
        except PlaywrightTimeoutError:
            logger.error(f"Timeout navigating to {url}. Page might not have loaded or login redirect.", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}", exc_info=True)
            raise

    def _scroll_to_bottom(self):
        logger.info("Scrolling page to load dynamic content...")
        last_height = self.page.evaluate("document.body.scrollHeight")
        attempts = 0
        consecutive_no_change = 0
        while attempts < self.scroll_max_attempts:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            try:
                self.page.wait_for_load_state('networkidle', timeout=7000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout waiting for network idle after scroll.")
            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                consecutive_no_change +=1
                if consecutive_no_change >=2:
                    logger.info("Reached bottom or no new content loaded.")
                    break
            else:
                consecutive_no_change = 0
            last_height = new_height
            attempts += 1
            logger.info(f"Scroll attempt {attempts}/{self.scroll_max_attempts}. New height: {new_height}")
            time.sleep(1)

    def _extract_post_data(self, post_element, index: int) -> Optional[dict]:
        """Extracts data from a single post element (which is the post card itself)."""
        data = {}
        try:
            # post_element is already the div.feed-shared-update-v2[data-urn=...]
            urn_value = post_element.get_attribute('data-urn')
            if urn_value:
                data["post_url"] = f"https://www.linkedin.com/feed/update/{urn_value}/"
            else:
                data["post_url"] = "N/A"
                logger.warning(f"Post {index+1}: data-urn attribute not found. Cannot construct post_url.")

            # User Name
            user_name_el = post_element.query_selector(SELECTORS["user_name"])
            if user_name_el:
                data["user_name"] = user_name_el.inner_text().strip()
            else:
                user_name_el_alt = post_element.query_selector(SELECTORS_FALLBACK.get("user_name_alt"))
                data["user_name"] = user_name_el_alt.inner_text().strip() if user_name_el_alt else "N/A"
            if data["user_name"] == "N/A": logger.warning(f"Post {index+1} ({data['post_url']}): User name not found.")

            # Profile URL
            profile_url_el = post_element.query_selector(SELECTORS["profile_url"])
            if profile_url_el:
                data["profile_url"] = profile_url_el.get_attribute("href")
            else:
                profile_url_el_alt = post_element.query_selector(SELECTORS_FALLBACK.get("profile_url_alt_from_name"))
                data["profile_url"] = profile_url_el_alt.get_attribute("href") if profile_url_el_alt else "N/A"
            
            if data.get("profile_url") and isinstance(data["profile_url"], str) and not data["profile_url"].startswith("https://www.linkedin.com"):
                if data["profile_url"].startswith("/"):
                    data["profile_url"] = "https://www.linkedin.com" + data["profile_url"]
            if data.get("profile_url") == "N/A": logger.warning(f"Post {index+1} ({data['post_url']}): Profile URL not found.")

            # Posted Date Text
            posted_date_el = post_element.query_selector(SELECTORS["posted_date_text"])
            data["posted_date_text"] = posted_date_el.inner_text().strip() if posted_date_el else "N/A"
            if data["posted_date_text"] == "N/A": logger.warning(f"Post {index+1} ({data['post_url']}): Posted date not found.")

            # Post Content
            see_more_button = post_element.query_selector(SELECTORS["post_content_see_more_button"])
            if see_more_button and see_more_button.is_visible():
                try:
                    see_more_button.click(timeout=2000)
                    self.page.wait_for_timeout(500) 
                except Exception as e_click:
                    logger.warning(f"Post {index+1} ({data['post_url']}): Could not click 'See more' or not interactive: {e_click}")
            
            content_el = post_element.query_selector(SELECTORS["post_content_full"])
            data["post_content"] = content_el.inner_text().strip().replace("\n", " ") if content_el else "N/A"
            if data["post_content"] == "N/A": logger.warning(f"Post {index+1} ({data['post_url']}): Post content not found.")
            
            # Add URN itself to data for reference if needed, though post_url is primary
            data["urn"] = urn_value if urn_value else "N/A"

            logger.info(f"Post {index+1}: Successfully extracted data for {data.get('user_name', 'N/A')} ({data['post_url']})")
            return data

        except Exception as e:
            post_url_for_log = data.get("post_url", f"item_index_{index+1}")
            logger.error(f"Post {index+1} ({post_url_for_log}): Error extracting data: {e}", exc_info=True)
            return {"error": str(e), "user_name": data.get("user_name", "ErrorCase"), "post_url": post_url_for_log, "partial_data": True}

    def scrape(self, url: str) -> list:
        self._init_playwright()
        scraped_data = []
        try:
            self._navigate_to_url(url)
            
            try:
                self.page.wait_for_selector(SELECTORS["post_item_list"], timeout=30000)
                logger.info("Post list items (div[data-urn]) initially found or selector is valid.")
            except PlaywrightTimeoutError:
                logger.error(f"Timeout waiting for post list selector: {SELECTORS['post_item_list']}.")
                debug_timestamp = time.strftime("%Y%m%d-%H%M%S")
                
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True) # Ensure debug directory exists
                screenshot_path = os.path.join(DEBUG_OUTPUT_DIR, f"debug_screenshot_{debug_timestamp}.png")
                html_path = os.path.join(DEBUG_OUTPUT_DIR, f"debug_page_content_{debug_timestamp}.html")
                
                try:
                    self.page.screenshot(path=screenshot_path)
                    logger.info(f"Saved screenshot to {os.path.abspath(screenshot_path)}")
                    with open(html_path, "w", encoding="utf-8") as f_html:
                        f_html.write(self.page.content())
                    logger.info(f"Saved page HTML to {os.path.abspath(html_path)}")
                except Exception as debug_e:
                    logger.error(f"Error saving debug files: {debug_e}")
                current_url = self.page.url
                logger.info(f"Current page URL at failure: {current_url}")
                if "authwall" in current_url or "login" in current_url or "signup" in current_url:
                    logger.error("CRITICAL: Auth wall or login/signup page. Manual intervention likely needed.")
                elif (self.page.query_selector('text=/No results found/i') or
                      self.page.query_selector('text=/no matching results/i')):
                    logger.info("Page indicates no results were found.")
                return []

            self._scroll_to_bottom()

            post_elements = self.page.query_selector_all(SELECTORS["post_item_list"])
            logger.info(f"Found {len(post_elements)} post items using selector: {SELECTORS['post_item_list']}")

            if not post_elements:
                logger.warning("No post elements found after scrolling. Check selectors or page content. A screenshot/HTML might have been saved if initial wait_for_selector failed.")
                if not self.page.query_selector(SELECTORS["post_item_list"]):
                    debug_timestamp = time.strftime("%Y%m%d-%H%M%S")
                    
                    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True) # Ensure debug directory exists
                    screenshot_path = os.path.join(DEBUG_OUTPUT_DIR, f"debug_screenshot_postscroll_{debug_timestamp}.png")
                    html_path = os.path.join(DEBUG_OUTPUT_DIR, f"debug_page_content_postscroll_{debug_timestamp}.html")
                    try:
                        self.page.screenshot(path=screenshot_path)
                        logger.info(f"Saved screenshot (post-scroll) to {os.path.abspath(screenshot_path)}")
                        with open(html_path, "w", encoding="utf-8") as f_html:
                            f_html.write(self.page.content())
                        logger.info(f"Saved page HTML (post-scroll) to {os.path.abspath(html_path)}")
                    except Exception as debug_e:
                        logger.error(f"Error saving post-scroll debug files: {debug_e}")
                return []

            for i, el in enumerate(post_elements):
                logger.info(f"Processing post item {i+1}/{len(post_elements)}...")
                time.sleep(0.2) # Reduced delay, adjust as needed
                post_data = self._extract_post_data(el, i)
                if post_data and not post_data.get("partial_data"):
                    scraped_data.append(post_data)
                elif post_data: # Log partial data but don't necessarily add unless desired
                    logger.warning(f"Post {i+1} had partial data or error: {post_data.get('error', 'Unknown extraction issue')}")
            
            logger.info(f"Successfully processed {len(post_elements)} items, extracted {len(scraped_data)} complete posts.")

        except Exception as e:
            logger.error(f"An error occurred during the scraping process: {e}", exc_info=True)
        finally:
            self._close_playwright()
        
        return scraped_data

if __name__ == '__main__':
    sample_url = "https://www.linkedin.com/search/results/content/?datePosted=%22past-24h%22&keywords=%22freelance%22%20AND%20(%22Backend%20Developer%22%20OR%20%22Web%20Developer%22%20OR%20%22Full%20Stack%20Developer%22)%20NOT%20%22onsite%22%20.India&origin=FACETED_SEARCH&sid=vYc"
    scraper = LinkedInScraper(headless=True)
    logger.info(f"Starting scrape for URL: {sample_url}")
    extracted_leads = scraper.scrape(sample_url)

    if extracted_leads:
        logger.info(f"--- Scraped Data ({len(extracted_leads)} posts) ---")
        print(json.dumps(extracted_leads, indent=2))
        output_filename = "linkedin_leads_scraped.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(extracted_leads, f, indent=2, ensure_ascii=False)
        logger.info(f"Scraped data saved to {os.path.abspath(output_filename)}")
    else:
        logger.info("No data was scraped or all posts had issues.")
    logger.info("Scraper finished.") 