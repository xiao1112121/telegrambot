import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import os

logger = logging.getLogger(__name__)


class ScheduledForwardManager:
    def __init__(self, bot, sheets_manager):
        self.bot = bot
        self.sheets_manager = sheets_manager
        self.scheduled_data_file = "scheduled_forwards.json"
        self.scheduled_tasks = {}
        self._load_scheduled_data()

    def _load_scheduled_data(self):
        """Tải dữ liệu lịch hẹn giờ từ file"""
        try:
            if os.path.exists(self.scheduled_data_file):
                with open(self.scheduled_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Xử lý format cũ với nested structure
                    if 'scheduled_data' in data:
                        scheduled_data = data['scheduled_data']
                        logger.info(f"Đã tải {len(scheduled_data)} lịch hẹn giờ")
                        return scheduled_data
                    else:
                        logger.info(f"Đã tải {len(data)} lịch hẹn giờ")
                        return data
        except Exception as e:
            logger.error(f"Lỗi tải dữ liệu lịch hẹn giờ: {e}")
        return {}

    def _save_scheduled_data(self, data):
        """Lưu dữ liệu lịch hẹn giờ vào file"""
        try:
            # Lưu với format mới đơn giản
            with open(self.scheduled_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi lưu dữ liệu lịch hẹn giờ: {e}")

    def schedule_forward_message(self, message_data: Dict, schedule_time: datetime,
                                 target_type: str = "channels", target_ids: List[str] = None) -> str:
        """Lên lịch chuyển tiếp tin nhắn"""
        try:
            # Tạo ID duy nhất cho lịch hẹn giờ
            schedule_id = f"schedule_{int(schedule_time.timestamp())}_{len(self.scheduled_tasks) + 1}"

            # Tính toán thời gian chờ
            now = datetime.now()
            delay_seconds = (schedule_time - now).total_seconds()

            if delay_seconds <= 0:
                return "❌ Thời gian hẹn giờ phải trong tương lai!"

            # Lưu thông tin lịch hẹn giờ
            schedule_info = {
                "id": schedule_id,
                "message_data": message_data,
                "schedule_time": schedule_time.isoformat(),
                "target_type": target_type,
                "target_ids": target_ids or [],
                "created_at": now.isoformat()
            }

            # Lưu vào file
            data = self._load_scheduled_data()
            data[schedule_id] = schedule_info
            self._save_scheduled_data(data)

            # Tạo task chạy trong background
            task = asyncio.create_task(self._execute_scheduled_forward(schedule_id, delay_seconds))
            self.scheduled_tasks[schedule_id] = task

            logger.info(f"Đã lên lịch chuyển tiếp: {schedule_id} vào {schedule_time}")
            return f"✅ Đã lên lịch chuyển tiếp tin nhắn vào {schedule_time.strftime('%d/%m/%Y %H:%M')}"

        except Exception as e:
            logger.error(f"Lỗi lên lịch chuyển tiếp: {e}")
            return f"❌ Lỗi lên lịch chuyển tiếp: {e}"

    async def _execute_scheduled_forward(self, schedule_id: str, delay_seconds: float):
        """Thực hiện chuyển tiếp tin nhắn theo lịch hẹn giờ"""
        try:
            # Chờ đến thời gian hẹn giờ
            await asyncio.sleep(delay_seconds)

            # Tải lại dữ liệu để đảm bảo tính chính xác
            data = self._load_scheduled_data()
            if schedule_id not in data:
                logger.warning(f"Không tìm thấy lịch hẹn giờ: {schedule_id}")
                return

            schedule_info = data[schedule_id]
            message_data = schedule_info["message_data"]
            target_type = schedule_info["target_type"]
            target_ids = schedule_info["target_ids"]

            # Thực hiện chuyển tiếp
            await self._perform_forward(message_data, target_type, target_ids)

            # Xóa lịch hẹn giờ đã hoàn thành
            del data[schedule_id]
            self._save_scheduled_data(data)

            # Xóa task
            if schedule_id in self.scheduled_tasks:
                del self.scheduled_tasks[schedule_id]

            logger.info(f"Đã hoàn thành chuyển tiếp theo lịch hẹn giờ: {schedule_id}")

        except asyncio.CancelledError:
            logger.info(f"Task chuyển tiếp bị hủy: {schedule_id}")
        except Exception as e:
            logger.error(f"Lỗi thực hiện chuyển tiếp theo lịch hẹn giờ {schedule_id}: {e}")

    async def _perform_forward(self, message_data: Dict, target_type: str, target_ids: List[str]):
        """Thực hiện chuyển tiếp tin nhắn"""
        try:
            if target_type == "channels":
                await self._forward_to_selected_channels(message_data, target_ids)
            else:
                await self._forward_to_all_customers(message_data)

        except Exception as e:
            logger.error(f"Lỗi thực hiện chuyển tiếp: {e}")

    async def _forward_to_selected_channels(self, message_data: Dict, target_ids: List[str]):
        """Chuyển tiếp đến các kênh được chọn"""
        try:
            # Lấy danh sách kênh từ Google Sheets
            channels = self.sheets_manager.get_all_channels()

            if not channels:
                logger.warning("Không tìm thấy kênh nào trong Google Sheets")
                return

            # Lọc kênh theo target_ids nếu có
            if target_ids:
                channels = [ch for ch in channels if ch.get('id') in target_ids]

            success_count = 0
            error_count = 0

            for channel in channels:
                try:
                    channel_id = channel.get('id')
                    if not channel_id:
                        continue

                    # Chuyển tiếp tin nhắn theo loại
                    if message_data.get('type') == 'photo':
                        await self.bot.send_photo(
                            chat_id=channel_id,
                            photo=message_data['photo'],
                            caption=message_data.get('caption', ''),
                            parse_mode='HTML'
                        )
                    elif message_data.get('type') == 'video':
                        await self.bot.send_video(
                            chat_id=channel_id,
                            video=message_data['video'],
                            caption=message_data.get('caption', ''),
                            parse_mode='HTML'
                        )
                    elif message_data.get('type') == 'document':
                        await self.bot.send_document(
                            chat_id=channel_id,
                            document=message_data['document'],
                            caption=message_data.get('caption', ''),
                            parse_mode='HTML'
                        )
                    else:
                        # Tin nhắn văn bản
                        await self.bot.forward_message(
                            chat_id=channel_id,
                            from_chat_id=message_data['from_chat_id'],
                            message_id=message_data['message_id']
                        )

                    success_count += 1
                    logger.info(f"Đã chuyển tiếp đến kênh {channel_id}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"Lỗi chuyển tiếp đến kênh {channel.get('id', 'unknown')}: {e}")

            # Thông báo kết quả cho admin
            await self._notify_admin_result(success_count, error_count, len(channels))

        except Exception as e:
            logger.error(f"Lỗi chuyển tiếp đến kênh: {e}")

    async def _forward_to_all_customers(self, message_data: Dict):
        """Chuyển tiếp đến tất cả khách hàng"""
        try:
            customers = self.sheets_manager.get_all_customers()
            success_count = 0
            error_count = 0

            for customer in customers:
                try:
                    customer_id = customer.get('telegram_id')
                    if not customer_id:
                        continue

                    await self.bot.forward_message(
                        chat_id=customer_id,
                        from_chat_id=message_data['from_chat_id'],
                        message_id=message_data['message_id']
                    )

                    success_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f"Lỗi chuyển tiếp đến khách hàng {customer.get('telegram_id', 'unknown')}: {e}")

            # Thông báo kết quả cho admin
            await self._notify_admin_result(success_count, error_count, len(customers))

        except Exception as e:
            logger.error(f"Lỗi chuyển tiếp đến khách hàng: {e}")

    async def _notify_admin_result(self, success_count: int, error_count: int, total_count: int):
        """Thông báo kết quả chuyển tiếp cho admin"""
        try:
            from bot_config import ADMIN_USER_IDS

            result_message = "📊 Kết quả chuyển tiếp tin nhắn:\n"
            result_message += f"✅ Thành công: {success_count}\n"
            result_message += f"❌ Lỗi: {error_count}\n"
            result_message += f"📈 Tổng số: {total_count}"

            for admin_id in ADMIN_USER_IDS:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=result_message
                    )
                except Exception as e:
                    logger.error(f"Lỗi gửi thông báo kết quả cho admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Lỗi thông báo kết quả: {e}")

    def get_scheduled_forwards(self) -> List[Dict]:
        """Lấy danh sách lịch hẹn giờ chuyển tiếp"""
        try:
            data = self._load_scheduled_data()
            forwards = []

            for schedule_id, info in data.items():
                schedule_time = datetime.fromisoformat(info['schedule_time'])
                forwards.append({
                    'id': schedule_id,
                    'schedule_time': schedule_time,
                    'target_type': info['target_type'],
                    'target_ids': info['target_ids'],
                    'created_at': datetime.fromisoformat(info['created_at'])
                })

            # Sắp xếp theo thời gian hẹn giờ
            forwards.sort(key=lambda x: x['schedule_time'])
            return forwards

        except Exception as e:
            logger.error(f"Lỗi lấy danh sách lịch hẹn giờ: {e}")
            return []

    def cancel_scheduled_forward(self, schedule_id: str) -> bool:
        """Hủy lịch hẹn giờ chuyển tiếp"""
        try:
            # Hủy task nếu đang chạy
            if schedule_id in self.scheduled_tasks:
                self.scheduled_tasks[schedule_id].cancel()
                del self.scheduled_tasks[schedule_id]

            # Xóa khỏi file
            data = self._load_scheduled_data()
            if schedule_id in data:
                del data[schedule_id]
                self._save_scheduled_data(data)
                logger.info(f"Đã hủy lịch hẹn giờ: {schedule_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Lỗi hủy lịch hẹn giờ {schedule_id}: {e}")
            return False

    def get_schedule_stats(self) -> Dict[str, int]:
        """Lấy thống kê lịch hẹn giờ"""
        try:
            data = self._load_scheduled_data()
            now = datetime.now()

            stats = {
                'total': len(data),
                'pending': 0,
                'today': 0,
                'tomorrow': 0
            }

            for schedule_id, info in data.items():
                schedule_time = datetime.fromisoformat(info['schedule_time'])

                if schedule_time > now:
                    stats['pending'] += 1

                if schedule_time.date() == now.date():
                    stats['today'] += 1
                elif schedule_time.date() == (now + timedelta(days=1)).date():
                    stats['tomorrow'] += 1

            return stats

        except Exception as e:
            logger.error(f"Lỗi lấy thống kê lịch hẹn giờ: {e}")
            return {'total': 0, 'pending': 0, 'today': 0, 'tomorrow': 0}

    def cleanup_old_schedules(self):
        """Dọn dẹp các lịch hẹn giờ cũ"""
        try:
            data = self._load_scheduled_data()
            now = datetime.now()
            cleaned_count = 0

            # Xóa các lịch hẹn giờ đã qua quá 7 ngày
            cutoff_time = now - timedelta(days=7)

            for schedule_id, info in list(data.items()):
                schedule_time = datetime.fromisoformat(info['schedule_time'])
                if schedule_time < cutoff_time:
                    del data[schedule_id]
                    cleaned_count += 1

            if cleaned_count > 0:
                self._save_scheduled_data(data)
                logger.info(f"Đã dọn dẹp {cleaned_count} lịch hẹn giờ cũ")

        except Exception as e:
            logger.error(f"Lỗi dọn dẹp lịch hẹn giờ cũ: {e}")

    async def restart_scheduled_tasks(self):
        """Khởi động lại các task hẹn giờ sau khi restart bot"""
        try:
            logger.info("⏰ Khởi động lại các task hẹn giờ chuyển tiếp...")
            data = self._load_scheduled_data()
            now = datetime.now()
            restarted_count = 0

            for schedule_id, info in data.items():
                try:
                    # Xử lý format cũ và mới
                    if 'schedule_time' in info:
                        schedule_time = datetime.fromisoformat(info['schedule_time'])
                    else:
                        logger.warning(f"Không tìm thấy schedule_time trong {schedule_id}")
                        continue

                    # Chỉ khởi động lại các task chưa đến thời gian và có status scheduled
                    if schedule_time > now and info.get('status') == 'scheduled':
                        delay_seconds = (schedule_time - now).total_seconds()

                        # Tạo lại task
                        task = asyncio.create_task(self._execute_scheduled_forward(schedule_id, delay_seconds))
                        self.scheduled_tasks[schedule_id] = task

                        logger.info(f"Khởi động lại task hẹn giờ: {schedule_id} vào {schedule_time}")
                        restarted_count += 1
                    else:
                        logger.info(f"Bỏ qua task {schedule_id}: thời gian đã qua hoặc status không phải scheduled")

                except Exception as e:
                    logger.error(f"Lỗi xử lý task {schedule_id}: {e}")

            logger.info(f"Đã khởi động lại {restarted_count} task hẹn giờ")

        except Exception as e:
            logger.error(f"Lỗi khởi động lại task hẹn giờ: {e}")