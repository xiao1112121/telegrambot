import os
from typing import List

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8312199538:AAF27sDBhlZGSghMkOh9YGYYzEKqr58Yv8A')

# Google Sheets Configuration
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', 'your_google_spreadsheet_id_here')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')

# Admin User IDs
ADMIN_USER_IDS_STR = os.getenv('ADMIN_USER_IDS', '6513278007,7363247246,7988655018')
ADMIN_USER_IDS = [int(user_id.strip()) for user_id in ADMIN_USER_IDS_STR.split(',') if user_id.strip()]

# Debug: Print admin IDs for troubleshooting
print(f"🔧 Admin IDs loaded: {ADMIN_USER_IDS}")

# Forward Channels
FORWARD_CHANNELS_STR = os.getenv('FORWARD_CHANNELS', '')
FORWARD_CHANNELS = [channel.strip() for channel in FORWARD_CHANNELS_STR.split(',') if channel.strip()]

# AI Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama2')
ENABLE_AI = os.getenv('ENABLE_AI', 'true').lower() == 'true'

# Notification System
NOTIFICATION_ENABLED = os.getenv('NOTIFICATION_ENABLED', 'true').lower() == 'true'
AUTO_REPLY_ENABLED = os.getenv('AUTO_REPLY_ENABLED', 'true').lower() == 'true'
FOLLOW_UP_ENABLED = os.getenv('FOLLOW_UP_ENABLED', 'true').lower() == 'true'

# Form Builder
FORM_BUILDER_ENABLED = os.getenv('FORM_BUILDER_ENABLED', 'true').lower() == 'true'
MAX_FORMS_PER_USER = int(os.getenv('MAX_FORMS_PER_USER', '10'))

# Ecosystem Integration
SOCIAL_MEDIA_ENABLED = os.getenv('SOCIAL_MEDIA_ENABLED', 'false').lower() == 'true'
PAYMENT_ENABLED = os.getenv('PAYMENT_ENABLED', 'false').lower() == 'true'
CALENDAR_ENABLED = os.getenv('CALENDAR_ENABLED', 'true').lower() == 'true'
EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'bot.log')

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')

# Security
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'your-encryption-key-here')

# Rate Limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '30'))
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', '1000'))

# File Upload Limits
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '20971520'))  # 20MB
ALLOWED_FILE_TYPES = os.getenv('ALLOWED_FILE_TYPES', 'jpg,jpeg,png,gif,pdf,doc,docx,txt').split(',')

# Scheduled Forward Configuration
SCHEDULED_FORWARD_ENABLED = os.getenv('SCHEDULED_FORWARD_ENABLED', 'true').lower() == 'true'
MAX_SCHEDULED_FORWARDS = int(os.getenv('MAX_SCHEDULED_FORWARDS', '100'))
SCHEDULED_FORWARD_CLEANUP_DAYS = int(os.getenv('SCHEDULED_FORWARD_CLEANUP_DAYS', '7'))

# Health Check Configuration
HEALTH_CHECK_ENABLED = os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
HEALTH_CHECK_PORT = int(os.getenv('HEALTH_CHECK_PORT', '5000'))

# Development/Production
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')

# Webhook Configuration (if using webhooks instead of polling)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8443'))
WEBHOOK_CERT = os.getenv('WEBHOOK_CERT', '')
WEBHOOK_KEY = os.getenv('WEBHOOK_KEY', '')

# Proxy Configuration
PROXY_URL = os.getenv('PROXY_URL', '')
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

# Backup Configuration
BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'true').lower() == 'true'
BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))

# Monitoring
MONITORING_ENABLED = os.getenv('MONITORING_ENABLED', 'true').lower() == 'true'
METRICS_ENABLED = os.getenv('METRICS_ENABLED', 'true').lower() == 'true'
ALERT_EMAIL = os.getenv('ALERT_EMAIL', '')

# Feature Flags
ENABLE_ADVANCED_ANALYTICS = os.getenv('ENABLE_ADVANCED_ANALYTICS', 'false').lower() == 'true'
ENABLE_USER_PROFILES = os.getenv('ENABLE_USER_PROFILES', 'true').lower() == 'true'
ENABLE_MESSAGE_HISTORY = os.getenv('ENABLE_MESSAGE_HISTORY', 'true').lower() == 'true'
ENABLE_CUSTOM_COMMANDS = os.getenv('ENABLE_CUSTOM_COMMANDS', 'true').lower() == 'true'

# Localization
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'vi')
SUPPORTED_LANGUAGES = os.getenv('SUPPORTED_LANGUAGES', 'vi,en').split(',')

# Cache Configuration
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '3600'))
CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', '1000'))

# Performance
MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '10'))
REQUEST_TIMEOUT_SECONDS = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '30'))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', '3'))

# Validation
def validate_config():
    """Validate configuration values"""
    errors = []
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'your_telegram_token_here':
        errors.append("TELEGRAM_TOKEN is not set or invalid")
    
    if not ADMIN_USER_IDS:
        errors.append("ADMIN_USER_IDS is not set or invalid")
    
    if not SPREADSHEET_ID or SPREADSHEET_ID == 'your_google_spreadsheet_id_here':
        errors.append("SPREADSHEET_ID is not set or invalid")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

# Initialize validation
try:
    validate_config()
    print("✅ Configuration validated successfully")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    # Don't exit in production, just log the error
    if DEBUG:
        raise