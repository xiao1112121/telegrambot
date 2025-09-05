#!/usr/bin/env python3
"""
Logging Middleware for ABCDBET Bot
"""

import asyncio
import time
import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Middleware for detailed request logging"""
    
    def __init__(self, log_level: str = 'INFO'):
        self.log_level = log_level.upper()
        self.request_logs = []
        self.max_logs = 1000
        self._cleanup_running = False
        
    async def start_tasks(self):
        """Start background cleanup tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._cleanup_task())
    
    async def _cleanup_task(self):
        """Background task to clean up old logs"""
        while self._cleanup_running:
            try:
                # Keep only recent logs
                if len(self.request_logs) > self.max_logs:
                    self.request_logs = self.request_logs[-self.max_logs:]
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in logging cleanup task: {e}")
                await asyncio.sleep(300)
    
    async def __call__(self, update, context, next_handler):
        """Process request and log details"""
        start_time = time.time()
        request_id = f"req_{int(start_time * 1000)}"
        
        # Extract request info
        request_info = self._extract_request_info(update, request_id)
        
        # Log request start
        self._log_request_start(request_info)
        
        try:
            # Execute next handler
            result = await next_handler(update, context)
            
            # Log successful completion
            processing_time = time.time() - start_time
            self._log_request_success(request_info, processing_time, result)
            
            return result
            
        except Exception as e:
            # Log error
            processing_time = time.time() - start_time
            self._log_request_error(request_info, processing_time, str(e))
            raise
    
    def _extract_request_info(self, update, request_id: str) -> Dict:
        """Extract relevant information from update"""
        user = update.effective_user
        chat = update.effective_chat
        
        return {
            'request_id': request_id,
            'timestamp': time.time(),
            'user_id': user.id if user else None,
            'username': user.username if user else None,
            'chat_id': chat.id if chat else None,
            'chat_type': chat.type if chat else None,
            'update_type': self._get_update_type(update),
            'message_text': update.message.text if update.message and update.message.text else None,
            'callback_data': update.callback_query.data if update.callback_query else None
        }
    
    def _get_update_type(self, update) -> str:
        """Determine the type of update"""
        if update.message:
            return 'message'
        elif update.callback_query:
            return 'callback_query'
        elif update.inline_query:
            return 'inline_query'
        else:
            return 'unknown'
    
    def _log_request_start(self, request_info: Dict):
        """Log request start"""
        log_entry = {
            'type': 'request_start',
            'timestamp': datetime.fromtimestamp(request_info['timestamp']).isoformat(),
            'request_id': request_info['request_id'],
            'user_id': request_info['user_id'],
            'username': request_info['username'],
            'update_type': request_info['update_type']
        }
        
        self.request_logs.append(log_entry)
        
        if self.log_level == 'DEBUG':
            logger.debug(f"Request started: {request_info['request_id']} - "
                        f"User: {request_info['user_id']} - "
                        f"Type: {request_info['update_type']}")
    
    def _log_request_success(self, request_info: Dict, processing_time: float, result):
        """Log successful request completion"""
        log_entry = {
            'type': 'request_success',
            'timestamp': datetime.fromtimestamp(time.time()).isoformat(),
            'request_id': request_info['request_id'],
            'user_id': request_info['user_id'],
            'processing_time': round(processing_time, 3),
            'result': str(result)
        }
        
        self.request_logs.append(log_entry)
        
        if self.log_level in ['INFO', 'DEBUG']:
            logger.info(f"Request completed: {request_info['request_id']} - "
                       f"Time: {processing_time:.3f}s - "
                       f"User: {request_info['user_id']}")
    
    def _log_request_error(self, request_info: Dict, processing_time: float, error: str):
        """Log request error"""
        log_entry = {
            'type': 'request_error',
            'timestamp': datetime.fromtimestamp(time.time()).isoformat(),
            'request_id': request_info['request_id'],
            'user_id': request_info['user_id'],
            'processing_time': round(processing_time, 3),
            'error': error
        }
        
        self.request_logs.append(log_entry)
        
        logger.error(f"Request failed: {request_info['request_id']} - "
                    f"Time: {processing_time:.3f}s - "
                    f"User: {request_info['user_id']} - "
                    f"Error: {error}")
    
    def get_recent_logs(self, count: int = 100) -> list:
        """Get recent log entries"""
        return self.request_logs[-count:] if self.request_logs else []
    
    def get_logs_by_type(self, log_type: str) -> list:
        """Get logs filtered by type"""
        return [log for log in self.request_logs if log['type'] == log_type]
    
    def get_logs_by_user(self, user_id: int) -> list:
        """Get logs filtered by user ID"""
        return [log for log in self.request_logs if log.get('user_id') == user_id]
    
    def clear_logs(self):
        """Clear all stored logs"""
        self.request_logs.clear()
        logger.info("All logs cleared")


class RequestLogger:
    """Dedicated logger for request tracking"""
    
    def __init__(self, log_file: str = 'requests.log'):
        self.log_file = log_file
        self.logger = logging.getLogger('request_logger')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
    
    def log_request(self, request_data: Dict):
        """Log request data to file"""
        try:
            self.logger.info(f"Request: {request_data}")
        except Exception as e:
            logger.error(f"Error logging request: {e}")
    
    def log_response(self, response_data: Dict):
        """Log response data to file"""
        try:
            self.logger.info(f"Response: {response_data}")
        except Exception as e:
            logger.error(f"Error logging response: {e}")


# Khởi tạo instances
logging_middleware = LoggingMiddleware()
request_logger = RequestLogger()
