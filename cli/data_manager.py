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
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self):
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_url TEXT,
            user_name TEXT,
            post_content TEXT,
            posted_timestamp TIMESTAMP,
            post_url TEXT UNIQUE NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_emailed BOOLEAN DEFAULT 0,
            search_query_ref TEXT
        );
        '''
        self.conn.execute(create_table_sql)
        self.conn.commit()

    def insert_lead(self, lead: Dict[str, Any], search_query_ref: Optional[str] = None) -> bool:
        """
        Insert a lead dict. Returns True if inserted, False if duplicate.
        Expects lead to have keys: user_name, post_content, posted_date_text, profile_url, post_url
        """
        posted_timestamp = normalize_posted_date(lead.get("posted_date_text"))
        if not posted_timestamp:
            posted_timestamp = datetime.now(timezone.utc)
        try:
            self.conn.execute(
                '''INSERT INTO leads (profile_url, user_name, post_content, posted_timestamp, post_url, search_query_ref)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    lead.get("profile_url"),
                    lead.get("user_name"),
                    lead.get("post_content"),
                    posted_timestamp.isoformat(),
                    lead.get("post_url"),
                    search_query_ref
                )
            )
            self.conn.commit()
            logger.info(f"Inserted new lead: {lead.get('user_name')} | {lead.get('post_url')}")
            return True
        except sqlite3.IntegrityError:
            logger.info(f"Duplicate lead (post_url): {lead.get('post_url')}")
            return False
        except Exception as e:
            logger.error(f"Error inserting lead: {e}")
            return False

    def get_new_leads(self, only_unemailed: bool = True) -> List[Dict[str, Any]]:
        sql = 'SELECT * FROM leads'
        if only_unemailed:
            sql += ' WHERE is_emailed = 0'
        sql += ' ORDER BY posted_timestamp DESC'
        cur = self.conn.execute(sql)
        return [dict(row) for row in cur.fetchall()]

    def mark_leads_as_emailed(self, lead_ids: List[int]):
        if not lead_ids:
            return
        q_marks = ','.join(['?'] * len(lead_ids))
        sql = f'UPDATE leads SET is_emailed = 1 WHERE id IN ({q_marks})'
        self.conn.execute(sql, lead_ids)
        self.conn.commit()

    def close(self):
        self.conn.close()

# Example usage (for testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dm = DataManager()
    sample_lead = {
        "user_name": "John Doe",
        "profile_url": "https://www.linkedin.com/in/johndoe/",
        "post_content": "Looking for freelance backend work!",
        "posted_date_text": "2d",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/"
    }
    dm.insert_lead(sample_lead, search_query_ref="test_query")
    leads = dm.get_new_leads()
    print(leads)
    dm.close() 