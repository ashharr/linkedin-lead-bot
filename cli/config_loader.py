import json
import os
from dotenv import load_dotenv

load_dotenv() # Load .env file for environment variables

class Config:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self._config = json.load(f)

    @property
    def search_url(self) -> str:
        return self._config['search_url']

    @property
    def output_excel_file(self) -> str:
        return self._config['output_excel_file']

    @property
    def database_config(self) -> dict:
        return self._config['database']

    @property
    def email_settings(self) -> dict:
        settings = self._config['email_settings'].copy()
        # Override with environment variables if specified
        if 'smtp_password_env_var' in settings:
            settings['smtp_password'] = os.environ.get(settings['smtp_password_env_var'])
        if 'sender_email_env_var' in settings:
            settings['sender_email'] = os.environ.get(settings['sender_email_env_var'])
        if 'recipient_email_env_var' in settings:
            settings['recipient_email'] = os.environ.get(settings['recipient_email_env_var'])
        return settings

    @property
    def scraper_settings(self) -> dict:
        return self._config['scraper_settings']

    @property
    def selectors(self) -> dict:
        return self._config['selectors']

    @property
    def logging_config(self) -> dict:
        return self._config['logging']

# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # Assuming config.json is in the parent directory relative to cli/ when running this script directly
    # For actual application use, the path might be just 'config.json' if run from project root.
    config = Config(config_path='../config.json') 
    print("Search URL:", config.search_url)
    print("DB Path:", config.database_config.get('path'))
    email_conf = config.email_settings
    print("SMTP Server:", email_conf.get('smtp_server'))
    print("Sender Email (from env var SENDER_EMAIL):", email_conf.get('sender_email')) # Note: SENDER_EMAIL from .env is expected
    print("Recipient Email (from env var TO_EMAIL):", email_conf.get('recipient_email')) # Note: TO_EMAIL from .env is expected
    print("SMTP Password (from env var SMTP_PASSWORD):", email_conf.get('smtp_password')) # Note: SMTP_PASSWORD from .env is expected 