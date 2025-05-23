import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class EmailSender:
    def __init__(self, smtp_server: str, smtp_port: int, smtp_user: str, smtp_password: str, sender_email: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_email = sender_email

    def send_email(self, to_email: str, subject: str, html_body: str, attachment_path: Optional[str] = None):
        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content("This email contains HTML content. Please view in an HTML-compatible client.")
        msg.add_alternative(html_body, subtype="html")

        # Attach Excel file if provided
        if attachment_path and os.path.isfile(attachment_path):
            with open(attachment_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(attachment_path)
            msg.add_attachment(file_data, maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=file_name)
            logger.info(f"Attached file: {file_name}")
        else:
            if attachment_path:
                logger.warning(f"Attachment file not found: {attachment_path}")

        # Send email
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent to {to_email} with subject '{subject}'")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

# Example usage
if __name__ == "__main__":
    import logging
    from datetime import datetime
    # Setup basic logging for the test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Import necessary classes
    # Assuming running from the project root, so cli.module_name
    from cli.config_loader import Config
    from cli.data_manager import DataManager
    from cli.email_builder import EmailBuilder
    from cli.excel_exporter import ExcelExporter

    logger.info("Starting EmailSender test script...")

    # 1. Load Configuration
    # Ensure config.json is in the project root, and .env has required email variables
    try:
        app_config = Config(config_path='config.json')
        logger.info("Configuration loaded successfully.")
    except FileNotFoundError:
        logger.error("config.json not found. Make sure it is in the project root.")
        exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        exit(1)

    # Extract email settings from config
    email_conf = app_config.email_settings
    smtp_server = email_conf.get('smtp_server', 'smtp.example.com') # Default if not in config
    smtp_port = email_conf.get('smtp_port', 587)
    smtp_user = email_conf.get('smtp_user', 'apikey') # Default or from config
    smtp_password = email_conf.get('smtp_password') # From .env via Config class
    sender_email = email_conf.get('sender_email')     # From .env via Config class
    to_email = email_conf.get('recipient_email')   # From .env via Config class

    if not all([smtp_password, sender_email, to_email]):
        logger.error("SMTP password, sender email, or recipient email is missing. Check .env and config.json.")
        logger.info("Required environment variables: SMTP_PASSWORD, SENDER_EMAIL, TO_EMAIL (as defined in config.json under email_settings *env_var keys)")
        exit(1)

    subject = f"{email_conf.get('subject_prefix', 'LeadScraper Report')} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # 2. Initialize DataManager and prepare dummy data for testing
    # For this test, we'll use a temporary test database.
    class DummyDBConfig:
        def __init__(self, path='test_email_sender_leads.db'):
            self.database_config = {'path': path}
    
    dm_config = DummyDBConfig()
    dm = DataManager(config=dm_config)

    # Insert some dummy leads for the report
    leads_for_report = [
        {
            "profile_url": "http://linkedin.com/in/testuser1",
            "user_name": "Test User One",
            "post_content": "This is the first test lead for email reporting.",
            "posted_timestamp": datetime.now(),
            "post_url": "http://linkedin.com/feed/post/test1",
            "scraped_at": datetime.now(),
            "search_query_ref": "test_email_query"
        },
        {
            "profile_url": "http://linkedin.com/in/testuser2",
            "user_name": "Test User Two",
            "post_content": "A second lead to make the report look fuller.",
            "posted_timestamp": datetime.now(),
            "post_url": "http://linkedin.com/feed/post/test2",
            "scraped_at": datetime.now(),
            "search_query_ref": "test_email_query"
        }
    ]
    inserted_ids = []
    for lead_data in leads_for_report:
        if dm.insert_lead(lead_data):
            # Fetch the inserted lead to get its ID (or assume lastrowid if simple)
            # For simplicity, we'll just fetch all new leads again
            pass 
    
    # Fetch these leads as if they are new
    actual_leads_from_db = dm.get_new_leads()
    if not actual_leads_from_db:
        logger.warning("No leads found in the dummy database for the report. Email will be sent with no leads.")

    # 3. Generate Excel report
    excel_exporter = ExcelExporter()
    attachment_path = app_config.output_excel_file # e.g., "linkedin_leads_report.xlsx"
    if actual_leads_from_db:
        excel_file_path = excel_exporter.generate_excel(actual_leads_from_db, attachment_path)
        if not excel_file_path:
            logger.error("Failed to generate Excel attachment. Sending email without it.")
            attachment_path = None # Ensure no attachment if generation failed
        else:
            logger.info(f"Excel report generated: {excel_file_path}")
            attachment_path = excel_file_path # Use the returned path
    else:
        logger.info("No leads to export to Excel. Skipping Excel generation.")
        attachment_path = None # No attachment if no leads

    # 4. Generate HTML body
    email_builder = EmailBuilder()
    html_body = email_builder.generate_html_table(actual_leads_from_db)
    logger.info("HTML email body generated.")

    # 5. Initialize EmailSender and send the email
    email_sender = EmailSender(smtp_server, smtp_port, smtp_user, smtp_password, sender_email)
    logger.info(f"Attempting to send email to {to_email} with subject '{subject}'")
    if attachment_path:
        logger.info(f"Attaching file: {attachment_path}")
    
    email_sender.send_email(to_email, subject, html_body, attachment_path)

    # 6. Mark leads as emailed (optional for this test, but good practice)
    if actual_leads_from_db:
        lead_ids_to_mark = [lead['id'] for lead in actual_leads_from_db]
        if lead_ids_to_mark:
            dm.mark_leads_as_emailed(lead_ids_to_mark)
            logger.info(f"Marked {len(lead_ids_to_mark)} leads as emailed in the dummy database.")

    # 7. Clean up
    dm.close()
    # Clean up the dummy database and excel file
    if os.path.exists(dm_config.database_config['path']):
        os.remove(dm_config.database_config['path'])
        logger.info(f"Cleaned up dummy database: {dm_config.database_config['path']}")
    if attachment_path and os.path.exists(attachment_path) and attachment_path == app_config.output_excel_file:
        # Only remove if it's the default named one, to avoid deleting unrelated files if path changed
        os.remove(attachment_path)
        logger.info(f"Cleaned up generated Excel report: {attachment_path}")
    
    logger.info("EmailSender test script finished.") 