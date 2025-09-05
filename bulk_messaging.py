#!/usr/bin/env python3
"""
Bulk Messaging System - Hệ thống gửi tin nhắn hàng loạt
Hỗ trợ gửi text, hình ảnh, video, file kèm caption
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from telegram import Bot
from telegram.constants import ParseMode
from google_sheets import GoogleSheetsManager

logger = logging.getLogger(__name__)


class BulkMessagingManager:
    def __init__(self, bot: Bot, sheets_manager: GoogleSheetsManager):
        self.bot = bot
        self.sheets_manager = sheets_manager
        self.message_queue = []
        self.sending_in_progress = False
        self.stop_sending = False  # Thêm flag để dừng gửi tin nhắn

    def stop_bulk_messaging(self):
        """Dừng gửi tin nhắn hàng loạt"""
        self.stop_sending = True
        logger.info("🛑 Yêu cầu dừng gửi tin nhắn hàng loạt")

    def reset_stop_flag(self):
        """Reset flag dừng gửi tin nhắn"""
        self.stop_sending = False
        logger.info("🔄 Reset flag dừng gửi tin nhắn")

    async def send_bulk_message(
        self,
        message_content: str,
        filter_type: Optional[str] = None,
        filter_value: Optional[str] = None,
        media_file: Optional[str] = None,
        media_type: Optional[str] = None,
        delay_between_messages: float = 1.0,
        max_messages_per_minute: int = 30
    ) -> Dict[str, any]:
        """
        Gửi tin nhắn hàng loạt đến khách hàng
        Args:
            message_content: Nội dung tin nhắn (text hoặc caption)
            filter_type: Loại bộ lọc ('action', 'date', 'username')
            filter_value: Giá trị bộ lọc
            media_file: Đường dẫn file media (hình ảnh, video, file)
            media_type: Loại media ('photo', 'video', 'document', 'audio')
            delay_between_messages: Độ trễ giữa các tin nhắn (giây)
            max_messages_per_minute: Số tin nhắn tối đa mỗi phút

        Returns:
            Dict chứa kết quả gửi tin nhắn
        """
        try:
            # Lấy danh sách khách hàng
            if filter_type and filter_value:
                customers = self.sheets_manager.get_customers_by_filter(filter_type, filter_value)
            else:
                customers = self.sheets_manager.get_all_customers()

            if not customers:
                return {
                    'success': False,
                    'message': 'Không tìm thấy khách hàng nào',
                    'total_customers': 0,
                    'sent_count': 0,
                    'failed_count': 0
                }

            logger.info(f"Bắt đầu gửi tin nhắn hàng loạt đến {len(customers)} khách hàng")

            # Gửi tin nhắn với rate limiting
            results = await self._send_messages_with_rate_limit(
                customers, message_content, media_file, media_type, delay_between_messages, max_messages_per_minute
            )

            # Ghi log kết quả
            self._log_bulk_message_results(message_content, results, media_file, media_type)

            return {
                'success': True,
                'message': 'Đã gửi tin nhắn thành công',
                'total_customers': len(customers),
                'sent_count': results['sent_count'],
                'failed_count': results['failed_count'],
                'media_sent': bool(media_file),
                'media_type': media_type,
                'results': results
            }

        except Exception as e:
            logger.error(f"Lỗi gửi tin nhắn hàng loạt: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}',
                'total_customers': 0,
                'sent_count': 0,
                'failed_count': 0
            }

    async def _send_messages_with_rate_limit(
        self,
        customers: List[Dict],
        message_content: str,
        media_file: Optional[str],
        media_type: Optional[str],
        delay_between_messages: float,
        max_messages_per_minute: int
    ) -> Dict[str, any]:
        """Gửi tin nhắn với rate limiting để tránh bị chặn"""

        sent_count = 0
        failed_count = 0
        failed_users = []

        # Tính toán delay để đảm bảo không vượt quá giới hạn
        actual_delay = max(delay_between_messages, 60.0 / max_messages_per_minute)

        # Loại bỏ trùng lặp user_id - chỉ giữ lại user_id đầu tiên
        unique_customers = []
        seen_user_ids = set()

        for customer in customers:
            user_id = customer.get('user_id')
            if user_id and user_id not in seen_user_ids:
                unique_customers.append(customer)
                seen_user_ids.add(user_id)
            elif user_id:
                logger.info(f"Bỏ qua user_id trùng lặp: {user_id}")

        logger.info(f"Tổng khách hàng: {len(customers)}, Sau khi loại bỏ trùng lặp: {len(unique_customers)}")

        # Giới hạn số tin nhắn gửi mỗi lần để tránh spam
        max_messages_per_batch = 20
        customers_to_process = unique_customers[:max_messages_per_batch]

        logger.info(f"Gửi tin nhắn đến {len(customers_to_process)} khách hàng đầu tiên (giới hạn {max_messages_per_batch})")

        for i, customer in enumerate(customers_to_process):
            # Kiểm tra xem có yêu cầu dừng không
            if self.stop_sending:
                logger.info("🛑 Dừng gửi tin nhắn theo yêu cầu")
                break

            try:
                user_id = customer.get('user_id')
                if not user_id:
                    failed_count += 1
                    failed_users.append({
                        'user_id': 'Unknown',
                        'username': customer.get('username', 'Unknown'),
                        'error': 'Không có User ID'
                    })
                    continue

                # Kiểm tra xem user có phải admin không (bỏ qua admin)
                if str(user_id) in ['6513278007', '7363247246', '7988655018']:
                    logger.info(f"Bỏ qua admin user {user_id}")
                    continue

                # Kiểm tra và loại bỏ bot khác
                username = customer.get('username', '').lower()
                full_name = customer.get('full_name', '').lower()

                # Danh sách từ khóa để nhận diện bot
                bot_keywords = [
                    'bot', 'anonymous', 'group', 'channel', 'telegram',
                    'system', 'service', 'helper', 'assistant'
                ]

                # Kiểm tra username và full_name có chứa từ khóa bot không
                is_bot = any(keyword in username or keyword in full_name for keyword in bot_keywords)

                if is_bot:
                    logger.info(f"Bỏ qua bot: {username} ({full_name})")
                    continue

                # Gửi tin nhắn
                success = await self._send_single_message(
                    user_id, message_content, customer, media_file, media_type
                )

                if success:
                    sent_count += 1
                    # Cập nhật trạng thái trong Google Sheets
                    self.sheets_manager.update_customer_message_status(user_id, True)
                    logger.info(f"✅ Đã gửi tin nhắn đến user {user_id}")
                else:
                    failed_count += 1
                    failed_users.append({
                        'user_id': user_id,
                        'username': customer.get('username', 'Unknown'),
                        'error': 'Gửi tin nhắn thất bại'
                    })

                # Delay giữa các tin nhắn (tăng delay để tránh spam)
                if i < len(customers_to_process) - 1:
                    await asyncio.sleep(actual_delay * 2)  # Tăng delay gấp đôi

                # Log tiến độ
                if (i + 1) % 5 == 0:  # Log mỗi 5 tin nhắn thay vì 10
                    logger.info(f"Tiến độ: {i + 1}/{len(customers_to_process)} tin nhắn đã gửi")

            except Exception as e:
                failed_count += 1
                failed_users.append({
                    'user_id': customer.get('user_id', 'Unknown'),
                    'username': customer.get('username', 'Unknown'),
                    'error': str(e)
                })
                logger.error(f"Lỗi gửi tin nhắn đến user {customer.get('user_id')}: {e}")

        # Reset flag dừng sau khi hoàn thành
        self.stop_sending = False

        # Thông báo kết thúc
        if len(unique_customers) > max_messages_per_batch:
            logger.info(f"⚠️ Chỉ gửi {max_messages_per_batch}/{len(unique_customers)} khách hàng để tránh spam. Chạy lại để gửi tiếp.")

        logger.info(f"✅ Hoàn thành gửi tin nhắn: {sent_count} thành công, {failed_count} thất bại")

        return {
            'sent_count': sent_count,
            'failed_count': failed_count,
            'failed_users': failed_users,
            'total_processed': len(customers_to_process),
            'total_customers': len(unique_customers),
            'original_total': len(customers),
            'duplicates_removed': len(customers) - len(unique_customers),
            'batch_limit': max_messages_per_batch
        }

    async def _send_single_message(
        self,
        user_id: str,
        message_content: str,
        customer_info: Dict,
        media_file: Optional[str] = None,
        media_type: Optional[str] = None
    ) -> bool:
        """Gửi một tin nhắn đến một khách hàng cụ thể"""
        try:
            # Tùy chỉnh tin nhắn với thông tin khách hàng
            personalized_message = self._personalize_message(message_content, customer_info)

            # Gửi tin nhắn với media hoặc chỉ text
            if media_file and media_type and os.path.exists(media_file):
                await self._send_media_message(user_id, personalized_message, media_file, media_type)
            else:
                # Gửi chỉ text
                await self.bot.send_message(
                    chat_id=int(user_id),
                    text=personalized_message,
                    parse_mode=ParseMode.HTML
                )

            # Ghi log tin nhắn đã gửi
            self.sheets_manager.add_message_log(
                user_id, message_content, 'bulk_message', 'sent'
            )

            return True

        except Exception as e:
            logger.error(f"Lỗi gửi tin nhắn đến user {user_id}: {e}")

            # Ghi log lỗi
            self.sheets_manager.add_message_log(
                user_id, message_content, 'bulk_message', 'failed'
            )

            return False

    async def _send_media_message(
        self,
        user_id: str,
        caption: str,
        media_file: str,
        media_type: str
    ):
        """Gửi tin nhắn media với caption"""
        try:
            with open(media_file, 'rb') as file:
                if media_type == 'photo':
                    await self.bot.send_photo(
                        chat_id=int(user_id),
                        photo=file,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'video':
                    await self.bot.send_video(
                        chat_id=int(user_id),
                        video=file,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'document':
                    await self.bot.send_document(
                        chat_id=int(user_id),
                        document=file,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'audio':
                    await self.bot.send_audio(
                        chat_id=int(user_id),
                        audio=file,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    # Fallback: gửi document
                    await self.bot.send_document(
                        chat_id=int(user_id),
                        document=file,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )

        except Exception as e:
            logger.error(f"Lỗi gửi media đến user {user_id}: {e}")
            # Fallback: gửi chỉ text nếu media thất bại
            await self.bot.send_message(
                chat_id=int(user_id),
                text=caption,
                parse_mode=ParseMode.HTML
            )

    def _personalize_message(self, message_content: str, customer_info: Dict) -> str:
        """Tùy chỉnh tin nhắn với thông tin khách hàng"""
        try:
            personalized = message_content

            # Thay thế các placeholder
            replacements = {
                '{username}': customer_info.get('username', ''),
                '{full_name}': customer_info.get('full_name', ''),
                '{action}': customer_info.get('action', ''),
                '{date}': customer_info.get('time', '').split()[0] if customer_info.get('time') else ''
            }

            for placeholder, value in replacements.items():
                personalized = personalized.replace(placeholder, str(value))

            return personalized

        except Exception as e:
            logger.error(f"Lỗi tùy chỉnh tin nhắn: {e}")
            return message_content

    def _log_bulk_message_results(
        self,
        message_content: str,
        results: Dict,
        media_file: Optional[str] = None,
        media_type: Optional[str] = None
    ):
        """Ghi log kết quả gửi tin nhắn hàng loạt"""
        try:
            # Thông tin cơ bản
            log_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message_content': message_content[:100] + "..." if len(message_content) > 100 else message_content,
                'total_customers': results['total_customers'],
                'sent_count': results['sent_count'],
                'failed_count': results['failed_count'],
                'media_file': media_file or 'None',
                'media_type': media_type or 'text_only',
                'success_rate': f"{(results['sent_count'] / results['total_customers'] * 100):.1f}%" if results['total_customers'] > 0 else "0%"
            }

            # Thêm thông tin về trùng lặp nếu có
            if 'original_total' in results and 'duplicates_removed' in results:
                log_data['original_total'] = results['original_total']
                log_data['duplicates_removed'] = results['duplicates_removed']
                log_data['duplicate_info'] = f"Loại bỏ {results['duplicates_removed']} user_id trùng lặp"

            logger.info(f"📊 Kết quả gửi tin nhắn hàng loạt: {log_data}")

            # Log chi tiết về trùng lặp
            if 'duplicates_removed' in results and results['duplicates_removed'] > 0:
                logger.info(f"🔄 Đã loại bỏ {results['duplicates_removed']} user_id trùng lặp từ {results['original_total']} khách hàng gốc")

        except Exception as e:
            logger.error(f"Lỗi ghi log kết quả: {e}")

    async def schedule_bulk_message(
        self,
        message_content: str,
        schedule_time: datetime,
        filter_type: Optional[str] = None,
        filter_value: Optional[str] = None,
        media_file: Optional[str] = None,
        media_type: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Lên lịch gửi tin nhắn hàng loạt

        Args:
            message_content: Nội dung tin nhắn
            schedule_time: Thời gian gửi
            filter_type: Loại bộ lọc
            filter_value: Giá trị bộ lọc
            media_file: File media
            media_type: Loại media

        Returns:
            Dict chứa kết quả lên lịch
        """
        try:
            # Tính thời gian delay
            now = datetime.now()
            if schedule_time <= now:
                return {
                    'success': False,
                    'message': 'Thời gian lên lịch phải lớn hơn thời gian hiện tại'
                }

            delay_seconds = (schedule_time - now).total_seconds()

            # Lên lịch gửi tin nhắn
            asyncio.create_task(
                self._delayed_bulk_message(
                    delay_seconds, message_content, filter_type, filter_value, media_file, media_type
                )
            )

            return {
                'success': True,
                'message': f'Đã lên lịch gửi tin nhắn vào {schedule_time.strftime("%Y-%m-%d %H:%M:%S")}',
                'scheduled_time': schedule_time.strftime("%Y-%m-%d %H:%M:%S"),
                'delay_seconds': delay_seconds
            }

        except Exception as e:
            logger.error(f"Lỗi lên lịch gửi tin nhắn: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }

    async def _delayed_bulk_message(
        self,
        delay_seconds: float,
        message_content: str,
        filter_type: Optional[str],
        filter_value: Optional[str],
        media_file: Optional[str],
        media_type: Optional[str]
    ):
        """Gửi tin nhắn sau khi delay"""
        try:
            await asyncio.sleep(delay_seconds)
            await self.send_bulk_message(
                message_content, filter_type, filter_value, media_file, media_type
            )
        except Exception as e:
            logger.error(f"Lỗi gửi tin nhắn đã lên lịch: {e}")

    def get_supported_media_types(self) -> List[str]:
        """Lấy danh sách loại media được hỗ trợ"""
        return ['photo', 'video', 'document', 'audio']

    def validate_media_file(self, file_path: str, media_type: str) -> Dict[str, any]:
        """
        Kiểm tra tính hợp lệ của file media

        Args:
            file_path: Đường dẫn file
            media_type: Loại media

        Returns:
            Dict chứa kết quả kiểm tra
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'valid': False,
                    'message': 'Arquivo não existe',
                    'file_size': 0
                }

            file_size = os.path.getsize(file_path)

            # Kiểm tra kích thước file theo loại
            max_sizes = {
                'photo': 10 * 1024 * 1024,  # 10MB
                'video': 50 * 1024 * 1024,  # 50MB
                'document': 2000 * 1024 * 1024,  # 2GB
                'audio': 50 * 1024 * 1024  # 50MB
            }

            max_size = max_sizes.get(media_type, 50 * 1024 * 1024)

            if file_size > max_size:
                return {
                    'valid': False,
                    'message': f'Arquivo muito grande. Máximo: {max_size // (1024 * 1024)}MB',
                    'file_size': file_size
                }

            return {
                'valid': True,
                'message': 'Arquivo válido',
                'file_size': file_size
            }

        except Exception as e:
            return {
                'valid': False,
                'message': f'Erro ao verificar arquivo: {str(e)}',
                'file_size': 0
            }


# Hàm helper để sử dụng dễ dàng
async def send_bulk_message_to_customers(
    message_content: str,
    filter_type: Optional[str] = None,
    filter_value: Optional[str] = None,
    media_file: Optional[str] = None,
    media_type: Optional[str] = None
) -> Dict[str, any]:
    """Gửi tin nhắn hàng loạt đến khách hàng"""
    from bot_config import TELEGRAM_TOKEN
    bot = Bot(token=TELEGRAM_TOKEN)
    sheets_manager = GoogleSheetsManager()
    manager = BulkMessagingManager(bot, sheets_manager)
    return await manager.send_bulk_message(
        message_content, filter_type, filter_value, media_file, media_type
    )


async def schedule_bulk_message_for_customers(
    message_content: str,
    schedule_time: datetime,
    filter_type: Optional[str] = None,
    filter_value: Optional[str] = None,
    media_file: Optional[str] = None,
    media_type: Optional[str] = None
) -> Dict[str, any]:
    """Lên lịch gửi tin nhắn hàng loạt"""
    from bot_config import TELEGRAM_TOKEN
    bot = Bot(token=TELEGRAM_TOKEN)
    sheets_manager = GoogleSheetsManager()
    manager = BulkMessagingManager(bot, sheets_manager)
    return await manager.schedule_bulk_message(
        message_content, schedule_time, filter_type, filter_value, media_file, media_type
    )
