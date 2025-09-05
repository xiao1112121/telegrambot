#!/usr/bin/env python3
"""
Advanced Analytics System for ABCDBET Bot
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class UserAnalytics:
    """Analytics system for tracking user behavior"""

    def __init__(self):
        self.user_actions = defaultdict(list)
        self.feature_usage = defaultdict(int)
        self.session_data = defaultdict(dict)
        self.conversion_tracking = defaultdict(dict)
        self._cleanup_running = False

    async def start_tasks(self):
        """Start background cleanup tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._cleanup_task())

    async def _cleanup_task(self):
        """Background task to clean up old data"""
        while self._cleanup_running:
            try:
                current_time = time.time()
                cutoff_time = current_time - 86400  # 24 hours

                # Clean up old user actions
                for user_id in list(self.user_actions.keys()):
                    self.user_actions[user_id] = [
                        action for action in self.user_actions[user_id]
                        if action['timestamp'] > cutoff_time
                    ]

                    # Remove user if no actions left
                    if not self.user_actions[user_id]:
                        del self.user_actions[user_id]

                # Clean up old session data
                for user_id in list(self.session_data.keys()):
                    if 'last_activity' in self.session_data[user_id]:
                        if self.session_data[user_id]['last_activity'] < cutoff_time:
                            del self.session_data[user_id]

                await asyncio.sleep(300)  # Run every 5 minutes

            except Exception as e:
                logger.error(f"Error in analytics cleanup task: {e}")
                await asyncio.sleep(300)

    def track_action(self, user_id: int, action: str, data: Optional[Dict] = None):
        """Track user action"""
        action_data = {
            'action': action,
            'timestamp': time.time(),
            'data': data or {}
        }
        self.user_actions[user_id].append(action_data)

        # Update feature usage
        self.feature_usage[action] += 1

        # Update session data
        if user_id not in self.session_data:
            self.session_data[user_id] = {
                'start_time': time.time(),
                'actions_count': 0,
                'last_activity': time.time()
            }

        self.session_data[user_id]['actions_count'] += 1
        self.session_data[user_id]['last_activity'] = time.time()

    def track_conversion(self, user_id: int, conversion_type: str, value: float = 0):
        """Track user conversion"""
        if user_id not in self.conversion_tracking:
            self.conversion_tracking[user_id] = {}

        if conversion_type not in self.conversion_tracking[user_id]:
            self.conversion_tracking[user_id][conversion_type] = {
                'count': 0,
                'total_value': 0,
                'first_conversion': time.time(),
                'last_conversion': time.time()
            }

        conv_data = self.conversion_tracking[user_id][conversion_type]
        conv_data['count'] += 1
        conv_data['total_value'] += value
        conv_data['last_conversion'] = time.time()

    def get_user_stats(self, user_id: int) -> Dict:
        """Get analytics for specific user"""
        if user_id not in self.user_actions:
            return {'error': 'User not found'}

        actions = self.user_actions[user_id]
        session = self.session_data.get(user_id, {})
        conversions = self.conversion_tracking.get(user_id, {})

        # Calculate engagement score
        engagement_score = min(100, len(actions) * 10)

        # Calculate session duration
        session_duration = 0
        if 'start_time' in session and 'last_activity' in session:
            session_duration = session['last_activity'] - session['start_time']

        return {
            'user_id': user_id,
            'total_actions': len(actions),
            'engagement_score': engagement_score,
            'session_duration_seconds': session_duration,
            'actions_count': session.get('actions_count', 0),
            'conversions': conversions,
            'recent_actions': actions[-10:] if len(actions) > 10 else actions
        }

    def get_feature_usage(self) -> Dict:
        """Get feature usage statistics"""
        return dict(self.feature_usage)

    def get_conversion_stats(self) -> Dict:
        """Get conversion statistics"""
        total_conversions = 0
        total_value = 0

        for user_conversions in self.conversion_tracking.values():
            for conv_data in user_conversions.values():
                total_conversions += conv_data['count']
                total_value += conv_data['total_value']

        return {
            'total_conversions': total_conversions,
            'total_value': total_value,
            'unique_users': len(self.conversion_tracking)
        }


class PerformanceAnalytics:
    """Analytics system for tracking bot performance"""

    def __init__(self):
        self.response_times = deque(maxlen=1000)
        self.error_counts = defaultdict(int)
        self.request_counts = defaultdict(int)
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)
        self._cleanup_running = False

    async def start_tasks(self):
        """Start background monitoring tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._monitor_task())

    async def _monitor_task(self):
        """Background task to monitor system performance"""
        while self._cleanup_running:
            try:
                # Monitor memory usage
                import psutil
                memory = psutil.virtual_memory()
                self.memory_usage.append({
                    'timestamp': time.time(),
                    'percent': memory.percent,
                    'used_mb': memory.used / (1024 * 1024)
                })

                # Monitor CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.cpu_usage.append({
                    'timestamp': time.time(),
                    'percent': cpu_percent
                })

                await asyncio.sleep(60)  # Run every minute

            except ImportError:
                logger.warning("psutil not available, skipping system monitoring")
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(60)

    def track_response_time(self, handler: str, response_time: float):
        """Track response time for handler"""
        self.response_times.append({
            'handler': handler,
            'response_time': response_time,
            'timestamp': time.time()
        })

    def track_error(self, error_type: str, handler: str = 'unknown'):
        """Track error occurrence"""
        self.error_counts[error_type] += 1
        self.request_counts[handler] += 1

    def track_request(self, handler: str):
        """Track request to handler"""
        self.request_counts[handler] += 1

    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        if not self.response_times:
            return {'error': 'No data available'}

        response_times = [rt['response_time'] for rt in self.response_times]

        return {
            'response_times': {
                'count': len(response_times),
                'average': sum(response_times) / len(response_times),
                'min': min(response_times),
                'max': max(response_times)
            },
            'error_counts': dict(self.error_counts),
            'request_counts': dict(self.request_counts),
            'memory_usage': list(self.memory_usage)[-10:] if self.memory_usage else [],
            'cpu_usage': list(self.cpu_usage)[-10:] if self.memory_usage else []
        }

    def get_system_info(self) -> Dict:
        """Get current system information"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'memory': {
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'percent': memory.percent
                },
                'disk': {
                    'total_gb': disk.total / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'free_gb': disk.free / (1024**3),
                    'percent': (disk.used / disk.total) * 100
                },
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=1)
            }
        except ImportError:
            return {'error': 'psutil not available'}


# Khởi tạo instances
user_analytics = UserAnalytics()
performance_analytics = PerformanceAnalytics()
