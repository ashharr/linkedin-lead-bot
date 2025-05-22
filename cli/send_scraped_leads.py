import logging
import json
import os
from datetime import datetime
from scraper import LinkedInScraper
from data_manager import DataManager
from excel_exporter import ExcelExporter
from email_builder import EmailBuilder
from email_sender import EmailSender
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION (replace with your real values or load from a config file) ---
SMTP_SERVER = "smtp.sendgrid.net"
SMTP_PORT = 587
SMTP_USER = "apikey"
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")  # Now loaded from .env
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")  # Now loaded from .env
TO_EMAIL = os.environ.get("TO_EMAIL")  # Now loaded from .env
EMAIL_SUBJECT = "LeadScraper Linkedin Report | " + datetime.now().strftime("%Y-%m-%d")
EXCEL_PATH = "linkedin_leads_report.xlsx"
LEADS_JSON_PATH = "linkedin_leads_scraped.json"

SEARCH_URL = "https://www.linkedin.com/search/results/content/?datePosted=%22past-24h%22&keywords=%22freelance%22%20AND%20(%22Backend%20Developer%22%20OR%20%22Web%20Developer%22%20OR%20%22Full%20Stack%20Developer%22)%20NOT%20%22onsite%22%20.India&origin=FACETED_SEARCH&sid=vYc"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Step 1: Scraping LinkedIn leads...")
    scraper = LinkedInScraper(headless=True)
    leads = scraper.scrape(SEARCH_URL)
    if not leads:
        logger.warning("No leads scraped. Exiting pipeline.")
        return
    with open(LEADS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    logger.info(f"Scraped leads saved to {os.path.abspath(LEADS_JSON_PATH)}")

    logger.info("Step 2: Inserting leads into the database (deduplication handled)...")
    dm = DataManager()
    inserted_count = 0
    for lead in leads:
        if dm.insert_lead(lead):
            inserted_count += 1
    logger.info(f"Inserted {inserted_count} new leads into the database.")

    logger.info("Step 3: Fetching new (unemailed) leads from the database...")
    new_leads = dm.get_new_leads(only_unemailed=True)
    if not new_leads:
        logger.warning("No new unemailed leads to send. Exiting pipeline.")
        dm.close()
        return
    logger.info(f"Fetched {len(new_leads)} new leads for emailing.")

    logger.info("Step 4: Generating Excel file...")
    exporter = ExcelExporter()
    excel_file_path = exporter.generate_excel(new_leads, EXCEL_PATH)

    logger.info("Step 5: Generating HTML table for email body...")
    builder = EmailBuilder()
    html_body = builder.generate_html_table(new_leads)

    logger.info("Step 6: Sending email with leads report and Excel attachment...")
    sender = EmailSender(SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SENDER_EMAIL)
    sender.send_email(TO_EMAIL, EMAIL_SUBJECT, html_body, excel_file_path)

    logger.info("Step 7: Marking leads as emailed in the database...")
    lead_ids = [lead["id"] for lead in new_leads if "id" in lead]
    if lead_ids:
        dm.mark_leads_as_emailed(lead_ids)
        logger.info(f"Marked {len(lead_ids)} leads as emailed.")
    dm.close()
    logger.info("Pipeline complete.")

if __name__ == "__main__":
    main() 