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
    from datetime import datetime
    from data_manager import DataManager
    from email_builder import EmailBuilder
    # Dummy/test config (replace with your real SMTP settings)
    smtp_server = "smtp.sendgrid.net"
    smtp_port = 587
    smtp_user = "apikey"
    smtp_password = os.environ.get("SMTP_PASSWORD")
    sender_email = os.environ.get("SENDER_EMAIL")  # Now loaded from .env
    to_email = os.environ.get("TO_EMAIL")  # Now loaded from .env
    subject = "LeadScraper Linkedin Report | " + datetime.now().strftime("%Y-%m-%d")
    # Use EmailBuilder to generate HTML body from leads
    dm = DataManager()
    leads = dm.get_new_leads()
    builder = EmailBuilder()
    html_body = builder.generate_html_table(leads)
    dm.close()
    attachment_path = "linkedin_leads_report.xlsx"
    sender = EmailSender(smtp_server, smtp_port, smtp_user, smtp_password, sender_email)
    sender.send_email(to_email, subject, html_body, attachment_path) 