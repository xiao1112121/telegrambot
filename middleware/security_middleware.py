#!/usr/bin/env python3
"""
Security Middleware for ABCDBET Bot
"""

import asyncio
import time
import re
from collections import defaultdict, deque
from typing import Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Security middleware for spam detection and content filtering"""
    
    def __init__(self):
        self.spam_patterns = [
            r'(?i)(spam|advertisement|promote|buy now|click here)',
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'(?i)(casino|bet|gambling|money|earn|profit|rich|wealth)',
            r'(?i)(viagra|cialis|penis|sex|porn|adult)',
            r'(?i)(hack|crack|warez|pirate|free download)'
        ]
        self.user_message_history = defaultdict(lambda: deque(maxlen=50))
        self.blocked_users: Set[int] = set()
        self.block_timestamps = {}
        self.block_duration = 3600  # 1 hour
        self.max_urls_per_message = 3
        self.max_repeated_chars = 8
        self.max_messages_per_minute = 10
        self._cleanup_running = False
        
    async def start_tasks(self):
        """Start background cleanup tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._cleanup_task())
    
    async def _cleanup_task(self):
        """Background task to clean up old data and unblock users"""
        while self._cleanup_running:
            try:
                current_time = time.time()
                
                # Unblock expired users
                expired_users = [
                    user_id for user_id, block_time in self.block_timestamps.items()
                    if current_time - block_time > self.block_duration
                ]
                for user_id in expired_users:
                    self.blocked_users.discard(user_id)
                    del self.block_timestamps[user_id]
                
                # Clean up old message history
                cutoff_time = current_time - 3600  # Keep 1 hour
                for user_id in list(self.user_message_history.keys()):
                    # Remove old messages
                    while (self.user_message_history[user_id] and 
                           self.user_message_history[user_id][0]['timestamp'] < cutoff_time):
                        self.user_message_history[user_id].popleft()
                    
                    # Remove user if no messages left
                    if not self.user_message_history[user_id]:
                        del self.user_message_history[user_id]
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in security cleanup task: {e}")
                await asyncio.sleep(60)
    
    def validate_message(self, user_id: int, message_text: str) -> tuple[bool, Optional[str]]:
        """Validate message for security threats"""
        # Check if user is blocked
        if user_id in self.blocked_users:
            return False, "User is blocked due to security violations"
        
        # Check message length
        if len(message_text) > 4096:
            return False, "Message too long"
        
        # Check for repeated characters
        for char in message_text:
            if char * self.max_repeated_chars in message_text:
                return False, f"Too many repeated characters: {char}"
        
        # Check URL count
        url_count = len(re.findall(r'http[s]?://', message_text))
        if url_count > self.max_urls_per_message:
            return False, f"Too many URLs: {url_count}"
        
        # Check spam patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, message_text):
                return False, "Message contains prohibited content"
        
        # Check message frequency
        if not self._check_message_frequency(user_id):
            return False, "Message frequency too high"
        
        # Record message
        self._record_message(user_id, message_text)
        
        return True, None
    
    def _check_message_frequency(self, user_id: int) -> bool:
        """Check if user is sending messages too frequently"""
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Count messages in last minute
        recent_messages = sum(
            1 for msg in self.user_message_history[user_id]
            if msg['timestamp'] > minute_ago
        )
        
        return recent_messages < self.max_messages_per_minute
    
    def _record_message(self, user_id: int, message_text: str):
        """Record user message for analysis"""
        self.user_message_history[user_id].append({
            'text': message_text,
            'timestamp': time.time()
        })
    
    def block_user(self, user_id: int, duration: Optional[int] = None):
        """Block user for security violations"""
        block_duration = duration or self.block_duration
        self.blocked_users.add(user_id)
        self.block_timestamps[user_id] = time.time() + block_duration
        
        logger.warning(f"User {user_id} blocked for {block_duration} seconds")
    
    def unblock_user(self, user_id: int):
        """Unblock user"""
        self.blocked_users.discard(user_id)
        if user_id in self.block_timestamps:
            del self.block_timestamps[user_id]
        
        logger.info(f"User {user_id} unblocked")
    
    def get_user_security_status(self, user_id: int) -> Dict:
        """Get security status for user"""
        is_blocked = user_id in self.blocked_users
        block_remaining = 0
        
        if is_blocked:
            block_remaining = max(0, int(self.block_timestamps[user_id] - time.time()))
        
        recent_messages = len(self.user_message_history[user_id])
        
        return {
            'user_id': user_id,
            'is_blocked': is_blocked,
            'block_remaining_seconds': block_remaining,
            'recent_messages': recent_messages,
            'message_frequency_ok': self._check_message_frequency(user_id)
        }
    
    def get_security_stats(self) -> Dict:
        """Get overall security statistics"""
        total_users = len(self.user_message_history)
        blocked_users = len(self.blocked_users)
        
        return {
            'total_users': total_users,
            'blocked_users': blocked_users,
            'block_rate': (blocked_users / total_users * 100) if total_users > 0 else 0
        }


# Khởi tạo instance
security_middleware = SecurityMiddleware()
