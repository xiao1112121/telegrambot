#!/usr/bin/env python3
"""
Analytics Middleware for ABCDBET Bot
"""

import logging

logger = logging.getLogger(__name__)


class AnalyticsMiddleware:
    """Middleware for integrating with UserAnalytics system"""
    
    def __init__(self, user_analytics):
        self.user_analytics = user_analytics
    
    async def __call__(self, update, context, next_handler):
        """Process request and track analytics"""
        try:
            # Get user info
            user = update.effective_user
            if not user:
                return await next_handler(update, context)
            
            user_id = user.id
            username = user.username
            full_name = user.full_name
            
            # Track user action
            action = self._determine_action(update)
            self.user_analytics.track_action(
                user_id=user_id,
                action=action,
                data={
                    'username': username,
                    'full_name': full_name,
                    'chat_type': update.effective_chat.type if update.effective_chat else None,
                    'message_type': self._get_message_type(update)
                }
            )
            
            # Track conversion if applicable
            if self._is_conversion_action(update):
                self.user_analytics.track_conversion(
                    user_id=user_id,
                    conversion_type='feature_usage',
                    value=1.0
                )
            
            # Continue to next handler
            return await next_handler(update, context)
            
        except Exception as e:
            logger.error(f"Error in analytics middleware: {e}")
            # Continue to next handler even if analytics fails
            return await next_handler(update, context)
    
    def _determine_action(self, update) -> str:
        """Determine the action type from update"""
        if update.message:
            if update.message.text:
                return 'text_message'
            elif update.message.photo:
                return 'photo_message'
            elif update.message.document:
                return 'document_message'
            else:
                return 'other_message'
        elif update.callback_query:
            return f'callback_{update.callback_query.data}'
        elif update.inline_query:
            return 'inline_query'
        else:
            return 'unknown_action'
    
    def _get_message_type(self, update) -> str:
        """Get the type of message"""
        if update.message:
            if update.message.text:
                return 'text'
            elif update.message.photo:
                return 'photo'
            elif update.message.document:
                return 'document'
            elif update.message.sticker:
                return 'sticker'
            else:
                return 'other'
        return 'none'
    
    def _is_conversion_action(self, update) -> bool:
        """Check if this action represents a conversion"""
        if update.callback_query:
            data = update.callback_query.data
            # Define what actions are considered conversions
            conversion_actions = [
                'start', 'help', 'support', 'register', 'deposit', 'withdraw'
            ]
            return any(action in data for action in conversion_actions)
        return False


# Khởi tạo instance (sẽ được inject với user_analytics)
analytics_middleware = None
