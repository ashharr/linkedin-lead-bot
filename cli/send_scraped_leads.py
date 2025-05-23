import logging
import json
import os
from datetime import datetime

# Import core components
from cli.config_loader import Config # Updated
from cli.scraper import LinkedInScraper # Assuming this will be updated to use config
from cli.data_manager import DataManager
from cli.excel_exporter import ExcelExporter
from cli.email_builder import EmailBuilder
from cli.email_sender import EmailSender

# Load environment variables from .env file (done by ConfigLoader now)
# from dotenv import load_dotenv
# load_dotenv() # Handled by ConfigLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# This path is not in config.json, keeping it local or consider adding to config
LEADS_JSON_PATH = "linkedin_leads_scraped.json" 

def main():
    logger.info("Initializing configuration...")
    try:
        app_config = Config(config_path='config.json')
        logger.info("Configuration loaded successfully.")
    except FileNotFoundError:
        logger.error("CRITICAL: config.json not found. Make sure it is in the project root.")
        return
    except Exception as e:
        logger.error(f"CRITICAL: Error loading configuration: {e}")
        return

    # Retrieve settings from Config object
    email_conf = app_config.email_settings
    scraper_conf = app_config.scraper_settings # For LinkedInScraper

    smtp_server = email_conf.get('smtp_server')
    smtp_port = email_conf.get('smtp_port')
    smtp_user = email_conf.get('smtp_user')
    smtp_password = email_conf.get('smtp_password') # From .env via Config
    sender_email = email_conf.get('sender_email')     # From .env via Config
    to_email = email_conf.get('recipient_email')   # From .env via Config
    email_subject_prefix = email_conf.get('subject_prefix', 'LeadScraper Report')
    email_subject = f"{email_subject_prefix} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    excel_path = app_config.output_excel_file
    search_url = app_config.search_url

    if not all([smtp_server, isinstance(smtp_port, int), smtp_user, smtp_password, sender_email, to_email]):
        logger.error("CRITICAL: SMTP configuration is incomplete. Check config.json and .env file for SMTP_PASSWORD, SENDER_EMAIL, TO_EMAIL.")
        return
    if not search_url:
        logger.error("CRITICAL: Search URL is not configured in config.json.")
        return

    logger.info("Step 1: Scraping LinkedIn leads...")
    # Assuming LinkedInScraper will be refactored to take config
    # For now, we pass scraper_conf which contains headless, user_agent, selectors etc.
    # scraper = LinkedInScraper(config=app_config) # Ideal future state
    scraper = LinkedInScraper(headless=scraper_conf.get('headless', True)) # Temporary if scraper isn't updated yet
    
    leads = scraper.scrape(search_url) # LinkedInScraper.scrape might also need access to selectors via config
    
    if not leads:
        logger.warning("No leads scraped. Exiting pipeline.")
        return
    
    try:
        with open(LEADS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
        logger.info(f"Scraped leads saved to {os.path.abspath(LEADS_JSON_PATH)}")
    except IOError as e:
        logger.error(f"Error saving scraped leads to JSON file {LEADS_JSON_PATH}: {e}")
        # Decide if to continue without saving, or exit
        # For now, we'll continue to process the in-memory leads

    logger.info("Step 2: Inserting leads into the database (deduplication handled)...")
    dm = DataManager(config=app_config) # Pass the config object
    inserted_count = 0
    newly_inserted_lead_ids = []
    for lead_data in leads: # Assuming leads is a list of dicts from the scraper
        # The lead_data from scraper needs to be compatible with DataManager.insert_lead requirements
        # e.g., {'profile_url': ..., 'user_name': ..., ...}
        # We also need to ensure search_query_ref is added if needed by DataManager
        lead_data_for_db = lead_data.copy() # Avoid modifying original dict if reused
        lead_data_for_db['search_query_ref'] = search_url # Or a more specific query identifier
        
        if dm.insert_lead(lead_data_for_db):
            inserted_count += 1
            # To get IDs for marking as emailed later, it's better to fetch them from get_new_leads
    logger.info(f"Attempted to insert {len(leads)} leads. Successfully inserted {inserted_count} new leads into the database.")

    logger.info("Step 3: Fetching new (unemailed) leads from the database...")
    # get_new_leads() in DataManager already fetches unemailed leads
    new_leads_for_email = dm.get_new_leads()
    if not new_leads_for_email:
        logger.warning("No new unemailed leads to send. Exiting pipeline.")
        dm.close()
        return
    logger.info(f"Fetched {len(new_leads_for_email)} new leads for emailing.")

    logger.info("Step 4: Generating Excel file...")
    exporter = ExcelExporter()
    # excel_path is already defined from app_config.output_excel_file
    excel_file_generated_path = exporter.generate_excel(new_leads_for_email, excel_path)
    if not excel_file_generated_path:
        logger.error(f"Failed to generate Excel file at {excel_path}. Sending email without attachment.")
        # Continue without attachment

    logger.info("Step 5: Generating HTML table for email body...")
    builder = EmailBuilder()
    html_body = builder.generate_html_table(new_leads_for_email)

    logger.info("Step 6: Sending email with leads report and Excel attachment...")
    sender = EmailSender(smtp_server, smtp_port, smtp_user, smtp_password, sender_email)
    sender.send_email(to_email, email_subject, html_body, excel_file_generated_path if excel_file_generated_path else None)

    logger.info("Step 7: Marking leads as emailed in the database...")
    lead_ids_to_mark = [lead["id"] for lead in new_leads_for_email if "id" in lead]
    if lead_ids_to_mark:
        dm.mark_leads_as_emailed(lead_ids_to_mark)
        logger.info(f"Marked {len(lead_ids_to_mark)} leads as emailed.")
    
    dm.close()
    logger.info("Pipeline complete.")

if __name__ == "__main__":
    main() 