#!/usr/bin/env python3
"""
Webhook Handler for ABCDBET Bot
Handle real-time updates instead of polling
"""

import asyncio
import logging
from typing import Dict, Any
from aiohttp import web
from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self, application: Application, webhook_url: str, port: int = 8443):
        self.application = application
        self.webhook_url = webhook_url
        self.port = port
        self.app = web.Application()
        self.session = None

        # Thiết lập routes
        self.app.router.add_post('/webhook', self.handle_webhook)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/stats', self.get_stats)

        # Middleware để log requests
        self.app.middlewares.append(self.log_middleware)

    async def start(self):
        """Khởi động webhook server"""
        try:
            # Thiết lập webhook với Telegram
            await self.application.bot.set_webhook(
                url=self.webhook_url,
                allowed_updates=['message', 'callback_query', 'inline_query']
            )
            logger.info(f"✅ Webhook đã được thiết lập: {self.webhook_url}")

            # Khởi động web server
            runner = web.AppRunner(self.app)
            await runner.setup()

            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()

            logger.info(f"🚀 Webhook server đã khởi động trên port {self.port}")
            logger.info(f"🌐 Webhook URL: {self.webhook_url}")

            # Giữ server chạy
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"❌ Lỗi khởi động webhook: {e}")
            raise

    async def stop(self):
        """Dừng webhook server"""
        try:
            # Xóa webhook
            await self.application.bot.delete_webhook()
            logger.info("✅ Webhook đã được xóa")

            # Dừng web server
            if hasattr(self, 'runner'):
                await self.runner.cleanup()
            logger.info("🛑 Webhook server đã dừng")

        except Exception as e:
            logger.error(f"❌ Lỗi dừng webhook: {e}")

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Xử lý webhook từ Telegram"""
        try:
            # Lấy dữ liệu từ request
            data = await request.json()
            logger.debug(f"📥 Nhận webhook: {data}")

            # Tạo Update object
            update = Update.de_json(data, self.application.bot)

            # Xử lý update
            await self.application.process_update(update)

            return web.Response(text='OK', status=200)

        except Exception as e:
            logger.error(f"❌ Lỗi xử lý webhook: {e}")
            return web.Response(text='Error', status=500)

    async def health_check(self, request: web.Request) -> web.Response:
        """Kiểm tra trạng thái server"""
        try:
            # Kiểm tra kết nối với Telegram
            bot_info = await self.application.bot.get_me()

            health_data = {
                'status': 'healthy',
                'bot_name': bot_info.first_name,
                'bot_username': bot_info.username,
                'webhook_url': self.webhook_url,
                'timestamp': asyncio.get_event_loop().time()
            }

            return web.json_response(health_data)

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=500)

    async def get_stats(self, request: web.Request) -> web.Response:
        """Lấy thống kê webhook"""
        try:
            webhook_info = await self.application.bot.get_webhook_info()

            stats = {
                'webhook_url': webhook_info.url,
                'has_custom_certificate': webhook_info.has_custom_certificate,
                'pending_update_count': webhook_info.pending_update_count,
                'last_error_date': webhook_info.last_error_date.isoformat() if webhook_info.last_error_date else None,
                'last_error_message': webhook_info.last_error_message,
                'max_connections': webhook_info.max_connections,
                'allowed_updates': webhook_info.allowed_updates
            }

            return web.json_response(stats)

        except Exception as e:
            logger.error(f"❌ Lỗi lấy stats: {e}")
            return web.json_response({'error': str(e)}, status=500)

    @web.middleware
    async def log_middleware(self, request: web.Request, handler):
        """Middleware để log requests"""
        start_time = asyncio.get_event_loop().time()

        try:
            response = await handler(request)
            duration = asyncio.get_event_loop().time() - start_time

            logger.info(f"📊 {request.method} {request.path} - {response.status} - {duration:.3f}s")
            return response

        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            logger.error(f"❌ {request.method} {request.path} - Error - {duration:.3f}s - {e}")
            raise


class WebhookManager:
    def __init__(self, application: Application):
        self.application = application
        self.webhook_handler = None
        self.is_running = False

    async def start_webhook(self, webhook_url: str, port: int = 8443):
        """Khởi động webhook"""
        if self.is_running:
            logger.warning("⚠️ Webhook đang chạy")
            return

        try:
            self.webhook_handler = WebhookHandler(self.application, webhook_url, port)
            await self.webhook_handler.start()
            self.is_running = True

        except Exception as e:
            logger.error(f"❌ Không thể khởi động webhook: {e}")
            raise

    async def stop_webhook(self):
        """Dừng webhook"""
        if not self.is_running:
            logger.warning("⚠️ Webhook không chạy")
            return

        try:
            if self.webhook_handler:
                await self.webhook_handler.stop()
            self.is_running = False

        except Exception as e:
            logger.error(f"❌ Không thể dừng webhook: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái webhook"""
        return {
            'is_running': self.is_running,
            'webhook_url': self.webhook_handler.webhook_url if self.webhook_handler else None,
            'port': self.webhook_handler.port if self.webhook_handler else None
        }


# Utility functions
async def setup_webhook(application: Application, webhook_url: str, port: int = 8443):
    """Thiết lập webhook cho application"""
    manager = WebhookManager(application)
    await manager.start_webhook(webhook_url, port)
    return manager


async def switch_to_webhook(application: Application, webhook_url: str, port: int = 8443):
    """Chuyển từ polling sang webhook"""
    try:
        # Dừng polling nếu đang chạy
        if hasattr(application, '_running'):
            application.stop()
            logger.info("🛑 Đã dừng polling")

        # Khởi động webhook
        manager = await setup_webhook(application, webhook_url, port)
        logger.info("✅ Đã chuyển sang webhook mode")

        return manager

    except Exception as e:
        logger.error(f"❌ Lỗi chuyển sang webhook: {e}")
        raise


async def switch_to_polling(application: Application, webhook_manager: WebhookManager = None):
    """Chuyển từ webhook sang polling"""
    try:
        # Dừng webhook nếu đang chạy
        if webhook_manager and webhook_manager.is_running:
            await webhook_manager.stop_webhook()
            logger.info("🛑 Đã dừng webhook")

        # Khởi động polling
        await application.initialize()
        await application.start()
        await application.run_polling()
        logger.info("✅ Đã chuyển sang polling mode")

    except Exception as e:
        logger.error(f"❌ Lỗi chuyển sang polling: {e}")
        raise
