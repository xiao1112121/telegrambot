import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from telegram import Bot
import bot_config

logger = logging.getLogger(__name__)


class NotificationManager:
    """Quản lý hệ thống notification thông minh"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.auto_replies = {}
        self.follow_up_tasks = {}
        self.marketing_campaigns = {}
        self.alert_rules = {}
        self._load_config()

    def _load_config(self):
        """Tải cấu hình notification"""
        # Auto-reply messages
        self.auto_replies = {
            'offline': {
                'vi': ("🤖 Cảm ơn bạn đã liên hệ! Hiện tại chúng tôi đang offline. "
                       "Chúng tôi sẽ phản hồi trong vòng 2-4 giờ tới. "
                       "Trong thời gian chờ, bạn có thể:\n"
                       "• 🤖 Hỏi AI Assistant\n"
                       "• 📝 Đăng ký thông tin\n"
                       "• 📞 Để lại số điện thoại"),
                'zh': ("🤖 感谢您的联系！我们目前离线。我们将在2-4小时内回复。"
                       "在等待期间，您可以：\n"
                       "• 🤖 询问AI助手\n"
                       "• 📝 注册信息\n"
                       "• 📞 留下电话号码")
            },
            'busy': {
                'vi': ("⏰ Hiện tại chúng tôi đang bận rộn. "
                       "Vui lòng để lại tin nhắn, chúng tôi sẽ liên hệ sớm nhất!"),
                'zh': "⏰ 我们目前很忙。请留言，我们会尽快联系！"
            },
            'welcome_back': {
                'vi': "👋 Chào mừng bạn quay lại! Có gì mới không?",
                'zh': "👋 欢迎回来！有什么新消息吗？"
            }
        }

        # Follow-up rules
        self.follow_up_rules = {
            'incomplete_registration': {
                'delay_hours': 24,
                'message': {
                    'vi': ("📝 Bạn chưa hoàn thành đăng ký. "
                           "Vui lòng hoàn thành để nhận ưu đãi đặc biệt!"),
                    'zh': ("📝 您尚未完成注册。请完成注册以获得特别优惠！")
                }
            },
            'no_response': {
                'delay_hours': 48,
                'message': {
                    'vi': ("💡 Bạn có câu hỏi gì khác không? "
                           "Chúng tôi luôn sẵn sàng hỗ trợ!"),
                    'zh': "💡 您还有其他问题吗？我们随时准备帮助！"
                }
            }
        }

        # Marketing templates
        self.marketing_templates = {
            'new_product': {
                'vi': ("🎉 Sản phẩm mới: {product_name}\n"
                       "💰 Giá: {price}\n"
                       "📅 Khuyến mãi đến: {end_date}\n"
                       "🔗 Chi tiết: {link}"),
                'zh': ("🎉 新产品：{product_name}\n"
                       "💰 价格：{price}\n"
                       "📅 促销截止：{end_date}\n"
                       "🔗 详情：{link}")
            },
            'promotion': {
                'vi': ("🔥 Khuyến mãi đặc biệt!\n"
                       "💎 Giảm {discount}% cho khách hàng VIP\n"
                       "⏰ Chỉ còn {time_left}\n"
                       "🎯 Áp dụng cho: {products}"),
                'zh': ("🔥 特别促销！\n"
                       "💎 VIP客户享受{discount}%折扣\n"
                       "⏰ 仅剩{time_left}\n"
                       "🎯 适用于：{products}")
            }
        }

        # Alert rules
        self.alert_rules = {
            'vip_customer': {
                'condition': lambda customer: customer.get('company', '').lower() in [
                    'vip', 'enterprise', 'corporate'
                ],
                'message': {
                    'pt': "⭐ Cliente VIP entrou em contato: {name} - {company}",
                    'vi': "⭐ Khách hàng VIP đã liên hệ: {name} - {company}",
                    'zh': "⭐ VIP客户已联系：{name} - {company}"
                }
            },
            'high_value_lead': {
                'condition': lambda customer: len(customer.get('interests', '')) > 50,
                'message': {
                    'pt': "💎 Lead de alto valor: {name} - {interests}",
                    'vi': "💎 Lead tiềm năng cao: {name} - {interests}",
                    'zh': "💎 高价值潜在客户：{name} - {interests}"
                }
            }
        }

    async def send_auto_reply(self, user_id: int, reply_type: str,
                              language: str = 'vi'):
        """Gửi auto-reply"""
        try:
            if reply_type in self.auto_replies:
                message = self.auto_replies[reply_type].get(
                    language, self.auto_replies[reply_type]['vi']
                )
                await self.bot.send_message(chat_id=user_id, text=message)
                logger.info(f"Auto-reply sent to {user_id}: {reply_type}")
        except Exception as e:
            logger.error(f"Error sending auto-reply: {e}")

    async def schedule_follow_up(self, user_id: int, follow_up_type: str,
                                 language: str = 'vi', delay_hours: int = None):
        """Lên lịch follow-up"""
        try:
            if follow_up_type in self.follow_up_rules:
                rule = self.follow_up_rules[follow_up_type]
                delay = delay_hours or rule['delay_hours']

                # Lưu task để thực hiện sau
                task = asyncio.create_task(
                    self._delayed_follow_up(user_id, rule['message'],
                                            language, delay)
                )
                self.follow_up_tasks[user_id] = task

                logger.info(f"Follow-up scheduled for {user_id}: "
                            f"{follow_up_type} in {delay}h")
        except Exception as e:
            logger.error(f"Error scheduling follow-up: {e}")

    async def _delayed_follow_up(self, user_id: int, message_template: Dict[str, str],
                                 language: str, delay_hours: int):
        """Thực hiện follow-up sau delay"""
        await asyncio.sleep(delay_hours * 3600)  # Convert hours to seconds

        try:
            message = message_template.get(language, message_template['vi'])
            await self.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Follow-up sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending follow-up: {e}")

    async def send_marketing_campaign(self, user_ids: List[int], campaign_type: str,
                                     data: Dict[str, Any], language: str = 'vi'):
        """Gửi marketing campaign"""
        try:
            if campaign_type in self.marketing_templates:
                template = self.marketing_templates[campaign_type]
                message = template.get(language, template['vi']).format(**data)

                success_count = 0
                for user_id in user_ids:
                    try:
                        await self.bot.send_message(chat_id=user_id, text=message)
                        success_count += 1
                        await asyncio.sleep(0.1)  # Rate limiting
                    except Exception as e:
                        logger.error(f"Error sending marketing to {user_id}: {e}")

                logger.info(f"Marketing campaign sent: {success_count}/"
                             f"{len(user_ids)} success")
                return success_count
        except Exception as e:
            logger.error(f"Error in marketing campaign: {e}")
            return 0

    async def check_and_alert(self, customer_data: Dict[str, Any],
                              language: str = 'vi'):
        """Kiểm tra và gửi alert cho admin"""
        try:
            for rule_name, rule in self.alert_rules.items():
                if rule['condition'](customer_data):
                    message = rule['message'].get(language,
                                                 rule['message']['vi'])
                    formatted_message = message.format(**customer_data)

                    # Gửi alert cho tất cả admin
                    for admin_id in bot_config.ADMIN_USER_IDS:
                        try:
                            await self.bot.send_message(
                                chat_id=admin_id,
                                text=f"🚨 ALERT: {formatted_message}"
                            )
                        except Exception as e:
                            logger.error(f"Error sending alert to admin "
                                         f"{admin_id}: {e}")

                    logger.info(f"Alert sent for {rule_name}: "
                               f"{customer_data.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def send_bulk_notification(self, user_ids: List[int], message: str,
                                    language: str = 'vi'):
        """Gửi thông báo hàng loạt"""
        try:
            success_count = 0
            for user_id in user_ids:
                try:
                    await self.bot.send_message(chat_id=user_id, text=message)
                    success_count += 1
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error sending notification to {user_id}: {e}")

            logger.info(f"Bulk notification sent: {success_count}/"
                        f"{len(user_ids)} success")
            return success_count
        except Exception as e:
            logger.error(f"Error in bulk notification: {e}")
            return 0


class NotificationScheduler:
    """Lên lịch các notification tự động"""

    def __init__(self, notification_manager: NotificationManager):
        self.notification_manager = notification_manager
        self.scheduled_tasks = {}

    async def schedule_daily_digest(self, admin_ids: List[int]):
        """Lên lịch báo cáo hàng ngày"""
        while True:
            try:
                # Chờ đến 9:00 sáng
                now = datetime.now()
                next_run = now.replace(hour=9, minute=0, second=0,
                                     microsecond=0)
                if now >= next_run:
                    next_run += timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                # Gửi báo cáo hàng ngày
                await self._send_daily_digest(admin_ids)

            except Exception as e:
                logger.error(f"Error in daily digest: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour if error

    async def _send_daily_digest(self, admin_ids: List[int]):
        """Gửi báo cáo hàng ngày"""
        try:
            # TODO: Lấy dữ liệu từ database
            message = (
                "📊 Báo cáo hàng ngày\n\n"
                "📈 Thống kê hôm nay:\n"
                "• Khách hàng mới: 0\n"
                "• Tin nhắn hỗ trợ: 0\n"
                "• Tương tác AI: 0\n"
                "• Chuyển đổi: 0%\n\n"
                "🎯 Cần chú ý:\n"
                "• Không có hoạt động nào"
            )

            for admin_id in admin_ids:
                try:
                    await self.notification_manager.bot.send_message(
                        chat_id=admin_id, text=message
                    )
                except Exception as e:
                    logger.error(f"Error sending digest to admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Error generating daily digest: {e}")


# Global instance
notification_manager = None
notification_scheduler = None


def init_notification_system(bot: Bot):
    """Khởi tạo hệ thống notification"""
    global notification_manager, notification_scheduler

    notification_manager = NotificationManager(bot)
    notification_scheduler = NotificationScheduler(notification_manager)

    # Bắt đầu scheduler với xử lý lỗi
    try:
        task = asyncio.create_task(
            notification_scheduler.schedule_daily_digest(bot_config.ADMIN_USER_IDS)
        )
        # Lưu task để có thể dừng sau này
        notification_scheduler.daily_digest_task = task
    except Exception as e:
        logger.error(f"Error starting notification scheduler: {e}")

    logger.info("Notification system initialized")


def get_notification_manager() -> NotificationManager:
    """Lấy instance notification manager"""
    return notification_manager
