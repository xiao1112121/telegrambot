#!/usr/bin/env python3
"""
Performance Middleware for ABCDBET Bot
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class PerformanceMiddleware:
    """Middleware for tracking bot performance metrics"""
    
    def __init__(self):
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.request_counts = defaultdict(int)
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)
        self.start_time = time.time()
        self._monitoring_running = False
        
    async def start_tasks(self):
        """Start background monitoring tasks"""
        if not self._monitoring_running:
            self._monitoring_running = True
            asyncio.create_task(self._monitor_task())
    
    async def _monitor_task(self):
        """Background task to monitor system performance"""
        while self._monitoring_running:
            try:
                # Monitor memory usage
                try:
                    import psutil
                    memory = psutil.virtual_memory()
                    self.memory_usage.append({
                        'timestamp': time.time(),
                        'percent': memory.percent,
                        'used_mb': memory.used / (1024 * 1024),
                        'available_mb': memory.available / (1024 * 1024)
                    })
                    
                    # Monitor CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.cpu_usage.append({
                        'timestamp': time.time(),
                        'percent': cpu_percent
                    })
                    
                except ImportError:
                    logger.debug("psutil not available, skipping system monitoring")
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(60)
    
    def track_request(self, handler: str, start_time: float):
        """Track request start time"""
        self.request_counts[handler] += 1
        return start_time
    
    def track_response_time(self, handler: str, start_time: float):
        """Track response time for handler"""
        response_time = time.time() - start_time
        self.response_times[handler].append(response_time)
        
        # Keep only last 100 measurements per handler
        if len(self.response_times[handler]) > 100:
            self.response_times[handler].pop(0)
    
    def track_error(self, handler: str, error_type: str):
        """Track error occurrence"""
        self.error_counts[error_type] += 1
        self.request_counts[handler] += 1
    
    def get_handler_stats(self, handler: str) -> Dict:
        """Get performance statistics for specific handler"""
        response_times = self.response_times.get(handler, [])
        request_count = self.request_counts.get(handler, 0)
        
        if not response_times:
            return {
                'handler': handler,
                'request_count': request_count,
                'error': 'No response time data available'
            }
        
        return {
            'handler': handler,
            'request_count': request_count,
            'response_times': {
                'count': len(response_times),
                'average': sum(response_times) / len(response_times),
                'min': min(response_times),
                'max': max(response_times),
                'p95': sorted(response_times)[int(len(response_times) * 0.95)]
            }
        }
    
    def get_overall_stats(self) -> Dict:
        """Get overall performance statistics"""
        uptime = time.time() - self.start_time
        
        # Calculate total requests and errors
        total_requests = sum(self.request_counts.values())
        total_errors = sum(self.error_counts.values())
        
        # Calculate average response time across all handlers
        all_response_times = []
        for times in self.response_times.values():
            all_response_times.extend(times)
        
        avg_response_time = 0
        if all_response_times:
            avg_response_time = sum(all_response_times) / len(all_response_times)
        
        return {
            'uptime_seconds': uptime,
            'uptime_formatted': self._format_duration(uptime),
            'total_requests': total_requests,
            'total_errors': total_errors,
            'error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0,
            'average_response_time': avg_response_time,
            'handlers': list(self.request_counts.keys()),
            'memory_usage': list(self.memory_usage)[-10:] if self.memory_usage else [],
            'cpu_usage': list(self.cpu_usage)[-10:] if self.cpu_usage else []
        }
    
    def get_system_info(self) -> Dict:
        """Get current system information"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'percent': memory.percent
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent': round((disk.used / disk.total) * 100, 2)
                },
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=1)
            }
        except ImportError:
            return {'error': 'psutil not available'}
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def reset_stats(self):
        """Reset all performance statistics"""
        self.response_times.clear()
        self.error_counts.clear()
        self.request_counts.clear()
        self.memory_usage.clear()
        self.cpu_usage.clear()
        self.start_time = time.time()
        logger.info("Performance statistics reset")


# Khởi tạo instance
performance_middleware = PerformanceMiddleware()
