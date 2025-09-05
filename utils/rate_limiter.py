#!/usr/bin/env python3
"""
Smart Rate Limiter for ABCDBET Bot
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class SmartRateLimiter:
    """Smart rate limiter with multiple levels and automatic cleanup"""
    
    def __init__(self):
        self.rate_limits = {
            'per_minute': {'limit': 10, 'window': 60},
            'per_hour': {'limit': 100, 'window': 3600},
            'per_day': {'limit': 1000, 'window': 86400}
        }
        self.user_requests = defaultdict(lambda: defaultdict(deque))
        self.blocked_users: Set[int] = set()
        self.block_duration = 3600  # 1 hour
        self.block_timestamps = {}
        self._cleanup_running = False
        
    async def start_tasks(self):
        """Start background cleanup tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._cleanup_task())
    
    async def _cleanup_task(self):
        """Background task to clean up old requests and unblock users"""
        while self._cleanup_running:
            try:
                current_time = time.time()
                
                # Clean up old requests
                for user_id in list(self.user_requests.keys()):
                    for rate_type in list(self.user_requests[user_id].keys()):
                        window = self.rate_limits[rate_type]['window']
                        cutoff_time = current_time - window
                        
                        # Remove old requests
                        while (self.user_requests[user_id][rate_type] and 
                               self.user_requests[user_id][rate_type][0] < cutoff_time):
                            self.user_requests[user_id][rate_type].popleft()
                        
                        # Remove empty rate types
                        if not self.user_requests[user_id][rate_type]:
                            del self.user_requests[user_id][rate_type]
                    
                    # Remove user if no rate types left
                    if not self.user_requests[user_id]:
                        del self.user_requests[user_id]
                
                # Unblock users whose block time has expired
                expired_users = [
                    user_id for user_id, block_time in self.block_timestamps.items()
                    if current_time - block_time > self.block_duration
                ]
                for user_id in expired_users:
                    self.blocked_users.discard(user_id)
                    del self.block_timestamps[user_id]
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
    
    def is_allowed(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Kiểm tra xem user có được phép gửi request không"""
        now = time.time()
        
        # Kiểm tra user có bị block không
        if user_id in self.blocked_users:
            block_until = self.block_timestamps[user_id]
            if now < block_until:
                remaining = int(block_until - now)
                return False, f"User bị block trong {remaining} giây"
            else:
                # Hết thời gian block
                self.blocked_users.discard(user_id)
                del self.block_timestamps[user_id]
        
        # Kiểm tra rate limits
        for rate_type, config in self.rate_limits.items():
            if rate_type not in self.user_requests[user_id]:
                self.user_requests[user_id][rate_type] = deque()
            
            # Remove old requests outside the window
            window = config['window']
            cutoff_time = now - window
            while (self.user_requests[user_id][rate_type] and 
                   self.user_requests[user_id][rate_type][0] < cutoff_time):
                self.user_requests[user_id][rate_type].popleft()
            
            # Check if limit exceeded
            if len(self.user_requests[user_id][rate_type]) >= config['limit']:
                # Block user
                self.blocked_users.add(user_id)
                self.block_timestamps[user_id] = now + self.block_duration
                return False, f"Vượt quá giới hạn {config['limit']} requests/{rate_type}"
        
        # Add current request
        for rate_type in self.rate_limits.keys():
            self.user_requests[user_id][rate_type].append(now)
        
        return True, None
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Lấy thống kê rate limit của user"""
        now = time.time()
        requests = self.user_requests.get(user_id, {})
        
        stats = {}
        for rate_type, config in self.rate_limits.items():
            if rate_type in requests:
                # Count requests in current window
                window = config['window']
                cutoff_time = now - window
                count = sum(1 for req_time in requests[rate_type] if req_time > cutoff_time)
                stats[rate_type] = {
                    'current': count,
                    'limit': config['limit'],
                    'remaining': max(0, config['limit'] - count)
                }
            else:
                stats[rate_type] = {
                    'current': 0,
                    'limit': config['limit'],
                    'remaining': config['limit']
                }
        
        # Check if user is blocked
        is_blocked = user_id in self.blocked_users
        block_remaining = 0
        if is_blocked:
            block_remaining = max(0, int(self.block_timestamps[user_id] - now))
        
        return {
            'user_id': user_id,
            'is_blocked': is_blocked,
            'block_remaining_seconds': block_remaining,
            'rate_limits': stats
        }
    
    def block_user(self, user_id: int, duration: Optional[int] = None):
        """Block user manually"""
        block_duration = duration or self.block_duration
        self.blocked_users.add(user_id)
        self.block_timestamps[user_id] = time.time() + block_duration
    
    def unblock_user(self, user_id: int):
        """Unblock user manually"""
        self.blocked_users.discard(user_id)
        if user_id in self.block_timestamps:
            del self.block_timestamps[user_id]


class MessageValidator:
    """Validator cho nội dung tin nhắn"""
    
    def __init__(self):
        self.max_length = 4096
        self.max_urls = 5
        self.max_repeated_chars = 10
        self.blocked_words = {
            'spam', 'scam', 'hack', 'crack', 'warez', 'porn', 'sex'
        }
    
    def validate_message(self, text: str) -> Tuple[bool, Optional[str]]:
        """Kiểm tra tính hợp lệ của tin nhắn"""
        if not text or not text.strip():
            return False, "Tin nhắn không được để trống"
        
        # Kiểm tra độ dài
        if len(text) > self.max_length:
            return False, f"Tin nhắn quá dài (tối đa {self.max_length} ký tự)"
        
        # Kiểm tra số lượng URL
        url_count = text.count('http://') + text.count('https://')
        if url_count > self.max_urls:
            return False, f"Quá nhiều link (tối đa {self.max_urls})"
        
        # Kiểm tra ký tự lặp lại
        for char in text:
            if char * self.max_repeated_chars in text:
                return False, f"Ký tự '{char}' lặp lại quá nhiều lần"
        
        # Kiểm tra từ bị cấm
        text_lower = text.lower()
        for word in self.blocked_words:
            if word in text_lower:
                return False, f"Từ '{word}' bị cấm"
        
        return True, None


# Khởi tạo instances
smart_rate_limiter = SmartRateLimiter()
message_validator = MessageValidator()
