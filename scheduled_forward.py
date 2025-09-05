#!/usr/bin/env python3
"""
Scheduled Forward System - Hệ thống hẹn giờ chuyển tiếp tin nhắn
Hỗ trợ hẹn giờ chuyển tiếp tin nhắn, media, và bulk message
"""

import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from telegram import Bot
from telegram.constants import ParseMode
from google_sheets import GoogleSheetsManager

logger = logging.getLogger(__name__)


class ScheduledForwardManager:
    """Quản lý hệ thống hẹn giờ chuyển tiếp tin nhắn"""

    def __init__(self, bot: Bot, sheets_manager: GoogleSheetsManager):
        self.bot = bot
        self.sheets_manager = sheets_manager
        self.scheduled_tasks = {}  # Lưu trữ các task đã lên lịch
        self.scheduled_data = {}   # Lưu trữ dữ liệu tin nhắn cần chuyển tiếp
        self.schedule_file = "scheduled_forwards.json"
        self._load_scheduled_data()

    def _load_scheduled_data(self):
        """Tải dữ liệu lịch hẹn giờ từ file"""
        try:
            if os.path.exists(self.schedule_file):
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scheduled_data = data.get('scheduled_data', {})
                    logger.info(f"Đã tải {len(self.scheduled_data)} lịch hẹn giờ")
            else:
                self.scheduled_data = {}
                logger.info("Không tìm thấy file lịch hẹn giờ, tạo mới")
        except Exception as e:
            logger.error(f"Lỗi tải dữ liệu lịch hẹn giờ: {e}")
            self.scheduled_data = {}

    async def restart_scheduled_tasks(self):
        """Khởi động lại các task hẹn giờ khi bot restart"""
        try:
            now = datetime.now()
            restarted_count = 0

            for schedule_id, schedule_info in self.scheduled_data.items():
                # Chỉ khởi động lại các task đang chờ
                if schedule_info.get('status') == 'scheduled':
                    schedule_time = datetime.fromisoformat(schedule_info['schedule_time'])

                    # Nếu thời gian hẹn giờ chưa đến
                    if schedule_time > now:
                        delay_seconds = (schedule_time - now).total_seconds()

                        # Tạo lại task
                        task = asyncio.create_task(
                            self._execute_scheduled_forward(schedule_id, delay_seconds)
                        )
                        self.scheduled_tasks[schedule_id] = task
                        restarted_count += 1

                        logger.info(f"Khởi động lại task hẹn giờ: {schedule_id} vào {schedule_time}")
                    else:
                        # Thời gian đã qua, đánh dấu là thất bại
                        schedule_info['status'] = 'failed'
                        schedule_info['error'] = 'Thời gian hẹn giờ đã qua khi bot restart'
                        schedule_info['failed_at'] = now.isoformat()
                        self._save_scheduled_data()

            logger.info(f"Đã khởi động lại {restarted_count} task hẹn giờ")

        except Exception as e:
            logger.error(f"Lỗi khởi động lại task hẹn giờ: {e}")

    def _save_scheduled_data(self):
        """Lưu dữ liệu lịch hẹn giờ vào file"""
        try:
            data = {
                'scheduled_data': self.scheduled_data,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Đã lưu dữ liệu lịch hẹn giờ")
        except Exception as e:
            logger.error(f"Lỗi lưu dữ liệu lịch hẹn giờ: {e}")

    async def schedule_forward_message(
        self,
        schedule_time: datetime,
        message_data: Dict[str, Any],
        forward_type: str = "all_customers",
        filter_type: Optional[str] = None,
        filter_value: Optional[str] = None,
        admin_id: int = None
    ) -> Dict[str, Any]:
        """
        Lên lịch chuyển tiếp tin nhắn

        Args:
            schedule_time: Thời gian hẹn giờ
            message_data: Dữ liệu tin nhắn cần chuyển tiếp
            forward_type: Loại chuyển tiếp ('all_customers', 'selected_channels', 'bulk_message')
            filter_type: Loại bộ lọc
            filter_value: Giá trị bộ lọc
            admin_id: ID admin tạo lịch hẹn

        Returns:
            Dict chứa kết quả lên lịch
        """
        try:
            # Kiểm tra thời gian hẹn giờ
            now = datetime.now()
            if schedule_time <= now:
                return {
                    'success': False,
                    'message': 'Thời gian hẹn giờ phải lớn hơn thời gian hiện tại'
                }

            # Tạo ID duy nhất cho lịch hẹn
            schedule_id = f"schedule_{int(schedule_time.timestamp())}_{len(self.scheduled_data)}"

            # Lưu dữ liệu lịch hẹn
            schedule_info = {
                'schedule_id': schedule_id,
                'schedule_time': schedule_time.isoformat(),
                'message_data': message_data,
                'forward_type': forward_type,
                'filter_type': filter_type,
                'filter_value': filter_value,
                'admin_id': admin_id,
                'created_at': now.isoformat(),
                'status': 'scheduled'
            }

            self.scheduled_data[schedule_id] = schedule_info
            self._save_scheduled_data()

            # Tính delay và tạo task
            delay_seconds = (schedule_time - now).total_seconds()

            # Tạo task hẹn giờ
            task = asyncio.create_task(
                self._execute_scheduled_forward(schedule_id, delay_seconds)
            )
            self.scheduled_tasks[schedule_id] = task

            logger.info(f"Đã lên lịch chuyển tiếp tin nhắn: {schedule_id} vào {schedule_time}")

            return {
                'success': True,
                'message': f'Đã lên lịch chuyển tiếp tin nhắn vào {schedule_time.strftime("%Y-%m-%d %H:%M:%S")}',
                'schedule_id': schedule_id,
                'schedule_time': schedule_time.strftime("%Y-%m-%d %H:%M:%S"),
                'delay_seconds': delay_seconds
            }

        except Exception as e:
            logger.error(f"Lỗi lên lịch chuyển tiếp: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }

    async def _execute_scheduled_forward(self, schedule_id: str, delay_seconds: float):
        """Thực hiện chuyển tiếp tin nhắn đã hẹn giờ"""
        try:
            # Kiểm tra lại thời gian hẹn giờ trước khi chờ
            if schedule_id not in self.scheduled_data:
                logger.error(f"Không tìm thấy lịch hẹn: {schedule_id}")
                return

            schedule_info = self.scheduled_data[schedule_id]
            schedule_time = datetime.fromisoformat(schedule_info['schedule_time'])
            now = datetime.now()

            # Tính lại delay để đảm bảo chính xác
            actual_delay = (schedule_time - now).total_seconds()

            if actual_delay <= 0:
                logger.warning(f"Thời gian hẹn giờ đã qua: {schedule_time}, thực hiện ngay")
            else:
                logger.info(f"Chờ {actual_delay:.1f} giây đến thời gian hẹn giờ: {schedule_time}")
                # Chờ đến thời gian hẹn giờ
                await asyncio.sleep(actual_delay)

            # Kiểm tra lại sau khi chờ
            if schedule_id not in self.scheduled_data:
                logger.error(f"Lịch hẹn đã bị xóa: {schedule_id}")
                return

            schedule_info = self.scheduled_data[schedule_id]

            # Cập nhật trạng thái
            schedule_info['status'] = 'executing'
            schedule_info['executed_at'] = datetime.now().isoformat()
            self._save_scheduled_data()

            # Thực hiện chuyển tiếp
            result = await self._perform_forward(schedule_info)

            # Cập nhật kết quả
            schedule_info['status'] = 'completed' if result['success'] else 'failed'
            schedule_info['result'] = result
            schedule_info['completed_at'] = datetime.now().isoformat()
            self._save_scheduled_data()

            # Gửi thông báo kết quả cho admin
            if schedule_info.get('admin_id'):
                await self._notify_admin_result(schedule_info['admin_id'], schedule_info, result)

            # Xóa task khỏi danh sách
            if schedule_id in self.scheduled_tasks:
                del self.scheduled_tasks[schedule_id]

            logger.info(f"Hoàn thành chuyển tiếp hẹn giờ: {schedule_id}")

        except asyncio.CancelledError:
            logger.info(f"Task hẹn giờ bị hủy: {schedule_id}")
            if schedule_id in self.scheduled_tasks:
                del self.scheduled_tasks[schedule_id]
        except Exception as e:
            logger.error(f"Lỗi thực hiện chuyển tiếp hẹn giờ {schedule_id}: {e}")

            # Cập nhật trạng thái lỗi
            if schedule_id in self.scheduled_data:
                self.scheduled_data[schedule_id]['status'] = 'failed'
                self.scheduled_data[schedule_id]['error'] = str(e)
                self.scheduled_data[schedule_id]['failed_at'] = datetime.now().isoformat()
                self._save_scheduled_data()

    async def _perform_forward(self, schedule_info: Dict[str, Any]) -> Dict[str, Any]:
        """Thực hiện chuyển tiếp tin nhắn"""
        try:
            message_data = schedule_info['message_data']
            forward_type = schedule_info['forward_type']
            filter_type = schedule_info.get('filter_type')
            filter_value = schedule_info.get('filter_value')

            if forward_type == 'all_customers':
                return await self._forward_to_all_customers(message_data)
            elif forward_type == 'selected_channels':
                return await self._forward_to_selected_channels(message_data, filter_type, filter_value)
            elif forward_type == 'bulk_message':
                return await self._send_bulk_message(message_data, filter_type, filter_value)
            else:
                return {
                    'success': False,
                    'message': f'Loại chuyển tiếp không hỗ trợ: {forward_type}'
                }

        except Exception as e:
            logger.error(f"Lỗi thực hiện chuyển tiếp: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }

    async def _forward_to_all_customers(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Chuyển tiếp tin nhắn đến tất cả khách hàng"""
        try:
            customers = self.sheets_manager.get_all_customers()

            if not customers:
                return {
                    'success': False,
                    'message': 'Không tìm thấy khách hàng nào',
                    'sent_count': 0,
                    'failed_count': 0
                }

            sent_count = 0
            failed_count = 0

            for customer in customers:
                try:
                    customer_user_id = customer.get('user_id')
                    if customer_user_id:
                        # Chuyển tiếp tin nhắn
                        if message_data.get('is_forward'):
                            await self.bot.forward_message(
                                chat_id=int(customer_user_id),
                                from_chat_id=message_data['original_chat_id'],
                                message_id=message_data['original_message_id']
                            )
                        else:
                            # Gửi tin nhắn mới
                            await self.bot.send_message(
                                chat_id=int(customer_user_id),
                                text=message_data.get('text', ''),
                                parse_mode=ParseMode.HTML
                            )

                        sent_count += 1

                        # Cập nhật trạng thái
                        self.sheets_manager.update_customer_message_status(customer_user_id, True)

                        # Ghi log
                        self.sheets_manager.add_message_log(
                            customer_user_id,
                            "Scheduled forward message",
                            'scheduled_forward',
                            'sent'
                        )

                        # Delay để tránh spam
                        await asyncio.sleep(0.5)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Lỗi chuyển tiếp đến user {customer.get('user_id')}: {e}")

            return {
                'success': True,
                'message': f'Đã chuyển tiếp đến {sent_count} khách hàng',
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_customers': len(customers)
            }

        except Exception as e:
            logger.error(f"Lỗi chuyển tiếp đến tất cả khách hàng: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}',
                'sent_count': 0,
                'failed_count': 0
            }

    async def _forward_to_selected_channels(self, message_data: Dict[str, Any],
                                            filter_type: Optional[str],
                                            filter_value: Optional[str]) -> Dict[str, Any]:
        """Chuyển tiếp tin nhắn đến các kênh được chọn"""
        try:
            # Lấy danh sách kênh từ Google Sheets
            channels = self.sheets_manager.get_all_channels()

            if not channels:
                return {
                    'success': False,
                    'message': 'Không tìm thấy kênh nào',
                    'sent_count': 0,
                    'failed_count': 0
                }

            # Lọc kênh theo bộ lọc nếu có
            if filter_type and filter_value:
                filtered_channels = []
                for channel in channels:
                    if filter_type == 'category' and channel.get('category') == filter_value:
                        filtered_channels.append(channel)
                    elif filter_type == 'status' and channel.get('status') == filter_value:
                        filtered_channels.append(channel)
                    elif filter_type == 'type' and channel.get('type') == filter_value:
                        filtered_channels.append(channel)
                channels = filtered_channels

            if not channels:
                return {
                    'success': False,
                    'message': f'Không tìm thấy kênh nào phù hợp với bộ lọc {filter_type}={filter_value}',
                    'sent_count': 0,
                    'failed_count': 0
                }

            sent_count = 0
            failed_count = 0

            for channel in channels:
                try:
                    channel_id = channel.get('channel_id')
                    if channel_id:
                        # Chuyển tiếp tin nhắn đến kênh
                        if message_data.get('is_forward'):
                            await self.bot.forward_message(
                                chat_id=channel_id,
                                from_chat_id=message_data['original_chat_id'],
                                message_id=message_data['original_message_id']
                            )
                        else:
                            # Gửi tin nhắn mới đến kênh
                            if message_data.get('media_file'):
                                # Gửi media
                                if message_data.get('media_type') == 'photo':
                                    await self.bot.send_photo(
                                        chat_id=channel_id,
                                        photo=message_data['media_file'],
                                        caption=message_data.get('text', ''),
                                        parse_mode=ParseMode.HTML
                                    )
                                elif message_data.get('media_type') == 'video':
                                    await self.bot.send_video(
                                        chat_id=channel_id,
                                        video=message_data['media_file'],
                                        caption=message_data.get('text', ''),
                                        parse_mode=ParseMode.HTML
                                    )
                                elif message_data.get('media_type') == 'document':
                                    await self.bot.send_document(
                                        chat_id=channel_id,
                                        document=message_data['media_file'],
                                        caption=message_data.get('text', ''),
                                        parse_mode=ParseMode.HTML
                                    )
                            else:
                                # Gửi tin nhắn text
                                await self.bot.send_message(
                                    chat_id=channel_id,
                                    text=message_data.get('text', ''),
                                    parse_mode=ParseMode.HTML
                                )

                        sent_count += 1

                        # Ghi log chuyển tiếp đến kênh
                        self.sheets_manager.add_channel_log(
                            channel_id,
                            "Scheduled forward message",
                            'scheduled_forward',
                            'sent',
                            message_data.get('text', '')[:100]
                        )

                        # Delay để tránh spam
                        await asyncio.sleep(1.0)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Lỗi chuyển tiếp đến kênh {channel.get('channel_id')}: {e}")

            return {
                'success': True,
                'message': f'Đã chuyển tiếp đến {sent_count} kênh',
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_channels': len(channels)
            }

        except Exception as e:
            logger.error(f"Lỗi chuyển tiếp đến kênh được chọn: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}',
                'sent_count': 0,
                'failed_count': 0
            }

    async def _send_bulk_message(self, message_data: Dict[str, Any],
                                 filter_type: Optional[str],
                                 filter_value: Optional[str]) -> Dict[str, Any]:
        """Gửi tin nhắn hàng loạt"""
        try:
            # Import BulkMessagingManager
            from bulk_messaging import BulkMessagingManager

            bulk_manager = BulkMessagingManager(self.bot, self.sheets_manager)

            # Gửi tin nhắn hàng loạt
            result = await bulk_manager.send_bulk_message(
                message_content=message_data.get('text', ''),
                filter_type=filter_type,
                filter_value=filter_value,
                media_file=message_data.get('media_file'),
                media_type=message_data.get('media_type')
            )

            return result

        except Exception as e:
            logger.error(f"Lỗi gửi tin nhắn hàng loạt: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}',
                'sent_count': 0,
                'failed_count': 0
            }

    async def _notify_admin_result(self, admin_id: int, schedule_info: Dict[str, Any], result: Dict[str, Any]):
        """Thông báo kết quả cho admin"""
        try:
            status_emoji = "✅" if result['success'] else "❌"
            status_text = "thành công" if result['success'] else "thất bại"

            message = (
                f"{status_emoji} <b>Kết quả chuyển tiếp hẹn giờ</b>\n\n"
                f"🕐 <b>Thời gian:</b> {schedule_info['schedule_time']}\n"
                f"📝 <b>Loại:</b> {schedule_info['forward_type']}\n"
                f"📊 <b>Kết quả:</b> {status_text}\n"
                f"📤 <b>Đã gửi:</b> {result.get('sent_count', 0)}\n"
                f"❌ <b>Thất bại:</b> {result.get('failed_count', 0)}\n"
                f"💬 <b>Chi tiết:</b> {result.get('message', 'Không có')}"
            )

            await self.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"Lỗi gửi thông báo kết quả cho admin {admin_id}: {e}")

    def get_scheduled_forwards(self, admin_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách lịch hẹn giờ"""
        try:
            forwards = []

            for schedule_id, schedule_info in self.scheduled_data.items():
                # Lọc theo admin nếu được chỉ định
                if admin_id and schedule_info.get('admin_id') != admin_id:
                    continue

                # Thêm thông tin trạng thái task
                schedule_info['task_running'] = schedule_id in self.scheduled_tasks
                forwards.append(schedule_info)

            # Sắp xếp theo thời gian hẹn giờ
            forwards.sort(key=lambda x: x['schedule_time'])

            return forwards

        except Exception as e:
            logger.error(f"Lỗi lấy danh sách lịch hẹn giờ: {e}")
            return []

    def cancel_scheduled_forward(self, schedule_id: str, admin_id: int) -> Dict[str, Any]:
        """Hủy lịch hẹn giờ"""
        try:
            if schedule_id not in self.scheduled_data:
                return {
                    'success': False,
                    'message': 'Không tìm thấy lịch hẹn giờ'
                }

            schedule_info = self.scheduled_data[schedule_id]

            # Kiểm tra quyền admin
            if schedule_info.get('admin_id') != admin_id:
                return {
                    'success': False,
                    'message': 'Bạn không có quyền hủy lịch hẹn giờ này'
                }

            # Hủy task nếu đang chạy
            if schedule_id in self.scheduled_tasks:
                self.scheduled_tasks[schedule_id].cancel()
                del self.scheduled_tasks[schedule_id]

            # Cập nhật trạng thái
            schedule_info['status'] = 'cancelled'
            schedule_info['cancelled_at'] = datetime.now().isoformat()
            schedule_info['cancelled_by'] = admin_id
            self._save_scheduled_data()

            logger.info(f"Đã hủy lịch hẹn giờ: {schedule_id}")

            return {
                'success': True,
                'message': 'Đã hủy lịch hẹn giờ thành công'
            }

        except Exception as e:
            logger.error(f"Lỗi hủy lịch hẹn giờ: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }

    def get_schedule_stats(self) -> Dict[str, Any]:
        """Lấy thống kê lịch hẹn giờ"""
        try:
            total = len(self.scheduled_data)
            scheduled = len([s for s in self.scheduled_data.values() if s['status'] == 'scheduled'])
            completed = len([s for s in self.scheduled_data.values() if s['status'] == 'completed'])
            failed = len([s for s in self.scheduled_data.values() if s['status'] == 'failed'])
            cancelled = len([s for s in self.scheduled_data.values() if s['status'] == 'cancelled'])
            running = len(self.scheduled_tasks)

            return {
                'total': total,
                'scheduled': scheduled,
                'completed': completed,
                'failed': failed,
                'cancelled': cancelled,
                'running': running
            }

        except Exception as e:
            logger.error(f"Lỗi lấy thống kê lịch hẹn giờ: {e}")
            return {
                'total': 0,
                'scheduled': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0,
                'running': 0
            }

    async def cleanup_old_schedules(self, days_old: int = 30):
        """Dọn dẹp các lịch hẹn giờ cũ"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_count = 0

            schedule_ids_to_remove = []

            for schedule_id, schedule_info in self.scheduled_data.items():
                # Chỉ xóa các lịch đã hoàn thành hoặc thất bại
                if schedule_info['status'] in ['completed', 'failed', 'cancelled']:
                    schedule_time = datetime.fromisoformat(schedule_info['schedule_time'])
                    if schedule_time < cutoff_date:
                        schedule_ids_to_remove.append(schedule_id)

            # Xóa các lịch cũ
            for schedule_id in schedule_ids_to_remove:
                del self.scheduled_data[schedule_id]
                removed_count += 1

            if removed_count > 0:
                self._save_scheduled_data()
                logger.info(f"Đã dọn dẹp {removed_count} lịch hẹn giờ cũ")

            return removed_count

        except Exception as e:
            logger.error(f"Lỗi dọn dẹp lịch hẹn giờ cũ: {e}")
            return 0


# Hàm helper để sử dụng dễ dàng
async def schedule_forward_message(
    schedule_time: datetime,
    message_data: Dict[str, Any],
    forward_type: str = "all_customers",
    filter_type: Optional[str] = None,
    filter_value: Optional[str] = None,
    admin_id: int = None
) -> Dict[str, Any]:
    """Lên lịch chuyển tiếp tin nhắn"""
    from bot_config import TELEGRAM_TOKEN
    bot = Bot(token=TELEGRAM_TOKEN)
    sheets_manager = GoogleSheetsManager()
    manager = ScheduledForwardManager(bot, sheets_manager)
    return await manager.schedule_forward_message(
        schedule_time, message_data, forward_type, filter_type, filter_value, admin_id
    ) 
