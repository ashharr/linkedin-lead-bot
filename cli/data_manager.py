import sqlite3
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "leads.db"

# --- Date Normalization Utility ---
def normalize_posted_date(date_str: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Convert LinkedIn relative date strings (e.g., '2d', '5h ago', 'Just now') to UTC datetime.
    Returns None if parsing fails.
    """
    if not date_str:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = date_str.strip().lower()
    if "just now" in date_str:
        return now
    match = re.match(r"(\d+)\s*(h|hr|hrs|hour|hours)\b", date_str)
    if match:
        hours = int(match.group(1))
        return now - timedelta(hours=hours)
    match = re.match(r"(\d+)\s*(d|day|days)\b", date_str)
    if match:
        days = int(match.group(1))
        return now - timedelta(days=days)
    match = re.match(r"(\d+)\s*(w|wk|wks|week|weeks)\b", date_str)
    if match:
        weeks = int(match.group(1))
        return now - timedelta(weeks=weeks)
    # Try to parse absolute dates (e.g., 'Mar 15', 'March 15, 2024')
    for fmt in ["%b %d", "%B %d", "%b %d, %Y", "%B %d, %Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If year is missing, assume this year (or previous year if in the future)
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
                if dt > now:
                    dt = dt.replace(year=now.year - 1)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    logger.warning(f"Could not normalize date string: '{date_str}'")
    return None

# --- DataManager Class ---
class DataManager:
    def __init__(self, config):
        self.db_path = config.database_config.get('path', 'leads.db')
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_table_if_not_exists()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row # Access columns by name
            self.cursor = self.conn.cursor()
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database {self.db_path}: {e}")
            raise # Re-raise the exception to halt if DB connection fails

    def create_table_if_not_exists(self):
        try:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_url TEXT,
                user_name TEXT,
                post_content TEXT,
                posted_timestamp TIMESTAMP,
                post_url TEXT UNIQUE NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_emailed BOOLEAN DEFAULT FALSE,
                search_query_ref TEXT
            )
            """)
            self.conn.commit()
            logger.info("'leads' table checked/created successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error creating 'leads' table: {e}")

    def insert_lead(self, lead_data: dict) -> bool:
        # Ensure all required fields are present, especially post_url
        if not lead_data.get('post_url'):
            logger.warning("Attempted to insert lead with no post_url. Skipping.")
            return False

        query = """
        INSERT INTO leads (profile_url, user_name, post_content, posted_timestamp, post_url, search_query_ref)
        VALUES (:profile_url, :user_name, :post_content, :posted_timestamp, :post_url, :search_query_ref)
        """
        try:
            self.cursor.execute(query, {
                'profile_url': lead_data.get('profile_url'),
                'user_name': lead_data.get('user_name'),
                'post_content': lead_data.get('post_content'),
                'posted_timestamp': lead_data.get('posted_timestamp'),
                'post_url': lead_data.get('post_url'),
                'search_query_ref': lead_data.get('search_query_ref')
            })
            self.conn.commit()
            logger.info(f"Inserted new lead: {lead_data.get('post_url')}")
            return True
        except sqlite3.IntegrityError: # Handles UNIQUE constraint violation for post_url
            logger.info(f"Lead with post_url {lead_data.get('post_url')} already exists. Skipping insertion.")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error inserting lead {lead_data.get('post_url')}: {e}")
            return False

    def get_new_leads(self) -> list[dict]:
        """Fetches leads that have not been marked as emailed."""
        try:
            self.cursor.execute("SELECT * FROM leads WHERE is_emailed = FALSE ORDER BY scraped_at DESC")
            leads = [dict(row) for row in self.cursor.fetchall()]
            logger.info(f"Fetched {len(leads)} new leads.")
            return leads
        except sqlite3.Error as e:
            logger.error(f"Error fetching new leads: {e}")
            return []

    def mark_leads_as_emailed(self, lead_ids: list[int]):
        if not lead_ids:
            return
        try:
            placeholders = ', '.join('?' * len(lead_ids))
            query = f"UPDATE leads SET is_emailed = TRUE WHERE id IN ({placeholders})"
            self.cursor.execute(query, lead_ids)
            self.conn.commit()
            logger.info(f"Marked {self.cursor.rowcount} leads as emailed.")
        except sqlite3.Error as e:
            logger.error(f"Error marking leads as emailed: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info(f"Database connection closed for {self.db_path}")

# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # This example assumes a config.json exists in the parent directory
    # and a .env file for any environment variables Config might use.
    import sys
    sys.path.append('..') # Add project root to sys.path to import Config
    from cli.config_loader import Config

    logging.basicConfig(level=logging.INFO)

    # Create a dummy config object for testing
    class DummyConfig:
        def __init__(self):
            self.database_config = {'path': 'test_leads.db'}

    # Test with DummyConfig
    test_config = DummyConfig()
    dm = DataManager(config=test_config)

    # Test inserting a lead
    sample_lead_1 = {
        "profile_url": "http://linkedin.com/in/johndoe",
        "user_name": "John Doe",
        "post_content": "This is a test post about something interesting.",
        "posted_timestamp": datetime.now(),
        "post_url": "http://linkedin.com/feed/update/urn:li:activity:12345", # Unique
        "search_query_ref": "test_query"
    }
    dm.insert_lead(sample_lead_1)

    # Test inserting a duplicate lead (should be skipped)
    dm.insert_lead(sample_lead_1)

    # Test inserting another lead
    sample_lead_2 = {
        "profile_url": "http://linkedin.com/in/janedoe",
        "user_name": "Jane Doe",
        "post_content": "Another fascinating post content here.",
        "posted_timestamp": datetime.now(),
        "post_url": "http://linkedin.com/feed/update/urn:li:activity:67890", # Unique
        "search_query_ref": "test_query_2"
    }
    dm.insert_lead(sample_lead_2)

    # Test fetching new leads
    new_leads = dm.get_new_leads()
    print(f"Fetched {len(new_leads)} new leads:")
    lead_ids_to_mark = []
    for lead in new_leads:
        print(f"  - {lead['user_name']}: {lead['post_url']}")
        lead_ids_to_mark.append(lead['id'])

    # Test marking leads as emailed
    if lead_ids_to_mark:
        dm.mark_leads_as_emailed(lead_ids_to_mark)
        print("Marked leads as emailed.")
        # Verify they are no longer fetched as new
        new_leads_after_marking = dm.get_new_leads()
        print(f"Fetched {len(new_leads_after_marking)} new leads after marking (should be 0 or fewer).")

    dm.close()

    # Clean up the test database file
    import os
    if os.path.exists("test_leads.db"):
        os.remove("test_leads.db")
        logger.info("Cleaned up test_leads.db") 