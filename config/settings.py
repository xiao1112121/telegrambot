"""
Configuration settings for the Telegram bot
"""
from typing import Dict, Any

# Bot Configuration
BOT_CONFIG = {
    'name': 'ABCDBET Bot',
    'version': '2.0.0',
    'description': 'Enhanced Telegram bot with advanced features',
    'admin_ids': [123456789],  # Replace with actual admin IDs
    'support_username': '@ABCDBETONLINE'
}

# Rate Limiting Configuration
RATE_LIMIT_CONFIG = {
    'enabled': True,
    'max_requests_per_minute': 10,
    'max_requests_per_hour': 100,
    'max_requests_per_day': 1000,
    'block_duration': 3600,  # 1 hour in seconds
    'cleanup_interval': 60    # 1 minute in seconds
}

# Cache Configuration
CACHE_CONFIG = {
    'enabled': True,
    'default_ttl': 300,      # 5 minutes
    'max_size': 1000,
    'cleanup_interval': 60    # 1 minute in seconds
}

# Security Configuration
SECURITY_CONFIG = {
    'enabled': True,
    'max_message_length': 4096,
    'max_urls_per_message': 3,
    'max_repeated_chars': 8,
    'max_messages_per_minute': 10,
    'blocked_words': [
        'spam', 'scam', 'hack', 'crack', 'warez', 'porn', 'sex'
    ]
}

# Analytics Configuration
ANALYTICS_CONFIG = {
    'enabled': True,
    'track_user_actions': True,
    'track_conversions': True,
    'track_performance': True,
    'data_retention_days': 30,
    'cleanup_interval': 300   # 5 minutes in seconds
}

# Message Templates
MESSAGE_TEMPLATES = {
    'welcome': 'Chào mừng bạn đến với {bot_name}! 🎉',
    'help': 'Đây là menu trợ giúp. Chọn tùy chọn bạn cần:',
    'error': 'Đã xảy ra lỗi. Vui lòng thử lại sau.',
    'rate_limit': 'Bạn đang gửi tin nhắn quá nhanh. Vui lòng chờ {time} giây.',
    'blocked': 'Tài khoản của bạn đã bị khóa do vi phạm quy tắc.',
    'main_menu': 'Chọn tùy chọn từ menu chính:'
}

# Feature Flags
FEATURE_FLAGS = {
    'rate_limiting': True,
    'caching': True,
    'security_filtering': True,
    'analytics': True,
    'performance_monitoring': True,
    'logging': True
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'bot.log',
    'max_size_mb': 10,
    'backup_count': 5
}

# Database Configuration (for future use)
DATABASE_CONFIG = {
    'enabled': False,
    'type': 'sqlite',  # sqlite, postgresql, mysql
    'host': 'localhost',
    'port': 5432,
    'database': 'bot_db',
    'username': '',
    'password': ''
}

# Performance Configuration
PERFORMANCE_CONFIG = {
    'max_response_time': 5.0,  # seconds
    'memory_warning_threshold': 100,  # MB
    'cpu_warning_threshold': 80,      # percent
    'cleanup_interval': 60            # seconds
}

# Scheduled Forward Configuration
SCHEDULED_FORWARD_CONFIG = {
    'enabled': True,
    'max_scheduled_tasks': 100,       # Số lịch hẹn tối đa
    'cleanup_days': 30,               # Số ngày giữ lại lịch cũ
    'timezone': 'Asia/Ho_Chi_Minh',   # Múi giờ
    'default_delay_seconds': 2.0,     # Độ trễ mặc định giữa các tin nhắn
    'max_delay_seconds': 300,         # Độ trễ tối đa
    'retry_attempts': 3,              # Số lần thử lại khi thất bại
    'retry_delay_seconds': 60         # Độ trễ giữa các lần thử lại
}

# Helper functions


def get_config(section: str) -> Dict[str, Any]:
    """Get configuration section"""
    config_map = {
        'bot': BOT_CONFIG,
        'rate_limit': RATE_LIMIT_CONFIG,
        'cache': CACHE_CONFIG,
        'security': SECURITY_CONFIG,
        'analytics': ANALYTICS_CONFIG,
        'messages': MESSAGE_TEMPLATES,
        'features': FEATURE_FLAGS,
        'logging': LOGGING_CONFIG,
        'database': DATABASE_CONFIG,
        'performance': PERFORMANCE_CONFIG,
        'scheduled_forward': SCHEDULED_FORWARD_CONFIG
    }
    return config_map.get(section, {})


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled"""
    return FEATURE_FLAGS.get(feature, False)


def get_message_template(key: str, **kwargs) -> str:
    """Get message template with optional formatting"""
    template = MESSAGE_TEMPLATES.get(key, key)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
