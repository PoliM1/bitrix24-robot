import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    app_host = os.getenv('APP_HOST', '0.0.0.0')
    app_port = int(os.getenv('APP_PORT', '8000'))
    app_base_url = os.getenv('APP_BASE_URL', 'http://localhost:8000').rstrip('/')
    bitrix_client_id = os.getenv('BITRIX_CLIENT_ID', '')
    bitrix_client_secret = os.getenv('BITRIX_CLIENT_SECRET', '')
    default_bitrix_domain = os.getenv('DEFAULT_BITRIX_DOMAIN', '').strip()
    default_creator_id = int(os.getenv('DEFAULT_CREATOR_ID', '1'))
    default_responsible_id = int(os.getenv('DEFAULT_RESPONSIBLE_ID', '1'))
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./bitrix_robot.db')
    scheduler_enabled = os.getenv('SCHEDULER_ENABLED', 'true').lower() == 'true'
    schedule_cron = os.getenv('SCHEDULE_CRON', '*/15 * * * *')

settings = Settings()
