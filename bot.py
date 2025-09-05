#!/usr/bin/env python3
"""
ABCDBET Customer Service Bot - Bot de atendimento ao cliente
"""

import logging
import sys
import importlib
import signal
from datetime import datetime
from typing import Optional
from telegram import (  # pyright: ignore[reportMissingImports]
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, Bot, BotCommandScopeChat
)
from telegram.constants import ParseMode
from telegram.ext import (  # pyright: ignore[reportMissingImports]
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
import bot_config

from google_sheets import GoogleSheetsManager
from customer_data_manager import customer_manager
from notification_system import (
    init_notification_system, get_notification_manager
)
from bulk_messaging import BulkMessagingManager
from scheduled_forward import ScheduledForwardManager
# from form_builder import get_form_builder
# from ecosystem_integration import (
#     init_ecosystem_integration, get_ecosystem_manager
# )

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializar managers
sheets_manager = GoogleSheetsManager()
# Khởi tạo bot và bulk messaging manager
bot = Bot(token=bot_config.TELEGRAM_TOKEN)
bulk_messaging_manager = BulkMessagingManager(bot, sheets_manager)
scheduled_forward_manager = ScheduledForwardManager(bot, sheets_manager)
# form_builder = get_form_builder()

# Armazenamento temporário de dados
user_data = {}

# Biến global để lưu trữ application
current_application = None

# Biến global để lưu trữ kênh được chọn cho từng admin
admin_selected_channels = {}

# Biến global để lưu trữ trạng thái chọn kênh
channel_selection_state = {}


def get_admin_selected_channels(user_id: int) -> list:
    """Lấy danh sách kênh được chọn của admin"""
    return admin_selected_channels.get(str(user_id), [])


def set_admin_selected_channels(user_id: int, channels: list):
    """Đặt danh sách kênh được chọn cho admin"""
    admin_selected_channels[str(user_id)] = channels


def toggle_channel_selection(user_id: int, channel_id: str):
    """Chuyển đổi trạng thái chọn kênh"""
    current_channels = get_admin_selected_channels(user_id)

    if channel_id in current_channels:
        current_channels.remove(channel_id)
    else:
        current_channels.append(channel_id)

    set_admin_selected_channels(user_id, current_channels)
    return current_channels


def select_all_channels(user_id: int):
    """Chọn tất cả kênh"""
    all_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
    set_admin_selected_channels(user_id, all_channels.copy())
    return all_channels


def deselect_all_channels(user_id: int):
    """Bỏ chọn tất cả kênh"""
    set_admin_selected_channels(user_id, [])
    return []


def create_channel_selection_keyboard(user_id: int):
    """Tạo keyboard chọn kênh"""
    all_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
    selected_channels = get_admin_selected_channels(user_id)

    if not all_channels:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Không có kênh nào", callback_data="no_channels")
        ]])

    keyboard = []

    # Hiển thị thống kê
    stats_text = f"📊 **Đã chọn: {len(selected_channels)}/{len(all_channels)} kênh**"
    keyboard.append([InlineKeyboardButton(stats_text, callback_data="stats_info")])

    # Nút chọn tất cả / bỏ chọn tất cả
    if len(selected_channels) == len(all_channels):
        keyboard.append([InlineKeyboardButton(
            "🔴 Bỏ chọn tất cả",
            callback_data="deselect_all_channels"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            "🟢 Chọn tất cả",
            callback_data="select_all_channels"
        )])

    # Danh sách từng kênh
    for channel_id in all_channels:
        is_selected = channel_id in selected_channels
        status_icon = "✅" if is_selected else "❌"

        # Hiển thị tên kênh ngắn gọn
        if channel_id.startswith('-100'):
            display_name = f"📢 Kênh {channel_id[-8:]}"
        elif channel_id.startswith('@'):
            display_name = f"📢 {channel_id}"
        else:
            display_name = f"📢 {channel_id}"

        keyboard.append([InlineKeyboardButton(
            f"{status_icon} {display_name}",
            callback_data=f"toggle_channel:{channel_id}"
        )])

    # Nút xác nhận và hủy
    if selected_channels:
        keyboard.append([InlineKeyboardButton(
            "✅ Xác nhận gửi",
            callback_data="confirm_send_to_channels"
        )])

    keyboard.append([InlineKeyboardButton(
        "❌ Hủy",
        callback_data="cancel_channel_selection"
    )])

    return InlineKeyboardMarkup(keyboard)


def reload_bot_modules():
    """Tự động reload các modules của bot"""
    try:
        # Reload bot_config
        importlib.reload(bot_config)
        print("✅ Reloaded bot_config")

        # Reload các modules khác nếu cần
        try:
            importlib.reload(sys.modules['google_sheets'])
            print("✅ Reloaded google_sheets")
        except Exception:
            pass

        try:
            importlib.reload(sys.modules['notification_system'])
            print("✅ Reloaded notification_system")
        except Exception:
            pass

        try:
            importlib.reload(sys.modules['bulk_messaging'])
            print("✅ Reloaded bulk_messaging")
        except Exception:
            pass

        return True
    except Exception as e:
        print(f"❌ Error reloading modules: {e}")
        return False


def graceful_restart(signum=None, frame=None):
    """Restart bot gracefully"""
    global current_application  # noqa: F824

    print("🔄 Starting graceful restart...")

    try:
        # Reload modules
        if reload_bot_modules():
            print("✅ Modules reloaded successfully")

            # Stop current application
            if current_application:
                print("🛑 Stopping current application...")
                current_application.stop()

            # Start new application
            print("🚀 Starting new application...")
            main()

        else:
            print("❌ Failed to reload modules, keeping current version")

    except Exception as e:
        print(f"❌ Error during restart: {e}")


def setup_signal_handlers():
    """Setup signal handlers for graceful restart"""
    if sys.platform != "win32":
        signal.signal(signal.SIGUSR1, graceful_restart)


def get_bulk_messaging_menu_keyboard(language='pt'):
    """Tạo keyboard cho menu bulk messaging theo ngôn ngữ"""
    if language == 'zh':
        # Tiếng Trung giản thể
        return [
            [InlineKeyboardButton('📢 发送消息给所有人', callback_data='bulk_all'),
             InlineKeyboardButton('📢 转发到频道', callback_data='bulk_forward_to_channel')],
            [InlineKeyboardButton('⚙️ 管理频道', callback_data='manage_channels'),
             InlineKeyboardButton('🎯 按筛选条件发送消息', callback_data='bulk_filter')],
            [InlineKeyboardButton('📅 安排发送消息', callback_data='bulk_schedule'),
             InlineKeyboardButton('⏰ 定时转发', callback_data='scheduled_forward')],
            [InlineKeyboardButton('📊 客户统计', callback_data='bulk_stats')],
            [InlineKeyboardButton('🛑 停止发送消息', callback_data='bulk_stop'),
             InlineKeyboardButton('🌐 更改语言', callback_data='bulk_language')]
        ]
    elif language == 'en':
        # Tiếng Anh
        return [
            [InlineKeyboardButton('📢 Send message to all', callback_data='bulk_all'),
             InlineKeyboardButton('📢 Forward to channel', callback_data='bulk_forward_to_channel')],
            [InlineKeyboardButton('⚙️ Manage channels', callback_data='manage_channels'),
             InlineKeyboardButton('🎯 Send message by filter', callback_data='bulk_filter')],
            [InlineKeyboardButton('📅 Schedule message', callback_data='bulk_schedule'),
             InlineKeyboardButton('⏰ Schedule forward', callback_data='scheduled_forward')],
            [InlineKeyboardButton('📊 Customer statistics', callback_data='bulk_stats')],
            [InlineKeyboardButton('🛑 Stop sending messages', callback_data='bulk_stop'),
             InlineKeyboardButton('🌐 Change language', callback_data='bulk_language')]
        ]
    elif language == 'vi':
        # Tiếng Việt
        return [
            [InlineKeyboardButton('📢 Gửi tin nhắn đến tất cả', callback_data='bulk_all'),
             InlineKeyboardButton('📢 Chuyển tiếp đến kênh', callback_data='bulk_forward_to_channel')],
            [InlineKeyboardButton('⚙️ Quản lý kênh', callback_data='manage_channels'),
             InlineKeyboardButton('🎯 Gửi tin nhắn theo bộ lọc', callback_data='bulk_filter')],
            [InlineKeyboardButton('📅 Lên lịch gửi tin nhắn', callback_data='bulk_schedule'),
             InlineKeyboardButton('⏰ Hẹn giờ chuyển tiếp', callback_data='scheduled_forward')],
            [InlineKeyboardButton('📊 Thống kê khách hàng', callback_data='bulk_stats')],
            [InlineKeyboardButton('🛑 Dừng gửi tin nhắn', callback_data='bulk_stop'),
             InlineKeyboardButton('🌐 Thay đổi ngôn ngữ', callback_data='bulk_language')]
        ]
    else:
        # Tiếng Bồ Đào Nha (mặc định)
        return [
            [InlineKeyboardButton('📢 Enviar mensagem para todos', callback_data='bulk_all'),
             InlineKeyboardButton('📢 Encaminhar para canal', callback_data='bulk_forward_to_channel')],
            [InlineKeyboardButton('⚙️ Gerenciar canais', callback_data='manage_channels'),
             InlineKeyboardButton('🎯 Enviar mensagem por filtro', callback_data='bulk_filter')],
            [InlineKeyboardButton('📅 Agendar mensagem', callback_data='bulk_schedule'),
             InlineKeyboardButton('⏰ Agendar encaminhamento', callback_data='scheduled_forward')],
            [InlineKeyboardButton('📊 Estatísticas de clientes', callback_data='bulk_stats')],
            [InlineKeyboardButton('🛑 Parar envio de mensagens', callback_data='bulk_stop'),
             InlineKeyboardButton('🌐 Alterar idioma', callback_data='bulk_language')]
        ]


def get_bulk_messaging_title(language='pt'):
    """Lấy tiêu đề menu bulk messaging theo ngôn ngữ"""
    if language == 'zh':
        return '📢 **批量消息系统**\n\n请选择您要使用的功能:'
    elif language == 'en':
        return '📢 **BULK MESSAGING SYSTEM**\n\nSelect the function you want to use:'
    elif language == 'vi':
        return '📢 **HỆ THỐNG GỬI TIN NHẮN HÀNG LOẠT**\n\nChọn chức năng bạn muốn sử dụng:'
    else:
        return '📢 **SISTEMA DE MENSAGENS EM MASSA**\n\nSelecione a função que deseja usar:'


def get_scheduled_forward_menu_keyboard(language='pt'):
    """Tạo keyboard cho menu hẹn giờ chuyển tiếp theo ngôn ngữ"""
    if language == 'zh':
        return [
            [InlineKeyboardButton('⏰ 设置定时转发', callback_data='schedule_forward_set'),
             InlineKeyboardButton('📋 查看定时任务', callback_data='schedule_forward_list')],
            [InlineKeyboardButton('❌ 取消定时任务', callback_data='schedule_forward_cancel'),
             InlineKeyboardButton('📊 定时任务统计', callback_data='schedule_forward_stats')],
            [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
        ]
    elif language == 'en':
        return [
            [InlineKeyboardButton('⏰ Set scheduled forward', callback_data='schedule_forward_set'),
             InlineKeyboardButton('📋 View scheduled tasks', callback_data='schedule_forward_list')],
            [InlineKeyboardButton('❌ Cancel scheduled task', callback_data='schedule_forward_cancel'),
             InlineKeyboardButton('📊 Scheduled task stats', callback_data='schedule_forward_stats')],
            [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
        ]
    elif language == 'vi':
        return [
            [InlineKeyboardButton('⏰ Thiết lập hẹn giờ chuyển tiếp', callback_data='schedule_forward_set'),
             InlineKeyboardButton('📋 Xem lịch hẹn giờ', callback_data='schedule_forward_list')],
            [InlineKeyboardButton('❌ Hủy lịch hẹn giờ', callback_data='schedule_forward_cancel'),
             InlineKeyboardButton('📊 Thống kê lịch hẹn giờ', callback_data='schedule_forward_stats')],
            [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
        ]
    else:
        return [
            [InlineKeyboardButton('⏰ Configurar encaminhamento agendado', callback_data='schedule_forward_set'),
             InlineKeyboardButton('📋 Ver tarefas agendadas', callback_data='schedule_forward_list')],
            [InlineKeyboardButton('❌ Cancelar tarefa agendada', callback_data='schedule_forward_cancel'),
             InlineKeyboardButton('📊 Estatísticas de tarefas agendadas', callback_data='schedule_forward_stats')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='bulk_back')]
        ]


def get_scheduled_forward_title(language='pt'):
    """Lấy tiêu đề menu hẹn giờ chuyển tiếp theo ngôn ngữ"""
    if language == 'zh':
        return '⏰ **定时转发系统**\n\n请选择您要使用的功能:'
    elif language == 'en':
        return '⏰ **SCHEDULED FORWARD SYSTEM**\n\nSelect the function you want to use:'
    elif language == 'vi':
        return '⏰ **HỆ THỐNG HẸN GIỜ CHUYỂN TIẾP**\n\nChọn chức năng bạn muốn sử dụng:'
    else:
        return '⏰ **SISTEMA DE ENCAMINHAMENTO AGENDADO**\n\nSelecione a função que deseja usar:'


async def update_admin_commands_for_user(context, language):
    """Cập nhật admin commands cho user theo ngôn ngữ mới"""
    try:
        user_id = context.user_data.get('user_id') or context.effective_user.id

        # Kiểm tra xem user có phải admin không
        if str(user_id) in bot_config.ADMIN_USER_IDS:
            # Lấy admin commands theo ngôn ngữ mới
            admin_commands = get_admin_commands(language)

            # Cập nhật commands cho user này
            await context.bot.set_my_commands(
                [BotCommand(command, description) for command, description in admin_commands],
                scope=BotCommandScopeChat(chat_id=int(user_id))
            )

            logger.info(f"✅ Đã cập nhật admin commands cho user {user_id} sang ngôn ngữ {language}")
        else:
            logger.info(f"User {user_id} không phải admin, không cần cập nhật commands")

    except Exception as e:
        logger.error(f"❌ Lỗi khi cập nhật admin commands: {e}")
        print(f"❌ Lỗi khi cập nhật admin commands: {e}")


def get_admin_commands(language='pt'):
    """Lấy danh sách lệnh admin theo ngôn ngữ"""
    if language == 'zh':
        return [
            ('bulk', '📢 发送消息给所有人 (Admin)'),
            ('manage_channels', '⚙️ 管理频道 (Admin)'),
            ('stats', '📊 客户统计 (Admin)'),
            ('stop_bulk', '🛑 停止发送消息 (Admin)'),
            ('scheduled_forward', '⏰ 定时转发 (Admin)')
        ]
    elif language == 'en':
        return [
            ('bulk', '📢 Send bulk messages (Admin)'),
            ('manage_channels', '⚙️ Manage channels (Admin)'),
            ('stats', '📊 Customer statistics (Admin)'),
            ('stop_bulk', '🛑 Stop sending messages (Admin)'),
            ('scheduled_forward', '⏰ Schedule forward (Admin)')
        ]
    elif language == 'vi':
        return [
            ('bulk', '📢 Gửi tin nhắn hàng loạt (Admin)'),
            ('manage_channels', '⚙️ Quản lý kênh (Admin)'),
            ('stats', '📊 Thống kê khách hàng (Admin)'),
            ('stop_bulk', '🛑 Dừng gửi tin nhắn (Admin)'),
            ('scheduled_forward', '⏰ Hẹn giờ chuyển tiếp (Admin)')
        ]
    else:
        # Tiếng Bồ Đào Nha (mặc định)
        return [
            ('bulk', '📢 Enviar mensagens em massa (Admin)'),
            ('manage_channels', '⚙️ Gerenciar canais (Admin)'),
            ('stats', '📊 Estatísticas de clientes (Admin)'),
            ('stop_bulk', '🛑 Parar envio de mensagens (Admin)'),
            ('scheduled_forward', '⏰ Agendar encaminhamento (Admin)')
        ]


def get_bulk_all_title(language='pt'):
    """Lấy tiêu đề menu gửi tin nhắn đến tất cả theo ngôn ngữ"""
    if language == 'zh':
        return '📢 **发送消息给所有客户**\n\n选择输入消息的方式:'
    elif language == 'en':
        return '📢 **SEND MESSAGE TO ALL CUSTOMERS**\n\nSelect how to input message:'
    elif language == 'vi':
        return '📢 **GỬI TIN NHẮN ĐẾN TẤT CẢ KHÁCH HÀNG**\n\nChọn cách nhập tin nhắn:'
    else:
        return '📢 **ENVIAR MENSAGEM PARA TODOS OS CLIENTES**\n\nSelecione como inserir a mensagem:'


def get_bulk_filter_title(language='pt'):
    """Lấy tiêu đề menu gửi tin nhắn theo bộ lọc theo ngôn ngữ"""
    if language == 'zh':
        return '🎯 **按筛选条件发送消息**\n\n选择筛选类型:'
    elif language == 'en':
        return '🎯 **SEND MESSAGE BY FILTER**\n\nSelect filter type:'
    elif language == 'vi':
        return '🎯 **GỬI TIN NHẮN THEO BỘ LỌC**\n\nChọn loại bộ lọc:'
    else:
        return '🎯 **ENVIAR MENSAGEM POR FILTRO**\n\nSelecione o tipo de filtro:'


def get_bulk_schedule_title(language='pt'):
    """Lấy tiêu đề menu lên lịch gửi tin nhắn theo ngôn ngữ"""
    if language == 'zh':
        return '📅 **安排发送消息**\n\n此功能将在下一版本中开发。\n\n请使用即时发送消息功能。'
    elif language == 'en':
        return '📅 **SCHEDULE MESSAGE**\n\nThis feature will be developed in the next version.\n\nPlease use the instant message sending feature.'
    elif language == 'vi':
        return '📅 **LÊN LỊCH GỬI TIN NHẮN**\n\nTính năng này sẽ được phát triển trong phiên bản tiếp theo.\n\nVui lòng sử dụng tính năng gửi tin nhắn ngay lập tức.'
    else:
        return '📅 **AGENDAR MENSAGEM**\n\nEste recurso será desenvolvido na próxima versão.\n\nPor favor, use o recurso de envio de mensagem instantânea.'


def get_bulk_templates_title(language='vi'):
    """Lấy tiêu đề menu template tin nhắn theo ngôn ngữ"""
    if language == 'zh':
        return '📋 **消息模板**\n\n'
    elif language == 'en':
        return '📋 **MESSAGE TEMPLATES**\n\n'
    else:
        return '📋 **TEMPLATE TIN NHẮN MẪU**\n\n'


def get_bulk_stats_title(language='pt'):
    """Lấy tiêu đề menu thống kê theo ngôn ngữ"""
    if language == 'zh':
        return '📊 **客户统计**\n\n'
    elif language == 'en':
        return '📊 **CUSTOMER STATISTICS**\n\n'
    elif language == 'vi':
        return '📊 **THỐNG KÊ KHÁCH HÀNG**\n\n'
    else:
        return '📊 **ESTATÍSTICAS DE CLIENTES**\n\n'


def get_bulk_all_keyboard(language='pt'):
    """Tạo keyboard cho menu gửi tin nhắn đến tất cả theo ngôn ngữ"""
    if language == 'zh':
        return [
            [InlineKeyboardButton('📝 输入消息', callback_data='bulk_input_message')],
            [InlineKeyboardButton('📋 使用模板', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
        ]
    elif language == 'en':
        return [
            [InlineKeyboardButton('📝 Input message', callback_data='bulk_input_message')],
            [InlineKeyboardButton('📋 Use template', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
        ]
    elif language == 'vi':
        return [
            [InlineKeyboardButton('📝 Nhập tin nhắn', callback_data='bulk_input_message')],
            [InlineKeyboardButton('📋 Sử dụng template', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
        ]
    else:
        return [
            [InlineKeyboardButton('📝 Inserir mensagem', callback_data='bulk_input_message')],
            [InlineKeyboardButton('📋 Usar template', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='bulk_back')]
        ]


def get_bulk_filter_keyboard(language='pt'):
    """Tạo keyboard cho menu gửi tin nhắn theo bộ lọc theo ngôn ngữ"""
    if language == 'zh':
        return [
            [InlineKeyboardButton('📅 按日期', callback_data='bulk_filter_date')],
            [InlineKeyboardButton('🎯 按操作', callback_data='bulk_filter_action')],
            [InlineKeyboardButton('👤 按用户名', callback_data='bulk_filter_username')],
            [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
        ]
    elif language == 'en':
        return [
            [InlineKeyboardButton('📅 By date', callback_data='bulk_filter_date')],
            [InlineKeyboardButton('🎯 By action', callback_data='bulk_filter_action')],
            [InlineKeyboardButton('👤 By username', callback_data='bulk_filter_username')],
            [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
        ]
    elif language == 'vi':
        return [
            [InlineKeyboardButton('📅 Theo ngày', callback_data='bulk_filter_date')],
            [InlineKeyboardButton('🎯 Theo hành động', callback_data='bulk_filter_action')],
            [InlineKeyboardButton('👤 Theo username', callback_data='bulk_filter_username')],
            [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
        ]
    else:
        return [
            [InlineKeyboardButton('📅 Por data', callback_data='bulk_filter_date')],
            [InlineKeyboardButton('🎯 Por ação', callback_data='bulk_filter_action')],
            [InlineKeyboardButton('👤 Por nome de usuário', callback_data='bulk_filter_username')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='bulk_back')]
        ]


def get_bulk_templates_keyboard(language='vi'):
    """Tạo keyboard cho menu template tin nhắn theo ngôn ngữ"""
    if language == 'zh':
        return [
            [InlineKeyboardButton('📝 使用模板', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
        ]
    elif language == 'en':
        return [
            [InlineKeyboardButton('📝 Use template', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
        ]
    else:
        return [
            [InlineKeyboardButton('📝 Sử dụng template', callback_data='bulk_use_template')],
            [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
        ]


def get_bulk_stats_keyboard(language='vi'):
    """Tạo keyboard cho menu thống kê theo ngôn ngữ"""
    if language == 'zh':
        return [
            [InlineKeyboardButton('📢 批量发送消息', callback_data='bulk_all')],
            [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
        ]
    elif language == 'en':
        return [
            [InlineKeyboardButton('📢 Bulk messaging', callback_data='bulk_all')],
            [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
        ]
    else:
        return [
            [InlineKeyboardButton('📢 Gửi tin nhắn hàng loạt', callback_data='bulk_all')],
            [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
        ]


async def _forward_media_to_customers(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Helper function để forward media đến tất cả khách hàng"""
    try:
        customers = sheets_manager.get_all_customers()

        if customers:
            forwarded_count = 0
            failed_count = 0

            for customer in customers:
                try:
                    customer_user_id = customer.get('user_id')
                    if customer_user_id:
                        # Không gửi lại cho admin đang thao tác
                        if str(customer_user_id) == str(user_id):
                            print(f"⏭️ Bỏ qua admin {customer_user_id} (không gửi lại cho chính mình)")
                            continue

                        # Forward media message (giữ nguyên định dạng gốc, emoji động)
                        await context.bot.forward_message(
                            chat_id=int(customer_user_id),
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id
                        )
                        forwarded_count += 1

                        # Cập nhật trạng thái trong Google Sheets
                        sheets_manager.update_customer_message_status(customer_user_id, True)

                        # Ghi log
                        sheets_manager.add_message_log(
                            customer_user_id,
                            f"Forwarded media message from admin {user_id}",
                            'forward_media',
                            'sent'
                        )

                    else:
                        failed_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Lỗi forward media đến user {customer.get('user_id')}: {e}")

            # Thông báo kết quả
            await update.message.reply_text(
                f'✅ **ĐÃ FORWARD MEDIA THÀNH CÔNG!**\n\n'
                f'**Media đã được chuyển tiếp đến:**\n'
                f'✅ **Thành công:** {forwarded_count} khách hàng\n'
                f'❌ **Thất bại:** {failed_count} khách hàng\n\n'
                f'**Lưu ý:** Media đã được forward với định dạng gốc, giữ nguyên emoji động.'
            )

        else:
            await update.message.reply_text(
                '⚠️ **KHÔNG CÓ KHÁCH HÀNG NÀO**\n\n'
                'Không có khách hàng nào trong hệ thống để forward media.',
            )

    except Exception as e:
        logger.error(f"Lỗi forward media: {e}")
        await update.message.reply_text(
            f'❌ **LỖI KHI FORWARD MEDIA**\n\n'
            f'Lỗi: {str(e)}\n\n'
            'Vui lòng thử lại.',
        )


async def _forward_media_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Helper function để forward media đến tất cả các kênh"""
    try:
        # Lấy danh sách kênh từ bot_config
        forward_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
        if not forward_channels:
            await update.message.reply_text(
                '❌ **LỖI: CHƯA CẤU HÌNH KÊNH**\n\n'
                'Vui lòng cấu hình FORWARD_CHANNELS trong bot_config.py để sử dụng tính năng này.',
            )
            return

        # Chuyển tiếp media đến tất cả các kênh
        success_count = 0
        failed_count = 0
        failed_channels = []

        for channel_id in forward_channels:
            try:
                await context.bot.forward_message(
                    chat_id=channel_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                success_count += 1
                logger.info(f"✅ Đã forward media đến kênh {channel_id}")

            except Exception as e:
                failed_count += 1
                failed_channels.append(f"{channel_id} ({str(e)})")
                logger.error(f"❌ Lỗi copy media đến kênh {channel_id}: {e}")

        # Thông báo kết quả
        result_message = '✅ **ĐÃ CHUYỂN TIẾP MEDIA ĐẾN {} KÊNH!**\n\n'.format(len(forward_channels))
        result_message += '**Kết quả:**\n'
        result_message += '✅ **Thành công:** {} kênh\n'.format(success_count)

        if failed_count > 0:
            result_message += '❌ **Thất bại:** {} kênh\n'.format(failed_count)
            result_message += '**Kênh lỗi:**\n'
            for failed in failed_channels[:5]:  # Chỉ hiển thị 5 kênh lỗi đầu tiên
                result_message += '• {}\n'.format(failed)
            if len(failed_channels) > 5:
                result_message += '• ... và {} kênh khác\n'.format(len(failed_channels) - 5)

        result_message += '\n**Lưu ý:** Media đã được forward với định dạng gốc, giữ nguyên emoji động.'

        await update.message.reply_text(result_message)

        # Ghi log
        sheets_manager.add_message_log(
            str(user_id),
            f"Forwarded media to {success_count}/{len(forward_channels)} channels",
            'forward_media_to_channels',
            'sent'
        )

    except Exception as e:
        logger.error(f"Lỗi chuyển tiếp media đến kênh: {e}")
        await update.message.reply_text(
            f'❌ **LỖI KHI CHUYỂN TIẾP MEDIA ĐẾN KÊNH**\n\n'
            f'Lỗi: {str(e)}\n\n'
            'Vui lòng kiểm tra:\n'
            '• FORWARD_CHANNELS có được cấu hình đúng không\n'
            '• Bot có quyền gửi tin nhắn đến các kênh không\n'
            '• Các kênh có tồn tại không',
        )


async def log_user_interaction(update: Update):
    """Registrar interação do usuário no Google Sheets"""
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username or 'N/A'
        full_name = user.full_name or 'N/A'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Criar dados para registrar no sheets
        user_data_to_log = {
            'user_id': str(user_id),
            'username': username,
            'full_name': full_name,
            'time': timestamp
        }

        # Registrar no Google Sheets
        if sheets_manager:
            success = sheets_manager.add_customer(user_data_to_log)
            if success:
                logger.info(
                    f"Registrada interação do usuário: {user_id} - {username}"
                )
            else:
                logger.warning(
                    f"Falha ao registrar interação do usuário: {user_id}"
                )

    except Exception as e:
        logger.error(f"Erro ao registrar interação do usuário: {e}")


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar menu principal"""
    keyboard = [
        [
            InlineKeyboardButton(
                '📝 Cadastrar Conta',
                callback_data='register'
            ),
            InlineKeyboardButton(
                '💰 Problema de Depósito',
                callback_data='deposit'
            )
        ],
        [
            InlineKeyboardButton(
                '💸 Problema de Saque',
                callback_data='withdraw'
            ),
            InlineKeyboardButton(
                '🎁 Programas Promocionais',
                callback_data='promotions'
            )
        ],
        [
            InlineKeyboardButton(
                '🆘 Atendimento ao Cliente Online',
                callback_data='support'
            ),
            InlineKeyboardButton(
                '💬 Atendimento ao Cliente Telegram',
                callback_data='telegram_support'
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            ('🎉 Bem-vindo ao ABCDBET Customer Service Bot!'
             '\n\nEscolha uma opção abaixo:'),
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            ('🎉 Bem-vindo ao ABCDBET Customer Service Bot!'
             '\n\nEscolha uma opção abaixo:'),
            reply_markup=reply_markup
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Iniciar bot"""
    user_id = update.effective_user.id
    user_data[user_id] = {}

    # Debug logging để kiểm tra
    print(f"🚀 START command được gọi bởi user {user_id}")
    logger.info(f"START command được gọi bởi user {user_id}")

    # Registrar interação do usuário
    await log_user_interaction(update)

    # Inicializar notification system se não existir
    if not get_notification_manager():
        init_notification_system(context.bot)

    # Inicializar ecosystem integration se não existir
    # if not get_ecosystem_manager():
    #     init_ecosystem_integration()

    await show_main_menu(update, context)


async def handle_bulk_messaging_callbacks(query, context):
    """Xử lý các callback cho chức năng gửi tin nhắn hàng loạt"""
    try:
        # Lấy ngôn ngữ hiện tại từ user_data
        language = context.user_data.get('bulk_language', 'vi')

        if query.data == 'bulk_all':
            # Gửi tin nhắn đến tất cả khách hàng
            keyboard = get_bulk_all_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                get_bulk_all_title(language),
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_filter':
            # Gửi tin nhắn theo bộ lọc
            keyboard = get_bulk_filter_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                get_bulk_filter_title(language),
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_schedule':
            # Lên lịch gửi tin nhắn
            if language == 'zh':
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
            elif language == 'en':
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
            else:
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

            await query.edit_message_text(
                get_bulk_schedule_title(language),
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )

        elif query.data == 'bulk_templates':
            # Hiển thị template tin nhắn
            templates = bulk_messaging_manager.get_message_templates()
            template_text = get_bulk_templates_title(language)

            for i, template in enumerate(templates, 1):
                template_text += f"{i}. **{template['name']}**\n"
                template_text += f"   {template['content']}\n\n"

            keyboard = get_bulk_templates_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                template_text,
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_stats':
            # Hiển thị thống kê khách hàng
            stats = sheets_manager.get_customer_stats()
            if stats:
                if language == 'zh':
                    stats_message = f"""
{get_bulk_stats_title(language)}👥 **总客户数:** {stats['total']}
📅 **今天:** {stats['today']}
📆 **本周:** {stats['week']}
🗓️ **本月:** {stats['month']}

🔄 **最后更新:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                elif language == 'en':
                    stats_message = f"""
{get_bulk_stats_title(language)}👥 **Total customers:** {stats['total']}
📅 **Today:** {stats['today']}
📆 **This week:** {stats['week']}
🗓️ **This month:** {stats['month']}

🔄 **Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                else:
                    stats_message = f"""
{get_bulk_stats_title(language)}👥 **Tổng số khách hàng:** {stats['total']}
📅 **Hôm nay:** {stats['today']}
📆 **Tuần này:** {stats['week']}
🗓️ **Tháng này:** {stats['month']}

🔄 **Cập nhật lần cuối:** {datetime.now().strftime('%Y-%m:%S')}
                    """
            else:
                if language == 'zh':
                    stats_message = "❌ 无法获取客户统计"
                elif language == 'en':
                    stats_message = "❌ Cannot get customer statistics"
                else:
                    stats_message = "❌ Không thể lấy thống kê khách hàng"

            keyboard = get_bulk_stats_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                stats_message,
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_stop':
            # Dừng gửi tin nhắn hàng loạt
            language = context.user_data.get('bulk_language', 'vi')

            try:
                bulk_messaging_manager.stop_bulk_messaging()

                if language == 'zh':
                    success_message = '🛑 **已停止批量发送消息!**\n\n机器人将在完成当前消息后停止发送消息。\n\n您可以通过发送命令 /stop_bulk 来检查状态'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
                elif language == 'en':
                    success_message = '🛑 **BULK MESSAGING STOPPED!**\n\nBot will stop sending messages after completing the current message.\n\nYou can check status by sending command /stop_bulk'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
                else:
                    success_message = '🛑 **ĐÃ DỪNG GỬI TIN NHẮN HÀNG LOẠT!**\n\nBot sẽ dừng gửi tin nhắn sau khi hoàn thành tin nhắn hiện tại.\n\nBạn có thể kiểm tra trạng thái bằng cách gửi lệnh /stop_bulk'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

                await query.edit_message_text(
                    success_message,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )
            except Exception as e:
                logger.error(f"Lỗi khi dừng gửi tin nhắn hàng loạt: {e}")

                if language == 'zh':
                    error_message = f'❌ **停止发送消息时出错**\n\n错误: {str(e)}\n\n请重试或使用命令 /stop_bulk'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
                elif language == 'en':
                    error_message = f'❌ **ERROR STOPPING MESSAGES**\n\nError: {str(e)}\n\nPlease try again or use command /stop_bulk'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
                else:
                    error_message = f'❌ **LỖI KHI DỪNG GỬI TIN NHẮN**\n\nLỗi: {str(e)}\n\nVui lòng thử lại hoặc sử dụng lệnh /stop_bulk'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

                await query.edit_message_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )

        elif query.data == 'bulk_input_message':
            # Hiển thị hướng dẫn và lắng nghe tin nhắn từ người dùng
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '📝 **发送消息或媒体到帖子**\n\n**允许的媒体:**\n• 图片、视频、相册、文件\n• 贴纸、GIF、音频\n• 语音消息、圆形视频\n\n💡 **要将媒体附加到消息，请在此处发送**\n\n**现在请发送您的消息或媒体:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
            elif language == 'en':
                title = '📝 **SEND MESSAGE OR MEDIA TO POST**\n\n**Allowed media:**\n• Images, videos, albums, files\n• Stickers, GIFs, audio\n• Voice messages, video notes\n\n💡 **To attach media to message, send here**\n\n**Now please send your message or media:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
            else:
                title = '📝 **GỬI TIN NHẮN HOẶC PHƯƠNG TIỆN VÀO BÀI ĐĂNG**\n\n**Phương tiện được phép:**\n• Ảnh, video, album, tệp\n• Nhãn dán, GIF, âm thanh\n• Tin nhắn thoại, video tròn\n\n💡 **Để đính kèm phương tiện vào tin nhắn, hãy gửi tại đây**\n\n**Bây giờ hãy gửi tin nhắn hoặc media của bạn:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )

            # Đặt trạng thái để bot lắng nghe tin nhắn từ người dùng
            context.user_data['waiting_for_message'] = True
            context.user_data['message_type'] = 'bulk_input'

        elif query.data == 'bulk_forward_to_channel':
            # Chuyển tiếp tin nhắn đến kênh
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '📢 **转发消息到频道**\n\n**使用方法:**\n• 发送任意文本消息 → 机器人将转发到频道\n• 发送媒体 (图片、视频、文件、音频) → 机器人将转发媒体\n• 无需选择消息类型，机器人自动识别!\n\n**请发送要转发到频道的消息或媒体:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
            elif language == 'en':
                title = '📢 **FORWARD MESSAGE TO CHANNEL**\n\n**How to use:**\n• Send any text message → Bot will forward to channel\n• Send media (image, video, file, audio) → Bot will forward media\n• No need to select message type, bot automatically detects!\n\n**Please send message or media to forward to channel:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
            else:
                title = '📢 **CHUYỂN TIẾP TIN NHẮN ĐẾN KÊNH**\n\n**Cách sử dụng:**\n• Gửi tin nhắn text bất kỳ → Bot sẽ chuyển tiếp đến kênh\n• Gửi media (ảnh, video, file, audio) → Bot sẽ chuyển tiếp media\n• Không cần chọn loại tin nhắn, bot tự động nhận diện!\n\n**Hãy gửi tin nhắn hoặc media để chuyển tiếp đến kênh:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )

            # Đặt trạng thái để bot lắng nghe tin nhắn từ người dùng
            context.user_data['waiting_for_message'] = True
            context.user_data['message_type'] = 'forward_to_channel'

        elif query.data == 'bulk_text_only':
            # Chỉ gửi text
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '📝 **输入文本消息**\n\n请输入您要发送给客户的消息。\n\n**注意:** 您可以使用以下占位符:\n• `{username}` - 用户名\n• `{full_name}` - 全名\n• `{action}` - 客户操作\n• `{date}` - 日期\n\n**现在请输入您的消息:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_input_message')
            elif language == 'en':
                title = '📝 **INPUT TEXT MESSAGE**\n\nPlease enter the message you want to send to customers.\n\n**Note:** You can use the following placeholders:\n• `{username}` - Username\n• `{full_name}` - Full name\n• `{action}` - Customer action\n• `{date}` - Date\n\n**Now please enter your message:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_input_message')
            else:
                title = '📝 **NHẬP TIN NHẮN TEXT**\n\nVui lòng nhập tin nhắn bạn muốn gửi đến khách hàng.\n\n**Lưu ý:** Bạn có thể sử dụng các placeholder sau:\n• `{username}` - Tên người dùng\n• `{full_name}` - Họ tên đầy đủ\n• `{action}` - Hành động của khách hàng\n• `{date}` - Ngày tháng\n\n**Bây giờ hãy nhập tin nhắn của bạn:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_input_message')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_message'] = True
            context.user_data['message_type'] = 'bulk_all'
            context.user_data['media_type'] = 'text_only'

        elif query.data == 'bulk_with_photo':
            # Gửi text + hình ảnh
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '🖼️ **发送文本+图片**\n\n**步骤1:** 发送您要使用的图片\n**步骤2:** 然后为图片输入说明文字\n\n**注意:** 您可以使用以下占位符:\n• `{username}` - 用户名\n• `{full_name}` - 全名\n• `{action}` - 客户操作\n• `{date}` - 日期\n\n**现在发送图片:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_input_message')
            elif language == 'en':
                title = '🖼️ **SEND TEXT + PHOTO**\n\n**Step 1:** Send the photo you want to use\n**Step 2:** Then enter caption (text) for the photo\n\n**Note:** You can use the following placeholders:\n• `{username}` - Username\n• `{full_name}` - Full name\n• `{action}` - Customer action\n• `{date}` - Date\n\n**Send photo now:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_input_message')
            else:
                title = '🖼️ **GỬI TEXT + HÌNH ẢNH**\n\n**Bước 1:** Gửi hình ảnh bạn muốn sử dụng\n**Bước 2:** Sau đó nhập caption (text) cho hình ảnh\n\n**Lưu ý:** Bạn có thể sử dụng các placeholder sau:\n• `{username}` - Tên người dùng\n• `{full_name}` - Họ tên đầy đủ\n• `{action}` - Hành động của khách hàng\n• `{date}` - Ngày tháng\n\n**Gửi hình ảnh ngay bây giờ:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_input_message')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_photo'] = True
            context.user_data['message_type'] = 'bulk_all'
            context.user_data['media_type'] = 'photo'

        elif query.data == 'bulk_with_video':
            # Gửi text + video
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '🎥 **发送文本+视频**\n\n**步骤1:** 发送您要使用的视频\n**步骤2:** 然后为视频输入说明文字\n\n**注意:** 您可以使用以下占位符:\n• `{username}` - 用户名\n• `{full_name}` - 全名\n• `{action}` - 客户操作\n• `{date}` - 日期\n\n**现在发送视频:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_input_message')
            elif language == 'en':
                title = '🎥 **SEND TEXT + VIDEO**\n\n**Step 1:** Send the video you want to use\n**Step 2:** Then enter caption (text) for the video\n\n**Note:** You can use the following placeholders:\n• `{username}` - Username\n• `{full_name}` - Full name\n• `{action}` - Customer action\n• `{date}` - Date\n\n**Send video now:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_input_message')
            else:
                title = '🎥 **GỬI TEXT + VIDEO**\n\n**Bước 1:** Gửi video bạn muốn sử dụng\n**Bước 2:** Sau đó nhập caption (text) cho video\n\n**Lưu ý:** Bạn có thể sử dụng các placeholder sau:\n• `{username}` - Tên người dùng\n• `{full_name}` - Họ tên đầy đủ\n• `{action}` - Hành động của khách hàng\n• `{date}` - Ngày tháng\n\n**Gửi video ngay bây giờ:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_input_message')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_video'] = True
            context.user_data['message_type'] = 'bulk_all'
            context.user_data['media_type'] = 'video'

        elif query.data == 'bulk_with_document':
            # Gửi text + file
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '📄 **发送文本+文件**\n\n**步骤1:** 发送您要使用的文件\n**步骤2:** 然后为文件输入说明文字\n\n**注意:** 您可以使用以下占位符:\n• `{username}` - 用户名\n• `{full_name}` - 全名\n• `{action}` - 客户操作\n• `{date}` - 日期\n\n**现在发送文件:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_input_message')
            elif language == 'en':
                title = '📄 **SEND TEXT + FILE**\n\n**Step 1:** Send the file you want to use\n**Step 2:** Then enter caption (text) for the file\n\n**Note:** You can use the following placeholders:\n• `{username}` - Username\n• `{full_name}` - Full name\n• `{action}` - Customer action\n• `{date}` - Date\n\n**Send file now:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_input_message')
            else:
                title = '📄 **GỬI TEXT + FILE**\n\n**Bước 1:** Gửi file bạn muốn sử dụng\n**Bước 2:** Sau đó nhập caption (text) cho file\n\n**Lưu ý:** Bạn có thể sử dụng các placeholder sau:\n• `{username}` - Tên người dùng\n• `{full_name}` - Họ tên đầy đủ\n• `{action}` - Hành động của khách hàng\n• `{date}` - Ngày tháng\n\n**Gửi file ngay bây giờ:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_input_message')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_document'] = True
            context.user_data['message_type'] = 'bulk_all'
            context.user_data['media_type'] = 'document'

        elif query.data == 'bulk_with_audio':
            # Gửi text + audio
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '🎵 **发送文本+音频**\n\n**步骤1:** 发送您要使用的音频\n**步骤2:** 然后为音频输入说明文字\n\n**注意:** 您可以使用以下占位符:\n• `{username}` - 用户名\n• `{full_name}` - 全名\n• `{action}` - 客户操作\n• `{date}` - 日期\n\n**现在发送音频:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_input_message')
            elif language == 'en':
                title = '🎵 **SEND TEXT + AUDIO**\n\n**Step 1:** Send the audio you want to use\n**Step 2:** Then enter caption (text) for the audio\n\n**Note:** You can use the following placeholders:\n• `{username}` - Username\n• `{full_name}` - Full name\n• `{action}` - Customer action\n• `{date}` - Date\n\n**Send audio now:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_input_message')
            else:
                title = '🎵 **GỬI TEXT + AUDIO**\n\n**Bước 1:** Gửi audio bạn muốn sử dụng\n**Bước 2:** Sau đó nhập caption (text) cho audio\n\n**Lưu ý:** Bạn có thể sử dụng các placeholder sau:\n• `{username}` - Tên người dùng\n• `{full_name}` - Họ tên đầy đủ\n• `{action}` - Hành động của khách hàng\n• `{date}` - Ngày tháng\n\n**Gửi audio ngay bây giờ:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_input_message')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_audio'] = True
            context.user_data['message_type'] = 'bulk_all'
            context.user_data['media_type'] = 'audio'

        elif query.data == 'bulk_use_template':
            # Sử dụng template tin nhắn
            templates = bulk_messaging_manager.get_message_templates()
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                template_text = '📋 **选择消息模板**\n\n'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_all')
            elif language == 'en':
                template_text = '📋 **SELECT MESSAGE TEMPLATE**\n\n'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_all')
            else:
                template_text = '📋 **CHỌN TEMPLATE TIN NHẮN**\n\n'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_all')

            keyboard = []
            for i, template in enumerate(templates, 1):
                template_text += f"{i}. **{template['name']}**\n"
                template_text += f"   {template['content']}\n\n"
                keyboard.append([InlineKeyboardButton(
                    f"📝 Sử dụng {template['name']}",
                    callback_data=f'bulk_template_{i - 1}'
                )])

            keyboard.append([back_button])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                template_text,
                reply_markup=reply_markup,
            )

        elif query.data.startswith('bulk_template_'):
            # Sử dụng template cụ thể
            template_index = int(query.data.split('_')[2])
            templates = bulk_messaging_manager.get_message_templates()
            language = context.user_data.get('bulk_language', 'vi')

            if 0 <= template_index < len(templates):
                template = templates[template_index]

                if language == 'zh':
                    title = f'📋 **已选择模板: {template["name"]}**\n\n**内容:**\n{template["content"]}\n\n您要将此消息发送给所有客户吗?'
                    send_button = InlineKeyboardButton('✅ 立即发送', callback_data='bulk_send_template')
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_use_template')
                elif language == 'en':
                    title = f'📋 **TEMPLATE SELECTED: {template["name"]}**\n\n**Content:**\n{template["content"]}\n\nDo you want to send this message to all customers?'
                    send_button = InlineKeyboardButton('✅ Send now', callback_data='bulk_send_template')
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_use_template')
                else:
                    title = f'📋 **TEMPLATE ĐÃ CHỌN: {template["name"]}**\n\n**Nội dung:**\n{template["content"]}\n\nBạn có muốn gửi tin nhắn này đến tất cả khách hàng?'
                    send_button = InlineKeyboardButton('✅ Gửi ngay', callback_data='bulk_send_template')
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_use_template')

                await query.edit_message_text(
                    title,
                    reply_markup=InlineKeyboardMarkup([
                        [send_button],
                        [back_button]
                    ])
                )
                context.user_data['selected_template'] = template
            else:
                if language == 'zh':
                    error_message = '❌ 模板无效。'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_use_template')
                elif language == 'en':
                    error_message = '❌ Invalid template.'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_use_template')
                else:
                    error_message = '❌ Template không hợp lệ.'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_use_template')

                await query.edit_message_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )

        elif query.data == 'bulk_send_template':
            # Gửi tin nhắn template
            template = context.user_data.get('selected_template')
            language = context.user_data.get('bulk_language', 'vi')

            if template:
                try:
                    # Gửi tin nhắn đến tất cả khách hàng
                    result = await bulk_messaging_manager.send_bulk_message(
                        message_content=template['content'],
                        filter_type='all'
                    )

                    if language == 'zh':
                        success_message = f'✅ **消息发送成功!**\n\n**模板:** {template["name"]}\n**结果:** {result["success_count"]}/{result["total_count"]} 条消息已发送\n**时间:** {result["duration"]:.2f} 秒'
                        other_button = InlineKeyboardButton('📢 发送其他消息', callback_data='bulk_all')
                    elif language == 'en':
                        success_message = f'✅ **MESSAGE SENT SUCCESSFULLY!**\n\n**Template:** {template["name"]}\n**Result:** {result["success_count"]}/{result["total_count"]} messages sent\n**Time:** {result["duration"]:.2f} seconds'
                        other_button = InlineKeyboardButton('📢 Send other message', callback_data='bulk_all')
                    else:
                        success_message = f'✅ **ĐÃ GỬI TIN NHẮN THÀNH CÔNG!**\n\n**Template:** {template["name"]}\n**Kết quả:** {result["success_count"]}/{result["total_count"]} tin nhắn đã gửi\n**Thời gian:** {result["duration"]:.2f} giây'
                        other_button = InlineKeyboardButton('📢 Gửi tin nhắn khác', callback_data='bulk_all')

                    await query.edit_message_text(
                        success_message,
                        reply_markup=InlineKeyboardMarkup([[other_button]])
                    )
                except Exception as e:
                    if language == 'zh':
                        error_message = f'❌ **发送消息时出错**\n\n错误: {str(e)}'
                        back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_all')
                    elif language == 'en':
                        error_message = f'❌ **ERROR SENDING MESSAGE**\n\nError: {str(e)}'
                        back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_all')
                    else:
                        error_message = f'❌ **LỖI KHI GỬI TIN NHẮN**\n\nLỗi: {str(e)}'
                        back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_all')

                    await query.edit_message_text(
                        error_message,
                        reply_markup=InlineKeyboardMarkup([[back_button]])
                    )
            else:
                if language == 'zh':
                    error_message = '❌ 找不到模板。'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_all')
                elif language == 'en':
                    error_message = '❌ Template not found.'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_all')
                else:
                    error_message = '❌ Không tìm thấy template.'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_all')

                await query.edit_message_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )

        elif query.data == 'bulk_filter_date':
            # Lọc theo ngày
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '📅 **按日期筛选**\n\n请输入日期 (格式: YYYY-MM-DD)\n例如: 2025-08-24'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_filter')
            elif language == 'en':
                title = '📅 **FILTER BY DATE**\n\nPlease enter date (format: YYYY-MM-DD)\nExample: 2025-08-24'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_filter')
            else:
                title = '📅 **LỌC THEO NGÀY**\n\nVui lòng nhập ngày (định dạng: YYYY-MM-DD)\nVí dụ: 2025-08-24'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_filter')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_filter'] = True
            context.user_data['filter_type'] = 'date'

        elif query.data == 'bulk_filter_action':
            # Lọc theo hành động
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '🎯 **按操作筛选**\n\n请输入需要筛选的操作:\n例如: deposit, withdraw, register'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_filter')
            elif language == 'en':
                title = '🎯 **FILTER BY ACTION**\n\nPlease enter the action to filter:\nExample: deposit, withdraw, register'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_filter')
            else:
                title = '🎯 **LỌC THEO HÀNH ĐỘNG**\n\nVui lòng nhập hành động cần lọc:\nVí dụ: deposit, withdraw, register'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_filter')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_filter'] = True
            context.user_data['filter_type'] = 'action'

        elif query.data == 'bulk_filter_username':
            # Lọc theo username
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '👤 **按用户名筛选**\n\n请输入需要筛选的用户名:'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_filter')
            elif language == 'en':
                title = '👤 **FILTER BY USERNAME**\n\nPlease enter the username to filter:'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_filter')
            else:
                title = '👤 **LỌC THEO USERNAME**\n\nVui lòng nhập username cần lọc:'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_filter')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )
            context.user_data['waiting_for_filter'] = True
            context.user_data['filter_type'] = 'username'

        else:
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                error_message = '❌ 选项无法识别。'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
            elif language == 'en':
                error_message = '❌ Option not recognized.'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
            else:
                error_message = '❌ Tùy chọn không được nhận diện.'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

            await query.edit_message_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )

    except Exception as e:
        logger.error(f"Lỗi xử lý callback gửi tin nhắn hàng loạt: {e}")
        language = context.user_data.get('bulk_language', 'vi')

        if language == 'zh':
            error_message = '❌ 发生错误。请重试。'
            back_button = InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')
        elif language == 'en':
            error_message = '❌ An error occurred. Please try again.'
            back_button = InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')
        else:
            error_message = '❌ Đã xảy ra lỗi. Vui lòng thử lại.'
            back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')

        await query.edit_message_text(
            error_message,
            reply_markup=InlineKeyboardMarkup([[back_button]])
        )


async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý media - forward chỉ khi admin đã bật chế độ chờ"""
    # Debug and use message_type to decide behavior
    message_type = context.user_data.get('message_type')
    print(f"handle_media_message called - waiting_for_message={context.user_data.get('waiting_for_message')} message_type={message_type}")

    user_id = update.effective_user.id
    # Kiểm tra quyền admin
    if user_id not in bot_config.ADMIN_USER_IDS:
        print(f"⚠️ User {user_id} không có quyền admin")
        return

    # Kiểm tra xem admin có đang ở trạng thái chờ tin nhắn để hẹn giờ chuyển tiếp không
    if context.user_data.get('waiting_for_schedule_message'):
        # Admin đang ở trạng thái nhập media để hẹn giờ chuyển tiếp
        print(f"⏰ Admin {user_id} đang nhập media để hẹn giờ chuyển tiếp")

        # Lưu thông tin media
        context.user_data['schedule_message_data'] = {
            'is_forward': True,
            'chat_id': update.effective_chat.id,
            'message_id': update.message.message_id
        }

        # Reset trạng thái chờ tin nhắn
        context.user_data['waiting_for_schedule_message'] = False

        # Yêu cầu nhập thời gian hẹn giờ
        language = context.user_data.get('language', 'vi')
        if language == 'vi':
            message = (
                "⏰ **NHẬP THỜI GIAN HẸN GIỜ**\n\n"
                "📎 Media đã được lưu để hẹn giờ chuyển tiếp.\n\n"
                "🕐 **Nhập thời gian hẹn giờ theo định dạng:**\n"
                "• `DD/MM/YYYY HH:MM` (ví dụ: 25/12/2024 14:30)\n"
                "• `HH:MM` (hẹn giờ hôm nay, ví dụ: 14:30)\n"
                "• `+N phút` (sau N phút, ví dụ: +30 phút)\n"
                "• `+N giờ` (sau N giờ, ví dụ: +2 giờ)\n\n"
                "💡 **Lưu ý:** Thời gian theo múi giờ Việt Nam (UTC+7)"
            )
        else:
            message = (
                "⏰ **INSERIR HORÁRIO AGENDADO**\n\n"
                "📎 Mídia salva para agendamento de encaminhamento.\n\n"
                "🕐 **Insira o horário agendado no formato:**\n"
                "• `DD/MM/YYYY HH:MM` (exemplo: 25/12/2024 14:30)\n"
                "• `HH:MM` (agendar para hoje, exemplo: 14:30)\n"
                "• `+N minutos` (após N minutos, exemplo: +30 minutos)\n"
                "• `+N horas` (após N horas, exemplo: +2 horas)\n\n"
                "💡 **Nota:** Horário no fuso horário do Vietnã (UTC+7)"
            )

        # Đặt trạng thái chờ thời gian
        context.user_data['waiting_for_schedule_time'] = True

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        return

    if not message_type:
        # No action requested
        print("⚠️ No message_type set, ignoring media")
        return

    try:
        if message_type == 'bulk_input':
            # Admin đang ở trạng thái nhập tin nhắn - forward ngay lập tức đến khách hàng
            print(f"📝 Admin {user_id} đang nhập media - forward đến khách hàng")

            # Forward media đến tất cả khách hàng
            await _forward_media_to_customers(update, context, user_id)

        elif message_type == 'forward_to_channel':
            # Admin đang ở trạng thái chuyển tiếp đến kênh
            print(f"📢 Admin {user_id} đang chuyển tiếp media đến kênh")

            # Thông báo xác nhận trước khi chuyển tiếp (hiển thị danh sách kênh và 2 nút XÁC NHẬN / HỦY)
            forward_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
            if not forward_channels:
                await update.message.reply_text('❌ LỖI: CHƯA CẤU HÌNH KÊNH. Vui lòng cấu hình FORWARD_CHANNELS trong bot_config.py để sử dụng tính năng này.')
                return

            channel_count = len(forward_channels)
            # Tạo keyboard xác nhận
            confirm_btn = InlineKeyboardButton('✅ XÁC NHẬN', callback_data='confirm_forward')
            cancel_btn = InlineKeyboardButton('❌ HỦY', callback_data='cancel_forward')
            # Hiển thị tên/ID các kênh (dạng text an toàn)
            channels_text = '\n'.join([f'- {c}' for c in forward_channels])
            msg_text = (
                f"Bạn sắp chuyển tiếp media này đến {channel_count} kênh:\n{channels_text}\n\n"
                "Nhấn 'XÁC NHẬN' để chuyển tiếp hoặc 'HỦY' để hủy bỏ."
            )
            await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup([[confirm_btn, cancel_btn]]))

            # Only accept if message contains text, media, caption, or is a forward from a chat
            has_content = bool(any([
                (getattr(update.message, 'text', None) and str(update.message.text).strip()),
                getattr(update.message, 'caption', None),
                update.message.photo,
                update.message.video,
                update.message.document,
                update.message.sticker,
                update.message.audio,
                update.message.animation,
            ]))
            is_forward = bool(getattr(update.message, 'forward_from_chat', None) and getattr(update.message, 'forward_from_message_id', None))
            if not (has_content or is_forward):
                await update.message.reply_text('⚠️ Vui lòng gửi/forward một bài đăng, text hoặc media để chuyển tiếp.')
                return

            # Đặt cờ chờ xác nhận và lưu thông tin message cần forward
            context.user_data['waiting_for_confirmation'] = True
            # Prefer original channel message id when available
            if is_forward:
                orig_chat = update.message.forward_from_chat
                orig_msg_id = update.message.forward_from_message_id
                context.user_data['pending_forward'] = {
                    'original_chat_id': int(orig_chat.id),
                    'original_message_id': int(orig_msg_id)
                }
            else:
                context.user_data['pending_forward'] = {
                    'chat_id': int(update.effective_chat.id),
                    'message_id': int(update.message.message_id)
                }

        elif message_type == 'forward_to_selected_channels':
            # Admin đang ở trạng thái chuyển tiếp đến các kênh đã chọn
            print(f"🎯 Admin {user_id} đang chuyển tiếp media đến các kênh đã chọn")

            # Lấy danh sách kênh đã chọn
            selected_channels = context.user_data.get('selected_channels', [])
            if not selected_channels:
                await update.message.reply_text(
                    '❌ **LỖI: KHÔNG CÓ KÊNH NÀO ĐƯỢC CHỌN**\n\n'
                    'Vui lòng chọn kênh trước khi gửi media.',
                )
                return

            # Chuyển tiếp media đến các kênh đã chọn
            try:
                success_count = 0
                failed_count = 0
                failed_channels = []

                for channel_id in selected_channels:
                    try:
                        await context.bot.forward_message(
                            chat_id=channel_id,
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id
                        )
                        success_count += 1
                        logger.info(f"✅ Đã forward media đến kênh {channel_id}")

                    except Exception as e:
                        failed_count += 1
                        failed_channels.append(f"{channel_id} ({str(e)})")
                        logger.error(f"❌ Lỗi forward media đến kênh {channel_id}: {e}")

                # Thông báo kết quả
                result_message = f'✅ **ĐÃ CHUYỂN TIẾP MEDIA ĐẾN {len(selected_channels)} KÊNH ĐÃ CHỌN!**\n\n'
                result_message += '**Kết quả:**\n'
                result_message += f'✅ **Thành công:** {success_count} kênh\n'

                if failed_count > 0:
                    result_message += f'❌ **Thất bại:** {failed_count} kênh\n'
                    result_message += '**Kênh lỗi:**\n'
                    for failed in failed_channels[:5]:  # Chỉ hiển thị 5 kênh lỗi đầu tiên
                        result_message += f'• {failed}\n'
                    if len(failed_channels) > 5:
                        result_message += f'• ... và {len(failed_channels) - 5} kênh khác\n'

                result_message += '\n**Lưu ý:** Media đã được forward với định dạng gốc, giữ nguyên emoji động.'

                await update.message.reply_text(result_message)

                # Ghi log
                sheets_manager.add_message_log(
                    str(user_id),
                    f"Forwarded media to {success_count}/{len(selected_channels)} selected channels",
                    'forward_media_to_selected_channels',
                    'sent'
                )

                # Reset danh sách kênh đã chọn
                context.user_data.pop('selected_channels', None)

            except Exception as e:
                logger.error(f"Lỗi chuyển tiếp media đến các kênh đã chọn: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI CHUYỂN TIẾP MEDIA ĐẾN CÁC KÊNH ĐÃ CHỌN**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng kiểm tra:\n'
                    '• Các kênh có tồn tại không\n'
                    '• Bot có quyền gửi media đến các kênh không',
                )

        else:
            # Không rõ loại hành động - từ chối xử lý
            print(f"⚠️ message_type không hợp lệ: {message_type} - bỏ qua")
            await update.message.reply_text('⚠️ Không có hành động nào được thiết lập. Vui lòng chọn chức năng trước khi gửi media.')

    except Exception as e:
        print(f"❌ Lỗi xử lý media: {e}")
        logger.error(f"Lỗi xử lý media: {e}")
        if update.message:
            await update.message.reply_text('❌ Lỗi khi xử lý media. Vui lòng thử lại.')
    finally:
        # Sau khi gửi yêu cầu xác nhận hoặc đã thực hiện hành động, reset trạng thái chờ (trừ khi đang chờ xác nhận)
        if not context.user_data.get('waiting_for_confirmation'):
            context.user_data['waiting_for_message'] = False
            context.user_data['message_type'] = None


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn văn bản - chỉ forward"""
    try:
        user_id = update.effective_user.id

        # Debug logging để kiểm tra
        print(f"📝 handle_text_message được gọi bởi user {user_id}, text: '{update.message.text}'")
        logger.info(f"handle_text_message được gọi bởi user {user_id}, text: '{update.message.text}'")

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            return

        # Kiểm tra xem admin có đang ở trạng thái chờ thời gian hẹn giờ không
        if context.user_data.get('waiting_for_schedule_time'):
            # Admin đang nhập thời gian hẹn giờ
            print(f"⏰ Admin {user_id} đang nhập thời gian hẹn giờ: {update.message.text}")

            try:
                # Parse thời gian hẹn giờ
                schedule_time = parse_schedule_time(update.message.text)

                if not schedule_time:
                    # Thời gian không hợp lệ
                    language = context.user_data.get('language', 'vi')
                    if language == 'vi':
                        error_message = (
                            "❌ THỜI GIAN KHÔNG HỢP LỆ!\n\n"
                            "🕐 Định dạng hợp lệ:\n\n"
                            "📅 Ngày tháng năm:\n"
                            "• DD/MM/YYYY HH:MM (ví dụ: 25/12/2024 14:30)\n"
                            "• DD-MM-YYYY HH:MM (ví dụ: 25-12-2024 14:30)\n"
                            "• YYYY-MM-DD HH:MM (ví dụ: 2024-12-25 14:30)\n\n"
                            "🔢 Định dạng số liên tục:\n"
                            "• DDMMYYYYHHMMSS (ví dụ: 25092024143000)\n"
                            "• YYYYMMDDHHMMSS (ví dụ: 20240925143000)\n"
                            "• DDMMYYYYHHMM (ví dụ: 250920241430)\n"
                            "• YYYYMMDDHHMM (ví dụ: 202409251430)\n\n"
                            "⏰ Thời gian đơn giản:\n"
                            "• HH:MM (hôm nay, ví dụ: 14:30)\n"
                            "• hôm nay 14:30\n"
                            "• ngày mai 20:00\n"
                            "• mai 20:00\n\n"
                            "⏱️ Thời gian tương đối:\n"
                            "• +30 phút hoặc 30 phút nữa\n"
                            "• +2 giờ hoặc 2 giờ sau\n"
                            "• +1 ngày hoặc 1 ngày nữa\n\n"
                            "🌅 Thời gian trong ngày:\n"
                            "• sáng 8:00\n"
                            "• chiều 14:30\n"
                            "• tối 20:00\n\n"
                            "⚡ Ngay lập tức:\n"
                            "• bây giờ hoặc ngay bây giờ\n\n"
                            "💡 Vui lòng nhập lại thời gian:"
                        )
                    else:
                        error_message = (
                            "❌ HORÁRIO INVÁLIDO!\n\n"
                            "🕐 Formatos válidos:\n\n"
                            "📅 Data e hora:\n"
                            "• DD/MM/YYYY HH:MM (exemplo: 25/12/2024 14:30)\n"
                            "• DD-MM-YYYY HH:MM (exemplo: 25-12-2024 14:30)\n"
                            "• YYYY-MM-DD HH:MM (exemplo: 2024-12-25 14:30)\n\n"
                            "⏰ Hora simples:\n"
                            "• HH:MM (hoje, exemplo: 14:30)\n"
                            "• hoje 14:30\n"
                            "• amanhã 20:00\n\n"
                            "⏱️ Tempo relativo:\n"
                            "• +30 minutos ou 30 minutos depois\n"
                            "• +2 horas ou 2 horas depois\n"
                            "• +1 dia ou 1 dia depois\n\n"
                            "🌅 Período do dia:\n"
                            "• manhã 8:00\n"
                            "• tarde 14:30\n"
                            "• noite 20:00\n\n"
                            "⚡ Imediato:\n"
                            "• agora ou immediately\n\n"
                            "💡 Por favor, insira o horário novamente:"
                        )

                    await update.message.reply_text(error_message)
                    return

                # Lấy dữ liệu tin nhắn đã lưu
                message_data = context.user_data.get('schedule_message_data', {})
                forward_type = context.user_data.get('schedule_forward_type', 'all_customers')

                # Lên lịch chuyển tiếp
                result = await scheduled_forward_manager.schedule_forward_message(
                    schedule_time=schedule_time,
                    message_data=message_data,
                    forward_type=forward_type,
                    admin_id=user_id
                )

                # Reset trạng thái
                context.user_data['waiting_for_schedule_time'] = False
                context.user_data.pop('schedule_message_data', None)
                context.user_data.pop('schedule_forward_type', None)

                # Thông báo kết quả
                language = context.user_data.get('language', 'vi')
                if result['success']:
                    if language == 'vi':
                        success_message = (
                            f"✅ ĐÃ LÊN LỊCH CHUYỂN TIẾP THÀNH CÔNG!\n\n"
                            f"🕐 Thời gian hẹn giờ: {result['schedule_time']}\n"
                            f"📝 Loại chuyển tiếp: {forward_type}\n"
                            f"🆔 ID lịch hẹn: {result['schedule_id']}\n\n"
                            f"💡 Lưu ý: Tin nhắn sẽ được chuyển tiếp tự động vào thời gian đã hẹn."
                        )
                    else:
                        success_message = (
                            f"✅ ENCAMINHAMENTO AGENDADO COM SUCESSO!\n\n"
                            f"🕐 Horário agendado: {result['schedule_time']}\n"
                            f"📝 Tipo de encaminhamento: {forward_type}\n"
                            f"🆔 ID do agendamento: {result['schedule_id']}\n\n"
                            f"💡 Nota: A mensagem será encaminhada automaticamente no horário agendado."
                        )
                else:
                    if language == 'vi':
                        success_message = f"❌ LỖI LÊN LỊCH CHUYỂN TIẾP\n\n{result['message']}"
                    else:
                        success_message = f"❌ ERRO AO AGENDAR ENCAMINHAMENTO\n\n{result['message']}"

                await update.message.reply_text(success_message)
                return

            except Exception as e:
                logger.error(f"Lỗi xử lý thời gian hẹn giờ: {e}")
                await update.message.reply_text(
                    f"❌ LỖI XỬ LÝ THỜI GIAN HẸN GIỜ\n\n"
                    f"Lỗi: {str(e)}\n\n"
                    f"Vui lòng thử lại."
                )
                return

        # Kiểm tra xem admin có đang ở trạng thái chờ tin nhắn để hẹn giờ chuyển tiếp không
        if context.user_data.get('waiting_for_schedule_message'):
            # Admin đang ở trạng thái nhập tin nhắn để hẹn giờ chuyển tiếp
            print(f"⏰ Admin {user_id} đang nhập tin nhắn để hẹn giờ chuyển tiếp")

            # Lưu thông tin tin nhắn
            context.user_data['schedule_message_data'] = {
                'text': update.message.text,
                'is_forward': False,
                'chat_id': update.effective_chat.id,
                'message_id': update.message.message_id
            }

            # Reset trạng thái chờ tin nhắn
            context.user_data['waiting_for_schedule_message'] = False

            # Yêu cầu nhập thời gian hẹn giờ
            language = context.user_data.get('language', 'vi')
            if language == 'vi':
                message = (
                    "⏰ **NHẬP THỜI GIAN HẸN GIỜ**\n\n"
                    "📝 Tin nhắn đã được lưu:\n"
                    f"```\n{update.message.text[:100]}{'...' if len(update.message.text) > 100 else ''}\n```\n\n"
                    "🕐 **Nhập thời gian hẹn giờ theo định dạng:**\n"
                    "• `DD/MM/YYYY HH:MM` (ví dụ: 25/12/2024 14:30)\n"
                    "• `HH:MM` (hẹn giờ hôm nay, ví dụ: 14:30)\n"
                    "• `+N phút` (sau N phút, ví dụ: +30 phút)\n"
                    "• `+N giờ` (sau N giờ, ví dụ: +2 giờ)\n\n"
                    "💡 **Lưu ý:** Thời gian theo múi giờ Việt Nam (UTC+7)"
                )
            else:
                message = (
                    "⏰ **INSERIR HORÁRIO AGENDADO**\n\n"
                    "📝 Mensagem salva:\n"
                    f"```\n{update.message.text[:100]}{'...' if len(update.message.text) > 100 else ''}\n```\n\n"
                    "🕐 **Insira o horário agendado no formato:**\n"
                    "• `DD/MM/YYYY HH:MM` (exemplo: 25/12/2024 14:30)\n"
                    "• `HH:MM` (agendar para hoje, exemplo: 14:30)\n"
                    "• `+N minutos` (após N minutos, exemplo: +30 minutos)\n"
                    "• `+N horas` (após N horas, exemplo: +2 horas)\n\n"
                    "💡 **Nota:** Horário no fuso horário do Vietnã (UTC+7)"
                )

            # Đặt trạng thái chờ thời gian
            context.user_data['waiting_for_schedule_time'] = True

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return

        # Kiểm tra xem admin có đang ở trạng thái chờ tin nhắn không
        if context.user_data.get('waiting_for_message') and context.user_data.get('message_type') == 'bulk_input':
            # Admin đang ở trạng thái nhập tin nhắn - forward ngay lập tức
            print(f"📝 Admin {user_id} đang nhập tin nhắn - forward ngay lập tức")

            # Reset trạng thái
            context.user_data['waiting_for_message'] = False
            context.user_data['message_type'] = None

            # Forward tin nhắn đến tất cả khách hàng
            try:
                customers = sheets_manager.get_all_customers()

                if customers:
                    forwarded_count = 0
                    failed_count = 0

                    for customer in customers:
                        try:
                            customer_user_id = customer.get('user_id')
                            if customer_user_id:
                                # Không gửi lại cho admin đang thao tác
                                if str(customer_user_id) == str(user_id):
                                    print(f"⏭️ Bỏ qua admin {customer_user_id} (không gửi lại cho chính mình)")
                                    continue

                                # Forward tin nhắn (giữ nguyên định dạng gốc, emoji động)
                                await context.bot.forward_message(
                                    chat_id=int(customer_user_id),
                                    from_chat_id=update.effective_chat.id,
                                    message_id=update.message.message_id
                                )
                                forwarded_count += 1

                                # Cập nhật trạng thái trong Google Sheets
                                sheets_manager.update_customer_message_status(customer_user_id, True)

                                # Ghi log
                                sheets_manager.add_message_log(
                                    customer_user_id,
                                    f"Forwarded message from admin {user_id}",
                                    'forward_message',
                                    'sent'
                                )

                            else:
                                failed_count += 1

                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Lỗi forward tin nhắn đến user {customer.get('user_id')}: {e}")

                    # Thông báo kết quả
                    await update.message.reply_text(
                        f'✅ **ĐÃ FORWARD TIN NHẮN THÀNH CÔNG!**\n\n'
                        f'**Tin nhắn đã được chuyển tiếp đến:**\n'
                        f'✅ **Thành công:** {forwarded_count} khách hàng\n'
                        f'**Lưu ý:** Tin nhắn đã được forward với định dạng gốc, giữ nguyên emoji động.'
                    )

                else:
                    await update.message.reply_text(
                        '⚠️ **KHÔNG CÓ KHÁCH HÀNG NÀO**\n\n'
                        'Không có khách hàng nào trong hệ thống để forward tin nhắn.',
                    )

            except Exception as e:
                logger.error(f"Lỗi forward tin nhắn: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI FORWARD TIN NHẮN**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng thử lại.',
                )

        elif context.user_data.get('waiting_for_message') and context.user_data.get('message_type') == 'forward_to_channel':
            # Admin đang ở trạng thái chuyển tiếp đến kênh
            print(f"📢 Admin {user_id} đang chuyển tiếp tin nhắn đến kênh")

            # Reset trạng thái
            context.user_data['waiting_for_message'] = False
            context.user_data['message_type'] = None

            # Chuyển tiếp tin nhắn đến tất cả các kênh
            try:
                # Lấy danh sách kênh từ bot_config
                forward_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
                if not forward_channels:
                    await update.message.reply_text(
                        '❌ **LỖI: CHƯA CẤU HÌNH KÊNH**\n\n'
                        'Vui lòng cấu hình FORWARD_CHANNELS trong bot_config.py để sử dụng tính năng này.',
                    )
                    return

                # Chuyển tiếp tin nhắn đến tất cả các kênh
                success_count = 0
                failed_count = 0
                failed_channels = []

                for channel_id in forward_channels:
                    try:
                        await context.bot.forward_message(
                            chat_id=channel_id,
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id
                        )
                        success_count += 1
                        logger.info(f"✅ Đã forward tin nhắn đến kênh {channel_id}")

                    except Exception as e:
                        failed_count += 1
                        failed_channels.append(f"{channel_id} ({str(e)})")
                        logger.error(f"❌ Lỗi copy tin nhắn đến kênh {channel_id}: {e}")

                # Thông báo kết quả
                result_message = '✅ **ĐÃ CHUYỂN TIẾP TIN NHẮN ĐẾN {} KÊNH!**\n\n'.format(len(forward_channels))
                result_message += '**Kết quả:**\n'
                result_message += '✅ **Thành công:** {} kênh\n'.format(success_count)

                if failed_count > 0:
                    result_message += '❌ **Thất bại:** {} kênh\n'.format(failed_count)
                    result_message += '**Kênh lỗi:**\n'
                    for failed in failed_channels[:5]:  # Chỉ hiển thị 5 kênh lỗi đầu tiên
                        result_message += '• {}\n'.format(failed)
                    if len(failed_channels) > 5:
                        result_message += '• ... và {} kênh khác\n'.format(len(failed_channels) - 5)

                result_message += '\n**Lưu ý:** Tin nhắn đã được forward với định dạng gốc, giữ nguyên emoji động.'

                await update.message.reply_text(result_message)

                # Ghi log
                sheets_manager.add_message_log(
                    str(user_id),
                    f"Forwarded message to {success_count}/{len(forward_channels)} channels",
                    'forward_to_channels',
                    'sent'
                )

            except Exception as e:
                logger.error(f"Lỗi chuyển tiếp tin nhắn đến kênh: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI CHUYỂN TIẾP ĐẾN KÊNH**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng kiểm tra:\n'
                    '• FORWARD_CHANNELS có được cấu hình đúng không\n'
                    '• Bot có quyền gửi tin nhắn đến các kênh không\n'
                    '• Các kênh có tồn tại không',
                )

        elif context.user_data.get('waiting_for_message') and context.user_data.get('message_type') == 'forward_to_selected_channels':
            # Admin đang ở trạng thái chuyển tiếp đến các kênh đã chọn
            print(f"🎯 Admin {user_id} đang chuyển tiếp tin nhắn đến các kênh đã chọn")

            # Reset trạng thái
            context.user_data['waiting_for_message'] = False
            context.user_data['message_type'] = None

            # Lấy danh sách kênh đã chọn
            selected_channels = context.user_data.get('selected_channels', [])
            if not selected_channels:
                await update.message.reply_text(
                    '❌ **LỖI: KHÔNG CÓ KÊNH NÀO ĐƯỢC CHỌN**\n\n'
                    'Vui lòng chọn kênh trước khi gửi tin nhắn.',
                )
                return

            # Chuyển tiếp tin nhắn đến các kênh đã chọn
            try:
                success_count = 0
                failed_count = 0
                failed_channels = []

                for channel_id in selected_channels:
                    try:
                        await context.bot.forward_message(
                            chat_id=channel_id,
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id
                        )
                        success_count += 1
                        logger.info(f"✅ Đã forward tin nhắn đến kênh {channel_id}")

                    except Exception as e:
                        failed_count += 1
                        failed_channels.append(f"{channel_id} ({str(e)})")
                        logger.error(f"❌ Lỗi forward tin nhắn đến kênh {channel_id}: {e}")

                # Thông báo kết quả
                result_message = f'✅ **ĐÃ CHUYỂN TIẾP TIN NHẮN ĐẾN {len(selected_channels)} KÊNH ĐÃ CHỌN!**\n\n'
                result_message += '**Kết quả:**\n'
                result_message += f'✅ **Thành công:** {success_count} kênh\n'

                if failed_count > 0:
                    result_message += f'❌ **Thất bại:** {failed_count} kênh\n'
                    result_message += '**Kênh lỗi:**\n'
                    for failed in failed_channels[:5]:  # Chỉ hiển thị 5 kênh lỗi đầu tiên
                        result_message += f'• {failed}\n'
                    if len(failed_channels) > 5:
                        result_message += f'• ... và {len(failed_channels) - 5} kênh khác\n'

                result_message += '\n**Lưu ý:** Tin nhắn đã được forward với định dạng gốc, giữ nguyên emoji động.'

                await update.message.reply_text(result_message)

                # Ghi log
                sheets_manager.add_message_log(
                    str(user_id),
                    f"Forwarded message to {success_count}/{len(selected_channels)} selected channels",
                    'forward_to_selected_channels',
                    'sent'
                )

                # Reset danh sách kênh đã chọn
                context.user_data.pop('selected_channels', None)

            except Exception as e:
                logger.error(f"Lỗi chuyển tiếp tin nhắn đến các kênh đã chọn: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI CHUYỂN TIẾP ĐẾN CÁC KÊNH ĐÃ CHỌN**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng kiểm tra:\n'
                    '• Các kênh có tồn tại không\n'
                    '• Bot có quyền gửi tin nhắn đến các kênh không',
                )

        elif context.user_data.get('waiting_for_channel') and context.user_data.get('action_type') == 'add_channel':
            # Admin đang thêm kênh mới
            print(f"➕ Admin {user_id} đang thêm kênh mới: {update.message.text}")

            # Reset trạng thái
            context.user_data['waiting_for_channel'] = False
            context.user_data['action_type'] = None

            # Xử lý thêm kênh
            try:
                new_channel = update.message.text.strip()

                # Kiểm tra định dạng kênh
                if not (new_channel.startswith('-100') or new_channel.startswith('@')):
                    await update.message.reply_text(
                        '❌ **ĐỊNH DẠNG KÊNH KHÔNG HỢP LỆ!**\n\n'
                        '**Định dạng hợp lệ:**\n'
                        '• ID kênh: `-1001234567890`\n'
                        '• Username: `@channel_name`\n\n'
                        '**Vui lòng thử lại với định dạng đúng:**',
                    )
                    return

                # Lấy danh sách kênh hiện tại
                current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])

                # Kiểm tra kênh đã tồn tại chưa
                if new_channel in current_channels:
                    await update.message.reply_text(
                        f'⚠️ **KÊNH ĐÃ TỒN TẠI!**\n\n'
                        f'Kênh `{new_channel}` đã có trong danh sách.\n'
                        f'**Số kênh hiện tại:** {len(current_channels)}',
                    )
                    return

                # Thêm kênh mới
                current_channels.append(new_channel)
                setattr(bot_config, 'FORWARD_CHANNELS', current_channels)

                # Thông báo thành công
                await update.message.reply_text(
                    f'✅ **ĐÃ THÊM KÊNH THÀNH CÔNG!**\n\n'
                    f'**Kênh mới:** `{new_channel}`\n'
                    f'**Tổng số kênh:** {len(current_channels)}\n\n'
                    f'**Danh sách kênh hiện tại:**\n'
                    f'{chr(10).join([f"• {ch}" for ch in current_channels])}'
                )

                # Ghi log
                sheets_manager.add_message_log(
                    str(user_id),
                    f"Added new channel: {new_channel}",
                    'manage_channels',
                    'success'
                )

            except Exception as e:
                logger.error(f"Lỗi khi thêm kênh: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI THÊM KÊNH**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng thử lại hoặc liên hệ admin.',
                )

        else:
            # Admin gửi tin nhắn bình thường - forward ngay lập tức
            print(f"📝 Admin {user_id} gửi tin nhắn bình thường - forward ngay lập tức")

            # Forward tin nhắn đến tất cả khách hàng
            try:
                customers = sheets_manager.get_all_customers()

                if customers:
                    forwarded_count = 0
                    failed_count = 0

                    for customer in customers:
                        try:
                            customer_user_id = customer.get('user_id')
                            if customer_user_id:
                                # Không gửi lại cho admin đang thao tác
                                if str(customer_user_id) == str(user_id):
                                    print(f"⏭️ Bỏ qua admin {customer_user_id} (không gửi lại cho chính mình)")
                                    continue

                                # Forward tin nhắn (giữ nguyên định dạng gốc, emoji động)
                                await context.bot.forward_message(
                                    chat_id=int(customer_user_id),
                                    from_chat_id=update.effective_chat.id,
                                    message_id=update.message.message_id
                                )
                                forwarded_count += 1

                                # Cập nhật trạng thái trong Google Sheets
                                sheets_manager.update_customer_message_status(customer_user_id, True)

                                # Ghi log
                                sheets_manager.add_message_log(
                                    customer_user_id,
                                    f"Forwarded message from admin {user_id}",
                                    'forward_message',
                                    'sent'
                                )

                            else:
                                failed_count += 1

                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Lỗi forward tin nhắn đến user {customer.get('user_id')}: {e}")

                    # Thông báo kết quả
                    await update.message.reply_text(
                        f'✅ **ĐÃ FORWARD TIN NHẮN THÀNH CÔNG!**\n\n'
                        f'**Tin nhắn đã được chuyển tiếp đến:**\n'
                        f'✅ **Thành công:** {forwarded_count} khách hàng\n'
                        f'❌ **Thất bại:** {failed_count} khách hàng\n\n'
                        f'**Lưu ý:** Tin nhắn đã được forward với định dạng gốc, giữ nguyên emoji động.'
                    )

                else:
                    await update.message.reply_text(
                        '⚠️ **KHÔNG CÓ KHÁCH HÀNG NÀO**\n\n'
                        'Không có khách hàng nào trong hệ thống để forward tin nhắn.',
                    )

            except Exception as e:
                logger.error(f"Lỗi forward tin nhắn: {e}")
                await update.message.reply_text(
                    f'❌ **LỖI KHI FORWARD TIN NHẮN**\n\n'
                    f'Lỗi: {str(e)}\n\n'
                    'Vui lòng thử lại.',
                )

    except Exception as e:
        logger.error(f"Lỗi xử lý tin nhắn text: {e}")
        await update.message.reply_text(
            '❌ **LỖI XỬ LÝ TIN NHẮN**\n\n'
            f'Lỗi: {str(e)}\n\n'
            'Vui lòng thử lại hoặc liên hệ admin.',
        )


def parse_schedule_time(time_input: str) -> Optional[datetime]:
    """
    Parse thời gian hẹn giờ từ input của user với nhiều định dạng khác nhau

    Args:
        time_input: Chuỗi thời gian từ user

    Returns:
        datetime object hoặc None nếu không hợp lệ
    """
    try:
        import re
        from datetime import datetime, timedelta
        import threading

        # Timeout protection for Windows
        def timeout_handler():
            raise TimeoutError("Parse timeout")

        # Set timeout 5 seconds using threading
        timeout_occurred = threading.Event()
        timeout_thread = threading.Timer(5.0, timeout_occurred.set)
        timeout_thread.start()

        try:
            time_input = time_input.strip().lower()
            now = datetime.now()

            # === ĐỊNH DẠNG NGÀY THÁNG NĂM ===

            # DD/MM/YYYY HH:MM hoặc DD-MM-YYYY HH:MM
            date_time_patterns = [
                r'^\d{1,2}[/-]\d{1,2}[/-]\d{4} \d{1,2}:\d{2}$',
                r'^\d{1,2}[/-]\d{1,2}[/-]\d{4} \d{1,2}:\d{2}:\d{2}$'
            ]

            for pattern in date_time_patterns:
                if re.match(pattern, time_input):
                    try:
                        # Thử các format khác nhau
                        formats = ['%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M',
                                   '%d/%m/%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S']
                        for fmt in formats:
                            try:
                                if timeout_occurred.is_set():
                                    raise TimeoutError("Parse timeout")
                                result = datetime.strptime(time_input, fmt)
                                timeout_thread.cancel()  # Cancel timeout
                                return result
                            except ValueError:
                                continue
                    except ValueError:
                        continue

            # === ĐỊNH DẠNG SỐ LIÊN TỤC (COMPACT FORMAT) ===

            # YYYYMMDDHHMMSS (20250906200000) - ưu tiên format này trước
            if re.match(r'^\d{14}$', time_input) and time_input[0:4] >= '2000':
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    # Parse: YYYYMMDDHHMMSS
                    year = int(time_input[0:4])
                    month = int(time_input[4:6])
                    day = int(time_input[6:8])
                    hour = int(time_input[8:10])
                    minute = int(time_input[10:12])
                    second = int(time_input[12:14])

                    result = datetime(year, month, day, hour, minute, second)
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except (ValueError, IndexError):
                    pass

            # DDMMYYYYHHMMSS (06092025200000)
            if re.match(r'^\d{14}$', time_input):
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    # Parse: DDMMYYYYHHMMSS
                    day = int(time_input[0:2])
                    month = int(time_input[2:4])
                    year = int(time_input[4:8])
                    hour = int(time_input[8:10])
                    minute = int(time_input[10:12])
                    second = int(time_input[12:14])

                    result = datetime(year, month, day, hour, minute, second)
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except (ValueError, IndexError):
                    pass

            # YYYYMMDDHHMM (202509062000) - ưu tiên format này trước
            if re.match(r'^\d{12}$', time_input) and time_input[0:4] >= '2000':
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    # Parse: YYYYMMDDHHMM
                    year = int(time_input[0:4])
                    month = int(time_input[4:6])
                    day = int(time_input[6:8])
                    hour = int(time_input[8:10])
                    minute = int(time_input[10:12])

                    result = datetime(year, month, day, hour, minute, 0)
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except (ValueError, IndexError):
                    pass

            # DDMMYYYYHHMM (060920252000)
            if re.match(r'^\d{12}$', time_input):
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    # Parse: DDMMYYYYHHMM
                    day = int(time_input[0:2])
                    month = int(time_input[2:4])
                    year = int(time_input[4:8])
                    hour = int(time_input[8:10])
                    minute = int(time_input[10:12])

                    result = datetime(year, month, day, hour, minute, 0)
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except (ValueError, IndexError):
                    pass

            # YYYY-MM-DD HH:MM (ISO format)
            if re.match(r'^\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{2}$', time_input):
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    result = datetime.strptime(time_input, '%Y-%m-%d %H:%M')
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except ValueError:
                    pass

            # === ĐỊNH DẠNG THỜI GIAN ĐƠN GIẢN ===

            # HH:MM (hôm nay)
            if re.match(r'^\d{1,2}:\d{2}$', time_input):
                try:
                    hour, minute = map(int, time_input.split(':'))
                    schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # Nếu thời gian đã qua trong ngày hôm nay, chuyển sang ngày mai
                    if schedule_time <= now:
                        schedule_time += timedelta(days=1)

                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    timeout_thread.cancel()  # Cancel timeout
                    return schedule_time
                except ValueError:
                    pass

            # === THỜI GIAN TƯƠNG ĐỐI (RELATIVE TIME) ===

            # +N phút/minutes/min
            minute_patterns = [
                r'^\+\s*(\d+)\s*(phút|phut|minute|minutes|min|mins?)$',
                r'^(\d+)\s*(phút|phut|minute|minutes|min|mins?)\s*(nữa|sau|later)$'
            ]

            for pattern in minute_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        minutes = int(match.group(1))
                        result = now + timedelta(minutes=minutes)
                        timeout_thread.cancel()  # Cancel timeout
                        return result
                    except (ValueError, IndexError):
                        pass

            # +N giờ/hours/hour
            hour_patterns = [
                r'^\+\s*(\d+)\s*(giờ|gio|hour|hours|hr|hrs?)$',
                r'^(\d+)\s*(giờ|gio|hour|hours|hr|hrs?)\s*(nữa|sau|later)$'
            ]

            for pattern in hour_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        hours = int(match.group(1))
                        result = now + timedelta(hours=hours)
                        timeout_thread.cancel()  # Cancel timeout
                        return result
                    except (ValueError, IndexError):
                        pass

            # +N ngày/days/day
            day_patterns = [
                r'^\+\s*(\d+)\s*(ngày|ngay|day|days)$',
                r'^(\d+)\s*(ngày|ngay|day|days)\s*(nữa|sau|later)$'
            ]

            for pattern in day_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        days = int(match.group(1))
                        result = now + timedelta(days=days)
                        timeout_thread.cancel()  # Cancel timeout
                        return result
                    except (ValueError, IndexError):
                        pass

            # === NGÔN NGỮ TỰ NHIÊN (NATURAL LANGUAGE) ===

            # Hôm nay + thời gian
            today_patterns = [
                r'^hôm\s+nay\s+(\d{1,2}):(\d{2})$',
                r'^today\s+(\d{1,2}):(\d{2})$',
                r'^hoje\s+(\d{1,2}):(\d{2})$'
            ]

            for pattern in today_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        hour, minute = int(match.group(1)), int(match.group(2))
                        schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if schedule_time <= now:
                            schedule_time += timedelta(days=1)
                        timeout_thread.cancel()  # Cancel timeout
                        return schedule_time
                    except (ValueError, IndexError):
                        pass

            # Ngày mai + thời gian
            tomorrow_patterns = [
                r'^ngày\s+mai\s+(\d{1,2}):(\d{2})$',
                r'^mai\s+(\d{1,2}):(\d{2})$',
                r'^tomorrow\s+(\d{1,2}):(\d{2})$',
                r'^amanhã\s+(\d{1,2}):(\d{2})$'
            ]

            for pattern in tomorrow_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        hour, minute = int(match.group(1)), int(match.group(2))
                        tomorrow = now + timedelta(days=1)
                        result = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        timeout_thread.cancel()  # Cancel timeout
                        return result
                    except (ValueError, IndexError):
                        pass

            # Thời gian trong ngày (sáng, chiều, tối)
            time_of_day_patterns = [
                (r'^sáng\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h, minute=m, second=0, microsecond=0) if h < 12 else None),
                (r'^chiều\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h + 12 if h < 12 else h, minute=m, second=0, microsecond=0)),
                (r'^tối\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h + 12 if h < 12 else h, minute=m, second=0, microsecond=0)),
                (r'^morning\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h, minute=m, second=0, microsecond=0) if h < 12 else None),
                (r'^afternoon\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h + 12 if h < 12 else h, minute=m, second=0, microsecond=0)),
                (r'^evening\s+(\d{1,2}):(\d{2})$', lambda h, m: now.replace(hour=h + 12 if h < 12 else h, minute=m, second=0, microsecond=0))
            ]

            for pattern, time_func in time_of_day_patterns:
                match = re.match(pattern, time_input, re.IGNORECASE)
                if match:
                    try:
                        if timeout_occurred.is_set():
                            raise TimeoutError("Parse timeout")
                        hour, minute = int(match.group(1)), int(match.group(2))
                        schedule_time = time_func(hour, minute)
                        if schedule_time and schedule_time <= now:
                            schedule_time += timedelta(days=1)
                        timeout_thread.cancel()  # Cancel timeout
                        return schedule_time
                    except (ValueError, IndexError):
                        pass

            # === CÁC TRƯỜNG HỢP ĐẶC BIỆT ===

            # "ngay bây giờ", "now", "agora"
            if time_input in ['ngay bây giờ', 'bây giờ', 'now', 'agora', 'immediately']:
                if timeout_occurred.is_set():
                    raise TimeoutError("Parse timeout")
                result = now + timedelta(seconds=10)  # 10 giây sau để tránh conflict
                timeout_thread.cancel()  # Cancel timeout
                return result

            # "1 tiếng nữa", "2 giờ sau"
            if re.match(r'^(\d+)\s*(tiếng|tieng|hour|hours)\s*(nữa|sau|later)$', time_input, re.IGNORECASE):
                try:
                    if timeout_occurred.is_set():
                        raise TimeoutError("Parse timeout")
                    hours = int(re.findall(r'\d+', time_input)[0])
                    result = now + timedelta(hours=hours)
                    timeout_thread.cancel()  # Cancel timeout
                    return result
                except (ValueError, IndexError):
                    pass

            # Cancel timeout if no match found
            timeout_thread.cancel()
            return None

        except TimeoutError:
            logger.error("Timeout khi parse thời gian hẹn giờ")
            return None
        finally:
            # Ensure timeout is always cancelled
            try:
                timeout_thread.cancel()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Lỗi parse thời gian hẹn giờ: {e}")
        return None


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processar callbacks dos botões"""
    try:
        print("🔘 Button handler called!")
        query = update.callback_query
        print(f"🔘 Query data: {query.data}")
        print(f"🔘 User ID: {query.from_user.id}")

        await query.answer()

        # Debug logging
        print(f"🔘 Button clicked: {query.data} by user {query.from_user.id}")
        logger.info(f"Button callback received: {query.data} from user {query.from_user.id}")

        if not query.data:
            logger.error("No callback data received")
            return

        print(f"🔘 Processing callback: {query.data}")

        if query.data == 'promotions':
            # Menu de promoções ABCD.BET
            keyboard = [
                [InlineKeyboardButton('👑 VIP Club',
                                      callback_data='vip_club')],
                [InlineKeyboardButton('🤝 Programa de Referência',
                                      callback_data='referral')],

                [InlineKeyboardButton('💳 Pacotes de Depósito',
                                      callback_data='deposit_packages')],
                [InlineKeyboardButton('🌅 Primeiro Depósito do Dia',
                                      callback_data='daily_first_deposit')],
                [InlineKeyboardButton('🎡 Roda da Fortuna',
                                      callback_data='lucky_wheel')],
                [InlineKeyboardButton('🎰 Roleta VIP',
                                      callback_data='vip_roulette')],
                [InlineKeyboardButton('📱 Baixar App Promocional',
                                      callback_data='download_app')],
                [InlineKeyboardButton('🆘 Compensação de Perda',
                                      callback_data='loss_compensation')],
                [InlineKeyboardButton('⬅️ Voltar',
                                      callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🎁 **Programas Promocionais ABCD.BET**\n\n'
                'Escolha o programa promocional que você gostaria de conhecer:',
                reply_markup=reply_markup
            )

        elif query.data == 'deposit':
            keyboard = [
                [InlineKeyboardButton(
                    '❌ Depósito não creditado',
                    callback_data='deposit_not_credited'
                )],
                [InlineKeyboardButton(
                    '🚫 Não consegue depositar',
                    callback_data='deposit_failed'
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='back'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '💰 **PROBLEMA DE DEPÓSITO**\n\n'
                'Escolha o problema que você está enfrentando:',
                reply_markup=reply_markup,
            )

        elif query.data == 'deposit_not_credited':
            keyboard = [
                [InlineKeyboardButton(
                    '🆘 Atendimento ao cliente online',
                    url=('https://vm.vondokua.com/'
                         '1kdzfz0cdixxg0k59medjggvhv')
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='deposit'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '❌ **DEPÓSITO NÃO CREDITADO**\n\n'
                '💡 **Informação:**\n'
                'Devido ao grande volume de depósitos, o processamento de\n'
                'transações pode estar atrasado.\n\n'
                '⏰ **Tempo de processamento:**\n'
                'Se após 1-10 minutos não foi creditado, entre em contato\n'
                'com o atendimento ao cliente online para orientação\n'
                'específica.\n\n'
                '📞 **Contato de suporte:**\n'
                'Clique em "Atendimento ao cliente online" para obter suporte imediatamente.',
                reply_markup=reply_markup,
            )

        elif query.data == 'withdraw':
            keyboard = [
                [InlineKeyboardButton(
                    '❌ Saque não recebido',
                    callback_data='withdraw_not_received'
                )],
                [InlineKeyboardButton(
                    '🚫 Não consegue sacar',
                    callback_data='withdraw_failed'
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='back'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '💸 **PROBLEMA DE SAQUE**\n\n'
                'Escolha o problema que você está enfrentando:',
                reply_markup=reply_markup,
            )

        elif query.data == 'register':
            # Abrir mini app de cadastro de conta ABCD.BET
            keyboard = [
                [InlineKeyboardButton(
                    '🌐 Abrir página de cadastro',
                    url=('https://www.abcd.bet/v2/index.html?'
                         'appName=0&pid=0&click_id=0&pixel_id=0&t=0#/Center')
                )],
                [InlineKeyboardButton(
                    '📱 Baixar APP ABCD.BET',
                    url='https://www.abcd.bet/app'
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='back'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '📝 **CADASTRAR CONTA ABCDBET**\n\n'
                '🎯 **Bem-vindo ao ABCD.BET!**\n\n'
                '🎁 **PROMOÇÃO DE DEPÓSITO INCRÍVEL:**\n'
                '• 🔥 Presente 100% do valor do primeiro depósito\n'
                '• 💰 Reembolso de 10% todos os dias sem limite\n'
                '• 🎰 Rodadas grátis 50 vezes para jogos de slot\n'
                '• 🏆 Receba R$ 500 imediatamente após cadastro\n\n'
                '📱 **BAIXE O APP ABCD.BET:**\n'
                '• Baixe o app para receber mais R$ 200\n'
                '• Experiência suave e rápida\n'
                '• Atualizações promocionais em tempo real\n\n'
                '🚀 **Comece agora:**\n'
                'Clique em "Abrir página de cadastro" para receber ofertas!',
                reply_markup=reply_markup
            )

        elif query.data == 'support':
            keyboard = [
                [InlineKeyboardButton(
                    '🌐 Abrir Atendimento ao cliente online',
                    url=('https://vm.vondokua.com/'
                         '1kdzfz0cdixxg0k59medjggvhv')
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='back'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🆘 **Atendimento ao Cliente Online**\n\n'
                '🌐 **Link de Suporte:** Clique no botão abaixo para abrir a página de\n'
                'suporte\n\n'
                '👆 **Clique em "Abrir Suporte Online" para acessar agora!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'deposit_failed':
            keyboard = [
                [InlineKeyboardButton(
                    '🆘 Atendimento ao cliente online',
                    url=('https://vm.vondokua.com/'
                         '1kdzfz0cdixxg0k59medjggvhv')
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='deposit'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🚫 **NÃO CONSEGUE DEPOSITAR**\n\n'
                '💡 **Possíveis causas:**\n'
                '• Problemas de conexão com a internet\n'
                '• Limite de cartão atingido\n'
                '• Problemas temporários do sistema\n'
                '• Bloqueio de transação pelo banco\n\n'
                '📞 **Solução:**\n'
                'Entre em contato com o suporte para orientação específica.',
                reply_markup=reply_markup,
            )

        elif query.data == 'withdraw_not_received':
            keyboard = [
                [InlineKeyboardButton(
                    '🆘 Atendimento ao cliente online',
                    url=('https://vm.vondokua.com/'
                         '1kdzfz0cdixxg0k59medjggvhv')
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='withdraw'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '❌ **SAQUE NÃO RECEBIDO**\n\n'
                '💡 **Informação:**\n'
                'O processamento de saques pode levar de 1-24 horas\n'
                'dependendo do método de pagamento escolhido.\n\n'
                '⏰ **Tempo de processamento:**\n'
                '• PIX: 1-2 horas\n'
                '• Transferência bancária: 1-24 horas\n'
                '• Criptomoedas: 1-6 horas\n\n'
                '📞 **Se não recebeu após 24h:**\n'
                'Entre em contato com o suporte imediatamente.',
                reply_markup=reply_markup,
            )

        elif query.data == 'withdraw_failed':
            keyboard = [
                [InlineKeyboardButton(
                    '🆘 Atendimento ao cliente online',
                    url=('https://vm.vondokua.com/'
                         '1kdzfz0cdixxg0k59medjggvhv')
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='withdraw'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🚫 **NÃO CONSEGUE SACAR**\n\n'
                '💡 **Possíveis causas:**\n'
                '• Saldo insuficiente na conta\n'
                '• Limite de saque diário atingido\n'
                '• Conta não verificada\n'
                '• Problemas temporários do sistema\n\n'
                '📞 **Solução:**\n'
                'Entre em contato com o suporte para verificar o status da sua conta.',
                reply_markup=reply_markup,
            )

        elif query.data == 'back':
            # Voltar ao menu principal
            await show_main_menu(update, context)

        elif query.data == 'vip_club':
            # Menu de clube VIP
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '👑 **Clube VIP ABCD.BET**\n\n'
                '🌟 **Participar do clube VIP:**\n\n'
                '📊 **Programa VIP com níveis de Novice até King.**\n'
                'Benefícios crescem a cada nível: prêmios em dinheiro (BRL), '
                'moedas NOW, valor de giros grátis e quantidade de giros '
                'por dia.\n\n'
                '🎯 **Atendimento ao cliente:** começa como Padrão e passa '
                'a Prioridade a partir do nível Platinum.\n\n'
                '💎 **Bônus exclusivo:** vai de 0% nos níveis iniciais '
                'até 60% extra no nível King.\n\n'
                '🏆 **Destaques:**\n\n'
                '🥉 **Bronze:** 25 BRL, 250 NOW, 2 giros/dia.\n\n'
                '🥈 **Silver:** 150 BRL, 1500 NOW, 20% extra.\n\n'
                '🥇 **Gold:** 1000 BRL, 10.000 NOW, 30% extra.\n\n'
                '💎 **Diamond:** 3125 BRL, 31.250 NOW, suporte '
                'prioritário, 50% extra.\n\n'
                '👑 **King:** 25.000 BRL, 250.000 NOW, 3 giros/dia, '
                '60% extra.\n\n'
                '🚀 **Suba de nível VIP e desfrute de benefícios '
                'exclusivos!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'referral':
            # Menu de programa de referência
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🤝 **Programa de Referência ABCD.BET**\n\n'
                '💰 **Convide seus amigos para receber recompensas:**\n\n'
                '➡️ **Compartilhe o link da sua conta com seus amigos para '
                'se registrar e receber os bônus correspondentes! Os detalhes '
                'específicos são os seguintes:**\n\n'
                '✔️ **Convide 1 amigo válido e ganhe R$24,8**\n'
                '✔️ **Convide 5 amigos válidos e ganhe R$158,88**\n\n'
                '➡️ **Como convidar amigos de forma eficaz:**\n\n'
                '✔️ **Seu amigo completa o cadastro da conta e você recebe '
                '0.2 real**\n\n'
                '✔️ **O amigo que você convidar vem até a plataforma para '
                'recarregar 30reais, e você ganhará 9,8 reais.**\n\n'
                '✔️ **O valor total da aposta dos amigos que você convidar '
                'para a plataforma é de R$ 700, e você receberá R$ 14,8.**\n\n'
                '➡️➡️ **5 amigos cadastrados receberão um bônus adicional '
                'de R$ 34,88 💰ao apostar**\n\n'
                '🚀 **Comece a convidar amigos e ganhe recompensas '
                'incríveis!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'deposit_packages':
            # Menu de pacotes de depósito
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '💳 **Pacotes de Depósito ABCD.BET**\n\n'
                '🎁 **Pacote de primeiro depósito:**\n'
                'Por exemplo: Valor máximo de depósito é de 1000 BRL. '
                'Deposite BRL 1000, e ganhe BRL 1000 de bônus.\n\n'
                '🎁 **Pacote de Segundo Depósito:**\n'
                'Por exemplo: Valor máximo de depósito é de 750 BRL. '
                'Deposite BRL 750, e ganhe 375 BRL de bônus.\n\n'
                '🎁 **Pacote de Terceiro Depósito:**\n'
                'Por exemplo: Valor máximo de depósito é de 500 BRL. '
                'Deposite BRL 500, e ganhe 375 BRL de bônus.\n\n'
                '🚀 **Comece agora e aproveite nossos pacotes exclusivos!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'daily_first_deposit':
            # Menu de primeiro depósito do dia
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '💎 **PROMOÇÃO ESPECIAL – DEPOSITE E RECEBA BÔNUS TODOS OS DIAS!** 💎\n\n'
                '👉 **Válido somente para o primeiro depósito do dia na ABCD.BET**\n\n'
                '🔹 **Deposite de R$ 20 a R$ 99** → Bônus de **+2%** diretamente na conta\n'
                '🔹 **Deposite de R$ 100 ou mais** → Bônus de **+3%** extremamente atrativo\n\n'
                '⚡ **O bônus será adicionado automaticamente após o depósito ser efetuado!**\n\n'
                '📌 **Observação importante:**\n\n'
                '• Cada conta pode receber apenas **1 bônus por dia**.\n'
                '• O bônus precisa ser apostado **10 vezes** para ser liberado e pode ser sacado ou continuado jogando.\n\n'
                '🔥 **Não perca a oportunidade de maximizar sua renda diária com a ABCD.BET!**\n\n'
                '⏰ **Cadastre-se agora!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'vip_roulette':
            # Menu de roleta VIP
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🎰 **Roleta VIP ABCD.BET**\n\n'
                '🎯 **Como participar:**\n\n'
                '✅ Basta concluir o cadastro para se tornar um jogador em '
                'nossa plataforma ABCD.BET e você terá a oportunidade de '
                'girar a roleta **uma vez por dia**.\n\n'
                '💳 **Depósito e apostas:**\n'
                'Você pode acessar a plataforma normalmente para depositar '
                'dinheiro e apostar no jogo.\n\n'
                '🚀 **Benefícios VIP:**\n'
                'No futuro, quanto maior for o seu nível VIP, mais vezes '
                'você poderá girar a roleta por dia.\n\n'
                '🎁 **Recompensas VIP:**\n'
                'As recompensas VIP da roleta são alocadas de acordo com '
                'o seu nível VIP. Quanto maior o seu nível, mais rodadas '
                'grátis você pode obter.\n\n'
                '📈 **Upgrades VIP:**\n'
                'À medida que seus upgrades VIP, as recompensas e bônus '
                'na roda da roleta também aumentarão.\n\n'
                '🎯 **Probabilidade:**\n'
                'Você pode obter A probabilidade também é maior, '
                'obrigado!\n\n'
                '🌟 **Comece agora e suba de nível VIP para mais '
                'recompensas!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'download_app':
            # Menu de download do app
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🎉 **FAÇA LOGIN NO EVENTO PARA GANHAR BÔNUS – GANHE R$ 50 AGORA!** 🎉\n\n'
                '👉 **Basta:**\n\n'
                '1️⃣ **Depositar e registrar-se** para participar do evento.\n\n'
                '2️⃣ **Baixar a versão mais recente** do jogo e fazer login continuamente por 3 dias.\n\n'
                '💰 **Recompensas super fáceis:**\n\n'
                '✅ **Dia 1:** Faça login e receba **R$ 10** imediatamente\n\n'
                '✅ **Dia 2:** Continue fazendo login para receber mais **R$ 10**\n\n'
                '✅ **Dia 3:** Faça login com o conjunto completo e receba **R$ 30** imediatamente\n\n'
                '🔥 **No total, você receberá R$ 50 grátis** imediatamente com apenas 3 dias de login!\n\n'
                '⏳ **Corra e participe para não perder a chance!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'lucky_wheel':
            # Menu de roda da fortuna
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🎡 **RODA DA FORTUNA ABCD.BET**\n\n'
                '🎯 **Como participar:**\n\n'
                '✅ **Cadastro automático:** Basta se cadastrar na plataforma ABCD.BET\n'
                '✅ **Acesso diário:** Gire a roda **uma vez por dia** gratuitamente\n'
                '✅ **Sem depósito:** Não é necessário depositar para participar\n\n'
                '🎁 **Prêmios possíveis:**\n\n'
                '💰 **Prêmios em dinheiro:** R$ 5, R$ 10, R$ 20, R$ 50, R$ 100\n'
                '🎰 **Rodadas grátis:** 10x, 25x, 50x, 100x para jogos de slot\n'
                '🎁 **Bônus especiais:** Multiplicadores, cashback, e muito mais\n\n'
                '🚀 **Benefícios VIP:**\n'
                '• Níveis VIP mais altos = mais giros por dia\n'
                '• Prêmios exclusivos para membros VIP\n'
                '• Acesso prioritário a eventos especiais\n\n'
                '⏰ **Horário:** Disponível 24/7\n'
                '🎯 **Probabilidade:** Todos têm chance de ganhar!\n\n'
                '🌟 **Comece agora e teste sua sorte na Roda da Fortuna!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'loss_compensation':
            # Menu de compensação de perda
            keyboard = [
                [InlineKeyboardButton('⬅️ Voltar', callback_data='promotions')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🆘 **Compensação de Perda ABCD.BET**\n\n'
                '📋 **Detalhes da Promoção:**\n\n'
                '1️⃣ **O Acampamento feliz é uma promoção que recompensa '
                'suas perdas no jogo seguindo a tabela acima;**\n\n'
                '2️⃣ **A participação dos membros nas atividades é '
                'registrada automaticamente pelo sistema. Em caso de '
                'disputa, a decisão resultante da consulta com a '
                'ABCDBET prevalecerá;**\n\n'
                '3️⃣ **Se você esquecer a sua conta/senha, você pode '
                'restaurar em {Esquecer senha] na página de log-in ou '
                'entrar em contato com o atendimento ao cliente '
                'on-line 24 horas para ajudá-lo a recuperar as '
                'informações da sua conta;**\n\n'
                '4️⃣ **Participar desta oferta significa concordar com '
                'as Regras e Termos da Oferta.**\n\n'
                '🚀 **Aproveite nossa promoção de compensação e '
                'recupere suas perdas!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'telegram_support':
            keyboard = [
                [InlineKeyboardButton(
                    '📱 Abrir @ABCDBETONLINE',
                    url='https://t.me/ABCDBETONLINE'
                )],
                [InlineKeyboardButton(
                    '⬅️ Voltar',
                    callback_data='back'
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '💬 **Atendimento ao Cliente Telegram**\n\n'
                '🚀 **Conecte-se diretamente com o ABCD Support!**\n\n'
                '📞 **Canal oficial:** @ABCDBETONLINE\n'
                '⏰ **Funcionamento:** 24/7 - Sem parar\n'
                '⚡ **Resposta:** Instantânea e profissional\n'
                '🎯 **Suporte:** Depósito/Saque, Promoções, Dúvidas\n\n'
                '👆 **Clique no botão abaixo para abrir o Telegram agora!**',
                reply_markup=reply_markup,
            )

        elif query.data == 'scheduled_forward':
            # Hiển thị menu hẹn giờ chuyển tiếp
            language = context.user_data.get('language', 'vi')
            keyboard = get_scheduled_forward_menu_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                get_scheduled_forward_title(language),
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif query.data == 'schedule_forward_set':
            # Thiết lập hẹn giờ chuyển tiếp
            language = context.user_data.get('language', 'vi')

            # Đặt trạng thái chờ tin nhắn để hẹn giờ
            context.user_data['waiting_for_schedule_message'] = True
            context.user_data['schedule_forward_type'] = 'all_customers'

            if language == 'vi':
                message = (
                    "⏰ **THIẾT LẬP HẸN GIỜ CHUYỂN TIẾP**\n\n"
                    "📝 Gửi tin nhắn hoặc media mà bạn muốn hẹn giờ chuyển tiếp.\n\n"
                    "💡 **Hướng dẫn:**\n"
                    "• Gửi tin nhắn text để hẹn giờ chuyển tiếp\n"
                    "• Gửi hình ảnh, video, file kèm caption\n"
                    "• Forward tin nhắn từ kênh khác\n\n"
                    "⏰ Sau khi gửi tin nhắn, bạn sẽ được yêu cầu nhập thời gian hẹn giờ."
                )
            else:
                message = (
                    "⏰ **CONFIGURAR ENCAMINHAMENTO AGENDADO**\n\n"
                    "📝 Envie a mensagem ou mídia que deseja agendar para encaminhamento.\n\n"
                    "💡 **Instruções:**\n"
                    "• Envie mensagem de texto para agendar encaminhamento\n"
                    "• Envie imagem, vídeo, arquivo com legenda\n"
                    "• Encaminhe mensagem de outro canal\n\n"
                    "⏰ Após enviar a mensagem, você será solicitado a inserir o horário agendado."
                )

            await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)

        elif query.data == 'schedule_forward_list':
            # Xem danh sách lịch hẹn giờ
            language = context.user_data.get('language', 'vi')
            user_id = query.from_user.id

            try:
                # Lấy danh sách lịch hẹn giờ
                scheduled_forwards = scheduled_forward_manager.get_scheduled_forwards(user_id)

                if not scheduled_forwards:
                    if language == 'vi':
                        message = "📋 **DANH SÁCH LỊCH HẸN GIỜ**\n\n❌ Không có lịch hẹn giờ nào."
                    else:
                        message = "📋 **LISTA DE TAREFAS AGENDADAS**\n\n❌ Nenhuma tarefa agendada."
                else:
                    if language == 'vi':
                        message = f"📋 **DANH SÁCH LỊCH HẸN GIỜ**\n\n📊 Tổng cộng: {len(scheduled_forwards)} lịch hẹn\n\n"
                    else:
                        message = f"📋 **LISTA DE TAREFAS AGENDADAS**\n\n📊 Total: {len(scheduled_forwards)} tarefas\n\n"

                    for i, schedule in enumerate(scheduled_forwards[:10], 1):  # Hiển thị tối đa 10 lịch
                        schedule_time = datetime.fromisoformat(schedule['schedule_time'])
                        status_emoji = {
                            'scheduled': '⏰',
                            'executing': '🔄',
                            'completed': '✅',
                            'failed': '❌',
                            'cancelled': '🚫'
                        }.get(schedule['status'], '❓')

                        if language == 'vi':
                            message += (
                                f"{i}. {status_emoji} **{schedule_time.strftime('%d/%m/%Y %H:%M')}**\n"
                                f"   📝 Loại: {schedule['forward_type']}\n"
                                f"   📊 Trạng thái: {schedule['status']}\n\n"
                            )
                        else:
                            message += (
                                f"{i}. {status_emoji} **{schedule_time.strftime('%d/%m/%Y %H:%M')}**\n"
                                f"   📝 Tipo: {schedule['forward_type']}\n"
                                f"   📊 Status: {schedule['status']}\n\n"
                            )

                    if len(scheduled_forwards) > 10:
                        if language == 'vi':
                            message += f"... và {len(scheduled_forwards) - 10} lịch hẹn khác"
                        else:
                            message += f"... e mais {len(scheduled_forwards) - 10} tarefas"

                # Thêm nút quay lại
                keyboard = [[InlineKeyboardButton('⬅️ Quay lại' if language == 'vi' else '⬅️ Voltar', callback_data='scheduled_forward')]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )

            except Exception as e:
                logger.error(f"Lỗi lấy danh sách lịch hẹn giờ: {e}")
                error_message = f"❌ **LỖI**\n\nLỗi: {str(e)}" if language == 'vi' else f"❌ **ERRO**\n\nErro: {str(e)}"
                await query.edit_message_text(error_message)

        elif query.data == 'schedule_forward_stats':
            # Thống kê lịch hẹn giờ
            language = context.user_data.get('language', 'vi')

            try:
                stats = scheduled_forward_manager.get_schedule_stats()

                if language == 'vi':
                    message = (
                        "📊 **THỐNG KÊ LỊCH HẸN GIỜ**\n\n"
                        f"📈 **Tổng quan:**\n"
                        f"• 📋 Tổng cộng: {stats['total']}\n"
                        f"• ⏰ Đang chờ: {stats['scheduled']}\n"
                        f"• 🔄 Đang thực hiện: {stats['running']}\n"
                        f"• ✅ Hoàn thành: {stats['completed']}\n"
                        f"• ❌ Thất bại: {stats['failed']}\n"
                        f"• 🚫 Đã hủy: {stats['cancelled']}\n\n"
                        f"💡 **Tỷ lệ thành công:** {stats['completed'] / (stats['total'] or 1) * 100:.1f}%"
                    )
                else:
                    message = (
                        "📊 **ESTATÍSTICAS DE TAREFAS AGENDADAS**\n\n"
                        f"📈 **Visão geral:**\n"
                        f"• 📋 Total: {stats['total']}\n"
                        f"• ⏰ Agendadas: {stats['scheduled']}\n"
                        f"• 🔄 Executando: {stats['running']}\n"
                        f"• ✅ Concluídas: {stats['completed']}\n"
                        f"• ❌ Falharam: {stats['failed']}\n"
                        f"• 🚫 Canceladas: {stats['cancelled']}\n\n"
                        f"💡 **Taxa de sucesso:** {stats['completed'] / (stats['total'] or 1) * 100:.1f}%"
                    )

                # Thêm nút quay lại
                keyboard = [[InlineKeyboardButton('⬅️ Quay lại' if language == 'vi' else '⬅️ Voltar', callback_data='scheduled_forward')]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )

            except Exception as e:
                logger.error(f"Lỗi lấy thống kê lịch hẹn giờ: {e}")
                error_message = f"❌ **LỖI**\n\nLỗi: {str(e)}" if language == 'vi' else f"❌ **ERRO**\n\nErro: {str(e)}"
                await query.edit_message_text(error_message)

        elif query.data == 'bulk_back':
            # Quay lại menu "HỆ THỐNG GỬI TIN NHẮN HÀNG LOẠT"
            language = context.user_data.get('bulk_language', 'vi')
            keyboard = get_bulk_messaging_menu_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                get_bulk_messaging_title(language),
                reply_markup=reply_markup,
            )

        elif query.data.startswith('cmd_'):
            # Xử lý các callback command nhanh
            command = query.data.split('_')[1]

            # Tạo fake update để gọi command handler
            fake_update = Update(
                update_id=query.update_id,
                callback_query=query
            )

            # Thực thi command tương ứng
            if command == 'start':
                await start(fake_update, context)
            elif command == 'help':
                # Gọi help command trực tiếp
                await fake_update.message.reply_text(
                    '🤖 **ABCDBET Customer Service Bot - Ajuda**\n\n'
                    '📋 **Comandos principais:**\n'
                    '/start - 🚀 Iniciar bot\n'
                    '/help - ❓ Ajuda e comandos\n'
                    '/menu - 📋 Menu Principal\n'
                    '/commands - 📋 Lista de comandos\n'
                    '/quick - ⚡ Comandos rápidos\n'
                    '/hint - 💡 Dicas de comandos\n\n'
                    '🎁 **Promoções e Bônus:**\n'
                    '/promotions - 🎁 Promoções e bônus\n'
                    '/deposit_packages - 💳 Pacotes de Depósito\n'
                    '/daily_first_deposit - 🌅 Primeiro Depósito do Dia\n'
                    '/vip - 👑 VIP Club\n'
                    '/referral - 🤝 Programa de Referência\n'
                    '/lucky_wheel - 🎡 Roda da Fortuna\n'
                    '/vip_roulette - 🎰 Roleta VIP\n\n'
                    '💰 **Depósito e Saque:**\n'
                    '/register - 📝 Cadastrar Conta\n'
                    '/deposit - 💰 Problema de Depósito\n'
                    '/withdraw - 💸 Problema de Saque\n'
                    '/status - 📊 Status da Conta\n\n'
                    '🆘 **Suporte e Informações:**\n'
                    '/support - 🆘 Suporte ao Cliente\n'
                    '/rules - 📜 Regras e Termos\n'
                    '/faq - ❓ Perguntas Frequentes\n'
                    '/contact - 📞 Contato Direto\n\n'
                    '🌐 **Configurações:**\n'
                    '/language - 🌐 Alterar Idioma\n'
                    '/download_app - 📱 Baixar App\n\n'
                    '🔐 **Lệnh Admin (chỉ dành cho admin):**\n'
                    '/bulk - 📢 Gửi tin nhắn hàng loạt\n'
                    '/manage_channels - ⚙️ Quản lý kênh chuyển tiếp\n'
                    '/stats - 📊 Xem thống kê khách hàng\n'
                    '/stop_bulk - 🛑 Dừng gửi tin nhắn hàng loạt\n'
                    '/reload - 🔄 Reload bot (Admin only)\n'
                    '/health - 🏥 Kiểm tra sức khỏe bot (Admin only)\n\n'
                    '💡 **Dica:** Use os botões do menu para navegar facilmente!\n'
                    '🔍 **Dica:** Digite / seguido do comando para usar qualquer função!'
                )
            elif command == 'menu':
                await show_main_menu(fake_update, context)
            elif command == 'commands':
                # Gọi commands list trực tiếp
                commands_text = (
                    '📋 **LISTA COMPLETA DE COMANDOS**\n\n'
                    '🚀 **COMANDOS PRINCIPAIS:**\n'
                    '• `/start` - Iniciar bot\n'
                    '• `/help` - Ajuda e comandos\n'
                    '• `/menu` - Menu Principal\n'
                    '• `/commands` - Esta lista de comandos\n\n'
                    '🎁 **PROMOÇÕES E BÔNUS:**\n'
                    '• `/promotions` - Promoções e bônus\n'
                    '• `/deposit_packages` - Pacotes de Depósito\n'
                    '• `/daily_first_deposit` - Primeiro Depósito do Dia\n'
                    '• `/vip` - VIP Club\n'
                    '• `/referral` - Programa de Referência\n'
                    '• `/lucky_wheel` - Roda da Fortuna\n'
                    '• `/vip_roulette` - Roleta VIP\n\n'
                    '💰 **DEPÓSITO E SAQUE:**\n'
                    '• `/register` - Cadastrar Conta\n'
                    '• `/deposit` - Problema de Depósito\n'
                    '• `/withdraw` - Problema de Saque\n'
                    '• `/status` - Status da Conta\n\n'
                    '🆘 **SUPORTE E INFORMAÇÕES:**\n'
                    '• `/support` - Suporte ao Cliente\n'
                    '• `/rules` - Regras e Termos\n'
                    '• `/faq` - Perguntas Frequentes\n'
                    '• `/contact` - Contato Direto\n\n'
                    '🌐 **CONFIGURAÇÕES:**\n'
                    '• `/language` - Alterar Idioma\n'
                    '• `/download_app` - Baixar App\n\n'
                    '🔐 **COMANDOS ADMIN:**\n'
                    '• `/bulk` - Gửi tin nhắn hàng loạt\n'
                    '• `/manage_channels` - Quản lý kênh\n'
                    '• `/stats` - Thống kê khách hàng\n'
                    '• `/stop_bulk` - Dừng gửi tin nhắn\n\n'
                    '💡 **DICA:** Digite `/` seguido do comando para usar qualquer função!\n'
                    '📱 **EXEMPLO:** `/vip`, `/status`, `/rules`'
                )
                await fake_update.message.reply_text(commands_text)
            elif command == 'promotions':
                # Gọi promotions trực tiếp
                keyboard = [
                    [InlineKeyboardButton('👑 VIP Club', callback_data='vip_club')],
                    [InlineKeyboardButton('🤝 Programa de Referência', callback_data='referral')],
                    [InlineKeyboardButton('💳 Pacotes de Depósito', callback_data='deposit_packages')],
                    [InlineKeyboardButton('🌅 Primeiro Depósito do Dia', callback_data='daily_first_deposit')],
                    [InlineKeyboardButton('🎡 Roda da Fortuna', callback_data='lucky_wheel')],
                    [InlineKeyboardButton('🎰 Roleta VIP', callback_data='vip_roulette')],
                    [InlineKeyboardButton('📱 Baixe o aplicativo de promoção', callback_data='download_app')],
                    [InlineKeyboardButton('🆘 Compensação de Perda', callback_data='loss_compensation')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '🎁 **Programas Promocionais ABCD.BET**\n\n'
                    'Escolha o programa promocional que você gostaria de conhecer:',
                    reply_markup=reply_markup
                )
            elif command == 'vip':
                # Gọi VIP trực tiếp
                keyboard = [
                    [InlineKeyboardButton('👑 VIP Club', callback_data='vip_club')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '👑 **VIP Club ABCD.BET**\n\n'
                    'Bem-vindo ao programa VIP exclusivo!',
                    reply_markup=reply_markup
                )
            elif command == 'deposit':
                # Gọi deposit trực tiếp
                keyboard = [
                    [InlineKeyboardButton('💳 Problema de Depósito', callback_data='deposit_issue')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '💰 **Problema de Depósito**\n\n'
                    'Como podemos ajudá-lo com seu depósito?',
                    reply_markup=reply_markup
                )
            elif command == 'withdraw':
                # Gọi withdraw trực tiếp
                keyboard = [
                    [InlineKeyboardButton('💸 Problema de Saque', callback_data='withdraw_issue')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '💸 **Problema de Saque**\n\n'
                    'Como podemos ajudá-lo com seu saque?',
                    reply_markup=reply_markup
                )
            elif command == 'register':
                # Gọi register trực tiếp
                keyboard = [
                    [InlineKeyboardButton('📝 Cadastrar Conta', callback_data='register_account')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '📝 **Cadastrar Conta**\n\n'
                    'Vamos ajudá-lo a criar sua conta!',
                    reply_markup=reply_markup
                )
            elif command == 'status':
                # Gọi status trực tiếp
                keyboard = [
                    [InlineKeyboardButton('📊 Status da Conta', callback_data='account_status')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '📊 **Status da Conta**\n\n'
                    'Verifique o status da sua conta!',
                    reply_markup=reply_markup
                )
            elif command == 'support':
                # Gọi support trực tiếp
                keyboard = [
                    [InlineKeyboardButton('🆘 Suporte ao Cliente', callback_data='customer_support')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '🆘 **Suporte ao Cliente**\n\n'
                    'Como podemos ajudá-lo?',
                    reply_markup=reply_markup
                )
            elif command == 'rules':
                # Gọi rules trực tiếp
                keyboard = [
                    [InlineKeyboardButton('📜 Regras e Termos', callback_data='rules_terms')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '📜 **Regras e Termos**\n\n'
                    'Leia nossas regras e termos!',
                    reply_markup=reply_markup
                )
            elif command == 'faq':
                # Gọi FAQ trực tiếp
                keyboard = [
                    [InlineKeyboardButton('❓ Perguntas Frequentes', callback_data='faq_questions')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '❓ **Perguntas Frequentes**\n\n'
                    'Encontre respostas para suas dúvidas!',
                    reply_markup=reply_markup
                )
            elif command == 'contact':
                # Gọi contact trực tiếp
                keyboard = [
                    [InlineKeyboardButton('📞 Contato Direto', callback_data='direct_contact')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '📞 **Contato Direto**\n\n'
                    'Entre em contato conosco!',
                    reply_markup=reply_markup
                )
            elif command == 'language':
                # Gọi language trực tiếp
                keyboard = [
                    [InlineKeyboardButton('🇻🇳 Tiếng Việt', callback_data='lang_vi')],
                    [InlineKeyboardButton('🇨🇳 Tiếng Trung', callback_data='lang_zh')],
                    [InlineKeyboardButton('🇺🇸 Tiếng Anh', callback_data='lang_en')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '🌐 **Alterar Idioma**\n\n'
                    'Chọn ngôn ngữ của bạn:',
                    reply_markup=reply_markup
                )
            elif command == 'download':
                # Gọi download app trực tiếp
                keyboard = [
                    [InlineKeyboardButton('📱 Baixar App', callback_data='download_app')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '📱 **Baixar App**\n\n'
                    'Baixe nosso aplicativo!',
                    reply_markup=reply_markup
                )
            elif command == 'lucky_wheel':
                # Gọi lucky wheel trực tiếp
                keyboard = [
                    [InlineKeyboardButton('🎡 Roda da Fortuna', callback_data='lucky_wheel')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '🎡 **Roda da Fortuna**\n\n'
                    'Gire a roda da fortuna!',
                    reply_markup=reply_markup
                )
            elif command == 'vip_roulette':
                # Gọi VIP roulette trực tiếp
                keyboard = [
                    [InlineKeyboardButton('🎰 Roleta VIP', callback_data='vip_roulette')],
                    [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await fake_update.message.reply_text(
                    '🎰 **Roleta VIP**\n\n'
                    'Jogue a roleta VIP!',
                    reply_markup=reply_markup
                )
            else:
                await query.answer(f"❌ Lệnh '{command}' không được hỗ trợ!")

        elif query.data == 'bulk_language':
            # Menu chọn ngôn ngữ cho bulk messaging
            keyboard = [
                [InlineKeyboardButton('🇻🇳 Tiếng Việt', callback_data='bulk_lang_vi')],
                [InlineKeyboardButton('🇨🇳 Tiếng Trung giản thể', callback_data='bulk_lang_zh')],
                [InlineKeyboardButton('🇺🇸 Tiếng Anh', callback_data='bulk_lang_en')],
                [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                '🌐 **CHỌN NGÔN NGỮ CHO HỆ THỐNG BULK MESSAGING**\n\n'
                'Chọn ngôn ngữ bạn muốn sử dụng:',
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_lang_vi':
            # Đặt ngôn ngữ tiếng Việt
            context.user_data['bulk_language'] = 'vi'
            await query.answer('✅ Đã chọn ngôn ngữ: Tiếng Việt')

            # Cập nhật admin commands theo ngôn ngữ mới
            await update_admin_commands_for_user(context, 'vi')

            # Quay lại menu chính với ngôn ngữ tiếng Việt
            keyboard = get_bulk_messaging_menu_keyboard('vi')
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                get_bulk_messaging_title('vi'),
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_lang_zh':
            # Đặt ngôn ngữ tiếng Trung
            context.user_data['bulk_language'] = 'zh'
            await query.answer('✅ 已选择语言: 简体中文')

            # Cập nhật admin commands theo ngôn ngữ mới
            await update_admin_commands_for_user(context, 'zh')

            # Quay lại menu chính với ngôn ngữ tiếng Trung
            keyboard = get_bulk_messaging_menu_keyboard('zh')
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                get_bulk_messaging_title('zh'),
                reply_markup=reply_markup,
            )

        elif query.data == 'bulk_lang_en':
            # Đặt ngôn ngữ tiếng Anh
            context.user_data['bulk_language'] = 'en'
            await query.answer('✅ Language selected: English')

            # Cập nhật admin commands theo ngôn ngữ mới
            await update_admin_commands_for_user(context, 'en')

            # Quay lại menu chính với ngôn ngữ tiếng Anh
            keyboard = get_bulk_messaging_menu_keyboard('en')
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                get_bulk_messaging_title('en'),
                reply_markup=reply_markup,
            )

        elif query.data.startswith('bulk_'):            # Xử lý các callback cho chức năng gửi tin nhắn hàng loạt
            await handle_bulk_messaging_callbacks(query, context)

        elif query.data == 'manage_channels':
            # Debug logging
            print(f"🔧 manage_channels callback received from user {query.from_user.id}")
            logger.info(f"manage_channels callback received from user {query.from_user.id}")

            # Kiểm tra quyền admin
            if query.from_user.id not in bot_config.ADMIN_USER_IDS:
                await query.answer("❌ Bạn không có quyền sử dụng chức năng này!", show_alert=True)
                return

            # Menu quản lý kênh
            current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
            channel_count = len(current_channels)

            # Lấy ngôn ngữ hiện tại
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                keyboard = [
                    [InlineKeyboardButton('➕ 添加新频道', callback_data='add_channel')],
                    [InlineKeyboardButton('📋 查看频道列表', callback_data='list_channels')],
                    [InlineKeyboardButton('❌ 删除频道', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
                ]
                title = f'⚙️ **频道管理**\n\n📊 **当前统计:**\n• 总频道数: {channel_count}\n• 状态: ✅ 活跃\n\n**选择您要使用的功能:**'
            elif language == 'en':
                keyboard = [
                    [InlineKeyboardButton('➕ Add new channel', callback_data='add_channel')],
                    [InlineKeyboardButton('📋 View channel list', callback_data='list_channels')],
                    [InlineKeyboardButton('❌ Delete channel', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
                ]
                title = f'⚙️ **CHANNEL MANAGEMENT**\n\n📊 **Current statistics:**\n• Total channels: {channel_count}\n• Status: ✅ Active\n\n**Select the function you want to use:**'
            else:
                keyboard = [
                    [InlineKeyboardButton('➕ Thêm kênh mới', callback_data='add_channel')],
                    [InlineKeyboardButton('📋 Xem danh sách kênh', callback_data='list_channels')],
                    [InlineKeyboardButton('❌ Xóa kênh', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
                ]
                title = f'⚙️ **QUẢN LÝ KÊNH CHUYỂN TIẾP**\n\n📊 **Thống kê hiện tại:**\n• Tổng số kênh: {channel_count}\n• Trạng thái: ✅ Hoạt động\n\n**Chọn chức năng bạn muốn sử dụng:**'

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                title,
                reply_markup=reply_markup,
            )

        elif query.data == 'select_channels_to_send':
            # Chọn kênh để gửi tin nhắn
            user_id = query.from_user.id

            # Kiểm tra quyền admin
            if user_id not in bot_config.ADMIN_USER_IDS:
                await query.answer("❌ Bạn không có quyền sử dụng chức năng này!", show_alert=True)
                return

            # Lấy danh sách kênh hiện tại
            all_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])

            if not all_channels:
                await query.edit_message_text(
                    "❌ **KHÔNG CÓ KÊNH NÀO**\n\n"
                    "Chưa có kênh nào được cấu hình.\n"
                    "Hãy thêm kênh trước khi sử dụng tính năng này.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Quay lại", callback_data="manage_channels")
                    ]])
                )
                return

            # Tạo keyboard chọn kênh
            keyboard = create_channel_selection_keyboard(user_id)

            # Lấy ngôn ngữ hiện tại
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = f"🎯 **选择频道发送消息**\n\n📊 **当前统计:**\n• 总频道数: {len(all_channels)}\n• 已选择: 0\n\n**请选择要发送消息的频道:**"
            elif language == 'en':
                title = f"🎯 **SELECT CHANNELS TO SEND MESSAGE**\n\n📊 **Current statistics:**\n• Total channels: {len(all_channels)}\n• Selected: 0\n\n**Please select channels to send message:**"
            else:
                title = f"🎯 **CHỌN KÊNH GỬI TIN NHẮN**\n\n📊 **Thống kê hiện tại:**\n• Tổng số kênh: {len(all_channels)}\n• Đã chọn: 0\n\n**Hãy chọn các kênh bạn muốn gửi tin nhắn:**"

            await query.edit_message_text(
                title,
                reply_markup=keyboard
            )

        elif query.data == 'add_channel':
            # Thêm kênh mới
            language = context.user_data.get('bulk_language', 'vi')

            if language == 'zh':
                title = '➕ **添加新频道**\n\n**说明:**\n• 发送频道ID (例如: -1001234567890)\n• 或发送频道用户名 (例如: @channel_name)\n• 机器人将自动添加到列表\n\n**注意:** 机器人必须是频道的管理员才能转发消息!\n\n**请发送频道ID或用户名:**'
                back_button = InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')
            elif language == 'en':
                title = '➕ **ADD NEW CHANNEL**\n\n**Instructions:**\n• Send channel ID (e.g., -1001234567890)\n• Or send channel username (e.g., @channel_name)\n• Bot will automatically add to the list\n\n**Note:** Bot must be admin of the channel to forward messages!\n\n**Please send channel ID or username:**'
                back_button = InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')
            else:
                title = '➕ **THÊM KÊNH MỚI**\n\n**Hướng dẫn:**\n• Gửi ID kênh \\(ví dụ: \\-1001234567890\\)\n• Hoặc gửi username kênh \\(ví dụ: @channel\\_name\\)\n• Bot sẽ tự động thêm vào danh sách\n\n**Lưu ý:** Bot phải là admin của kênh để có thể chuyển tiếp tin nhắn\\!\n\n**Hãy gửi ID hoặc username kênh:**'
                back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')

            await query.edit_message_text(
                title,
                reply_markup=InlineKeyboardMarkup([[back_button]])
            )

            # Đặt trạng thái chờ thêm kênh
            context.user_data['waiting_for_channel'] = True
            context.user_data['action_type'] = 'add_channel'

        elif query.data == 'list_channels':
            # Hiển thị danh sách kênh
            current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
            language = context.user_data.get('bulk_language', 'vi')

            if current_channels:
                if language == 'zh':
                    channel_list = '📋 **当前频道列表:**\n\n'
                    for i, channel_id in enumerate(current_channels, 1):
                        channel_list += f'{i}. `{channel_id}`\n'
                    channel_list += f'\n**总计:** {len(current_channels)} 个频道'
                elif language == 'en':
                    channel_list = '📋 **CURRENT CHANNEL LIST:**\n\n'
                    for i, channel_id in enumerate(current_channels, 1):
                        channel_list += f'{i}. `{channel_id}`\n'
                    channel_list += f'\n**Total:** {len(current_channels)} channels'
                else:
                    channel_list = '📋 **DANH SÁCH KÊNH HIỆN TẠI:**\n\n'
                    for i, channel_id in enumerate(current_channels, 1):
                        channel_list += f'{i}. `{channel_id}`\n'
                    channel_list += f'\n**Tổng cộng:** {len(current_channels)} kênh'
            else:
                if language == 'zh':
                    channel_list = '📋 **频道列表:**\n\n❌ 还没有添加任何频道'
                elif language == 'en':
                    channel_list = '📋 **CHANNEL LIST:**\n\n❌ No channels have been added yet'
                else:
                    channel_list = '📋 **DANH SÁCH KÊNH:**\n\n❌ Chưa có kênh nào được thêm'

            if language == 'zh':
                keyboard = [
                    [InlineKeyboardButton('➕ 添加新频道', callback_data='add_channel')],
                    [InlineKeyboardButton('❌ 删除频道', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')]
                ]
            elif language == 'en':
                keyboard = [
                    [InlineKeyboardButton('➕ Add new channel', callback_data='add_channel')],
                    [InlineKeyboardButton('❌ Delete channel', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton('➕ Thêm kênh mới', callback_data='add_channel')],
                    [InlineKeyboardButton('❌ Xóa kênh', callback_data='remove_channel')],
                    [InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')]
                ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                channel_list,
                reply_markup=reply_markup,
            )

        elif query.data == 'remove_channel':
            # Xóa kênh
            current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
            language = context.user_data.get('bulk_language', 'vi')

            if not current_channels:
                if language == 'zh':
                    title = '❌ **删除频道**\n\n❌ 没有频道可以删除!'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')
                elif language == 'en':
                    title = '❌ **DELETE CHANNEL**\n\n❌ No channels to delete!'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')
                else:
                    title = '❌ **XÓA KÊNH**\n\n❌ Không có kênh nào để xóa!'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')

                await query.edit_message_text(
                    title,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )
                return

            # Tạo danh sách kênh để chọn xóa
            keyboard = []
            for i, channel_id in enumerate(current_channels):
                keyboard.append([InlineKeyboardButton(
                    f'❌ {i + 1}. {channel_id}',
                    callback_data=f'delete_channel_{i}'
                )])

            if language == 'zh':
                keyboard.append([InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')])
            elif language == 'en':
                keyboard.append([InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')])
            else:
                keyboard.append([InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')])

            reply_markup = InlineKeyboardMarkup(keyboard)

            if language == 'zh':
                title = '❌ **删除频道**\n\n**选择您要删除的频道:**\n⚠️ **注意:** 此操作无法撤销!'
            elif language == 'en':
                title = '❌ **DELETE CHANNEL**\n\n**Select the channel you want to delete:**\n⚠️ **Warning:** This action cannot be undone!'
            else:
                title = '❌ **XÓA KÊNH**\n\n**Chọn kênh bạn muốn xóa:**\n⚠️ **Lưu ý:** Hành động này không thể hoàn tác!'

            await query.edit_message_text(
                title,
                reply_markup=reply_markup,
            )

        elif query.data.startswith('delete_channel_'):
            # Xóa kênh cụ thể
            try:
                channel_index = int(query.data.split('_')[2])
                current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])

                if 0 <= channel_index < len(current_channels):
                    deleted_channel = current_channels[channel_index]

                    # Xóa kênh khỏi danh sách
                    current_channels.pop(channel_index)

                    # Cập nhật bot_config
                    setattr(bot_config, 'FORWARD_CHANNELS', current_channels)

                    language = context.user_data.get('bulk_language', 'vi')

                    if language == 'zh':
                        success_message = f'✅ **频道删除成功!**\n\n**已删除的频道:** `{deleted_channel}`\n**剩余频道数:** {len(current_channels)}\n\n**新频道列表:**\n' + ('\n'.join([f'• {ch}' for ch in current_channels]) if current_channels else '❌ 没有剩余频道')
                        back_button = InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')
                    elif language == 'en':
                        success_message = f'✅ **CHANNEL DELETED SUCCESSFULLY!**\n\n**Deleted channel:** `{deleted_channel}`\n**Remaining channels:** {len(current_channels)}\n\n**New channel list:**\n' + ('\n'.join([f'• {ch}' for ch in current_channels]) if current_channels else '❌ No channels remaining')
                        back_button = InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')
                    else:
                        success_message = f'✅ **ĐÃ XÓA KÊNH THÀNH CÔNG!**\n\n**Kênh đã xóa:** `{deleted_channel}`\n**Số kênh còn lại:** {len(current_channels)}\n\n**Danh sách kênh mới:**\n' + ('\n'.join([f'• {ch}' for ch in current_channels]) if current_channels else '❌ Không còn kênh nào')
                        back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')

                    await query.edit_message_text(
                        success_message,
                        reply_markup=InlineKeyboardMarkup([[back_button]])
                    )
                else:
                    if language == 'zh':
                        error_message = '❌ **错误:** 频道索引无效!'
                        back_button = InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')
                    elif language == 'en':
                        error_message = '❌ **ERROR:** Invalid channel index!'
                        back_button = InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')
                    else:
                        error_message = '❌ **LỖI:** Index kênh không hợp lệ!'
                        back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')

                    await query.edit_message_text(
                        error_message,
                        reply_markup=InlineKeyboardMarkup([[back_button]])
                    )
            except Exception as e:
                logger.error(f"Lỗi khi xóa kênh: {e}")
                language = context.user_data.get('bulk_language', 'vi')

                if language == 'zh':
                    error_message = f'❌ **删除频道时出错**\n\n错误: {str(e)}'
                    back_button = InlineKeyboardButton('⬅️ 返回', callback_data='manage_channels')
                elif language == 'en':
                    error_message = f'❌ **ERROR DELETING CHANNEL**\n\nError: {str(e)}'
                    back_button = InlineKeyboardButton('⬅️ Back', callback_data='manage_channels')
                else:
                    error_message = f'❌ **LỖI KHI XÓA KÊNH**\n\nLỗi: {str(e)}'
                    back_button = InlineKeyboardButton('⬅️ Quay lại', callback_data='manage_channels')

                await query.edit_message_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup([[back_button]])
                )

        elif query.data == 'confirm_forward':
            # Kiểm tra quyền admin
            user_id = query.from_user.id
            if user_id not in bot_config.ADMIN_USER_IDS:
                await query.edit_message_text('❌ Bạn không có quyền thực hiện hành động này.')
                return

            pending = context.user_data.get('pending_forward')
            if not pending:
                await query.edit_message_text('⚠️ Không có tác vụ chuyển tiếp nào đang chờ.')
                return

            await query.edit_message_text('⏳ Đang chuyển tiếp media đến các kênh...')
            # Thực hiện forward
            success = 0
            failed = 0
            failed_channels = []
            forward_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
            for channel_id in forward_channels:
                try:
                    await context.bot.forward_message(
                        chat_id=channel_id,
                        from_chat_id=pending['chat_id'],
                        message_id=pending['message_id']
                    )
                    success += 1
                except Exception as e:
                    failed += 1
                    failed_channels.append(f"{channel_id} ({e})")

            # Báo kết quả
            result = f"✅ Hoàn thành: {success} thành công, {failed} thất bại."
            if failed:
                result += "\nKênh lỗi:\n" + '\n'.join(failed_channels[:5])

            await query.edit_message_text(result)

            # Ghi log và reset trạng thái
            sheets_manager.add_message_log(str(user_id), f"Forwarded media to {success}/{len(forward_channels)} channels", 'forward_media_to_channels', 'sent')
            context.user_data.pop('waiting_for_confirmation', None)
            context.user_data.pop('pending_forward', None)
            return

        elif query.data == 'cancel_forward':
            # Hủy tác vụ
            context.user_data.pop('waiting_for_confirmation', None)
            context.user_data.pop('pending_forward', None)
            await query.edit_message_text('❎ Đã hủy tác vụ chuyển tiếp.')
            return

        # ===== XỬ LÝ CHỌN KÊNH GỬI =====
        elif query.data == 'select_all_channels':
            # Chọn tất cả kênh
            user_id = query.from_user.id
            selected_channels = select_all_channels(user_id)

            await query.answer(f"✅ Đã chọn {len(selected_channels)} kênh")

            # Cập nhật keyboard
            keyboard = create_channel_selection_keyboard(user_id)
            await query.edit_message_reply_markup(reply_markup=keyboard)

        elif query.data == 'deselect_all_channels':
            # Bỏ chọn tất cả kênh
            user_id = query.from_user.id
            selected_channels = deselect_all_channels(user_id)

            await query.answer("🔴 Đã bỏ chọn tất cả kênh")

            # Cập nhật keyboard
            keyboard = create_channel_selection_keyboard(user_id)
            await query.edit_message_reply_markup(reply_markup=keyboard)

        elif query.data.startswith('toggle_channel:'):
            # Chuyển đổi trạng thái chọn kênh
            user_id = query.from_user.id
            channel_id = query.data.split(':', 1)[1]
            selected_channels = toggle_channel_selection(user_id, channel_id)

            if channel_id in selected_channels:
                await query.answer(f"✅ Đã chọn kênh {channel_id}")
            else:
                await query.answer(f"❌ Đã bỏ chọn kênh {channel_id}")

            # Cập nhật keyboard
            keyboard = create_channel_selection_keyboard(user_id)
            await query.edit_message_reply_markup(reply_markup=keyboard)

        elif query.data == 'confirm_send_to_channels':
            # Xác nhận gửi đến các kênh đã chọn
            user_id = query.from_user.id
            selected_channels = get_admin_selected_channels(user_id)

            if not selected_channels:
                await query.answer("❌ Chưa chọn kênh nào!", show_alert=True)
                return

            # Đặt trạng thái chờ tin nhắn để gửi đến kênh
            context.user_data['waiting_for_message'] = True
            context.user_data['message_type'] = 'forward_to_selected_channels'
            context.user_data['selected_channels'] = selected_channels

            # Tạo nội dung tin nhắn
            channel_list = '\n'.join([f"• {c}" for c in selected_channels[:5]])
            if len(selected_channels) > 5:
                channel_list += f"\n• ... và {len(selected_channels) - 5} kênh khác"

            message_text = (
                f"📢 **GỬI TIN NHẮN ĐẾN {len(selected_channels)} KÊNH ĐÃ CHỌN**\n\n"
                f"**Kênh đã chọn:**\n{channel_list}\n\n"
                "**Bây giờ hãy gửi tin nhắn hoặc media bạn muốn gửi đến các kênh này:**"
            )

            await query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Hủy", callback_data="cancel_channel_selection")
                ]])
            )

        elif query.data == 'cancel_channel_selection':
            # Hủy chọn kênh
            user_id = query.from_user.id
            set_admin_selected_channels(user_id, [])

            await query.answer("❌ Đã hủy chọn kênh")

            # Quay lại menu quản lý kênh
            await query.edit_message_text(
                "❌ **ĐÃ HỦY CHỌN KÊNH**\n\n"
                "Bạn có thể sử dụng lệnh /manage_channels để quản lý kênh.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Quay lại", callback_data="manage_channels")
                ]])
            )

        elif query.data == 'stats_info':
            # Hiển thị thông tin thống kê
            user_id = query.from_user.id
            selected_channels = get_admin_selected_channels(user_id)
            all_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])

            await query.answer(f"📊 Đã chọn {len(selected_channels)}/{len(all_channels)} kênh", show_alert=False)

        elif query.data == 'no_channels':
            # Không có kênh nào
            await query.answer("❌ Chưa có kênh nào được cấu hình!", show_alert=True)

        # ===== XỬ LÝ CÁC CALLBACK KHÁC =====
        else:
            # Opção không được nhận diện
            await query.edit_message_text(
                '❌ Tùy chọn không được nhận diện. Vui lòng chọn một tùy chọn hợp lệ.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton('⬅️ Quay lại Menu', callback_data='back')
                ]])
            )

    except Exception as e:
        logger.error(f"Erro no button_handler: {e}")
        await query.edit_message_text(
            '❌ Ocorreu um erro. Por favor, tente novamente.',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('⬅️ Voltar ao Menu', callback_data='back')
            ]])
        )


def main():
    """Iniciar bot"""
    global current_application

    if not bot_config.TELEGRAM_TOKEN:
        print("❌ Không tìm thấy TELEGRAM_TOKEN trong file .env")
        return

    # Setup signal handlers for graceful restart
    setup_signal_handlers()
    print("🔄 Signal handlers configured for auto-reload")

    # Criar application
    application = Application.builder().token(bot_config.TELEGRAM_TOKEN).build()
    current_application = application

    # KHÔNG gọi init_notification_system(application.bot) trực tiếp trong main()
    # Thay vào đó, dùng post_init để khởi tạo notification system và set lệnh
    # post_init có thể được gọi nhiều nơi, nên chúng ta wrap cả hai hành động vào
    # một hàm duy nhất đảm bảo cả Notification và Bot Commands đều được cấu hình.
    async def post_init_func(app):
        try:
            # Khởi tạo notification system nếu chưa có
            if not get_notification_manager():
                print("🔔 Khởi tạo notification system...")
                init_notification_system(app.bot)

            # Khởi động lại các task hẹn giờ chuyển tiếp
            try:
                print("⏰ Khởi động lại các task hẹn giờ chuyển tiếp...")
                await scheduled_forward_manager.restart_scheduled_tasks()
            except Exception as e:
                logger.error(f"Lỗi khi khởi động lại task hẹn giờ: {e}")
                print(f"Lỗi khi khởi động lại task hẹn giờ: {e}")

            # Đảm bảo các lệnh bot được đặt (cả cơ bản và admin)
            try:
                await set_bot_commands(app)
            except Exception as e:
                logger.error(f"Lỗi khi set bot commands trong post_init: {e}")
                print(f"Lỗi khi set bot commands trong post_init: {e}")
        except Exception as e:
            logger.error(f"Lỗi trong post_init_func: {e}")
            print(f"Lỗi trong post_init_func: {e}")

    application.post_init = post_init_func

    # Configurar comandos sugeridos do bot
    async def set_bot_commands(app):
        """Configurar comandos sugeridos do bot"""
        # Lệnh cơ bản cho tất cả người dùng (KHÔNG chứa lệnh admin)
        basic_commands = [
            ('start', '🚀 Iniciar bot'),
            ('help', '❓ Ajuda e comandos'),
            ('menu', '📋 Menu Principal'),
            ('commands', '📋 Lista de comandos'),
            ('quick', '⚡ Comandos rápidos'),
            ('hint', '💡 Dicas de comandos'),
            ('promotions', '🎁 Promoções e bônus'),
            ('deposit_packages', '💳 Pacotes de Depósito'),
            ('daily_first_deposit', '🌅 Primeiro Depósito do Dia'),
            ('support', '🆘 Suporte ao Cliente'),
            ('register', '📝 Cadastrar Conta'),
            ('deposit', '💰 Problema de Depósito'),
            ('withdraw', '💸 Problema de Saque'),
            ('vip', '👑 VIP Club'),
            ('referral', '🤝 Programa de Referência'),
            ('lucky_wheel', '🎡 Roda da Fortuna'),
            ('vip_roulette', '🎰 Roleta VIP'),
            ('download_app', '📱 Baixar App'),
            ('language', '🌐 Alterar Idioma'),
            ('status', '📊 Status da Conta'),
            ('rules', '📜 Regras e Termos'),
            ('faq', '❓ Perguntas Frequentes'),
            ('contact', '📞 Contato Direto')
        ]

        # Đặt lệnh cơ bản cho tất cả người dùng
        await app.bot.set_my_commands([
            BotCommand(command, description)
            for command, description in basic_commands
        ])

        print("✅ Comandos cơ bản đã được cấu hình!")

        # Đặt lệnh admin cho từng admin cụ thể theo ngôn ngữ của từng admin
        for admin_id in bot_config.ADMIN_USER_IDS:
            try:
                # Lấy ngôn ngữ ưu tiên cho admin từ bộ nhớ tạm (nếu có)
                try:
                    lang = user_data.get(int(admin_id), {}).get('bulk_language') or user_data.get(int(admin_id), {}).get('language') or 'vi'
                except Exception:
                    lang = 'vi'

                admin_cmds = get_admin_commands(lang)

                await app.bot.set_my_commands(
                    [BotCommand(cmd, desc) for cmd, desc in admin_cmds],
                    scope=BotCommandScopeChat(chat_id=int(admin_id))
                )
                print(f"✅ Comandos admin configurados para {admin_id} (lang={lang})")
            except Exception as e:
                print(f"⚠️ Não foi possível configurar comandos admin para {admin_id}: {e}")

        print("✅ Tất cả lệnh đã được cấu hình thành công!")

    # Adicionar comandos de sugestão
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando help"""
        await update.message.reply_text(
            '🤖 **ABCDBET Customer Service Bot - Ajuda**\n\n'
            '📋 **Comandos principais:**\n'
            '/start - 🚀 Iniciar bot\n'
            '/help - ❓ Ajuda e comandos\n'
            '/menu - 📋 Menu Principal\n'
            '/commands - 📋 Lista de comandos\n'
            '/quick - ⚡ Comandos rápidos\n'
            '/hint - 💡 Dicas de comandos\n\n'
            '🎁 **Promoções e Bônus:**\n'
            '/promotions - 🎁 Promoções e bônus\n'
            '/deposit_packages - 💳 Pacotes de Depósito\n'
            '/daily_first_deposit - 🌅 Primeiro Depósito do Dia\n'
            '/vip - 👑 VIP Club\n'
            '/referral - 🤝 Programa de Referência\n'
            '/lucky_wheel - 🎡 Roda da Fortuna\n'
            '/vip_roulette - 🎰 Roleta VIP\n\n'
            '💰 **Depósito e Saque:**\n'
            '/register - 📝 Cadastrar Conta\n'
            '/deposit - 💰 Problema de Depósito\n'
            '/withdraw - 💸 Problema de Saque\n'
            '/status - 📊 Status da Conta\n\n'
            '🆘 **Suporte e Informações:**\n'
            '/support - 🆘 Suporte ao Cliente\n'
            '/rules - 📜 Regras e Termos\n'
            '/faq - ❓ Perguntas Frequentes\n'
            '/contact - 📞 Contato Direto\n\n'
            '🌐 **Configurações:**\n'
            '/language - 🌐 Alterar Idioma\n'
            '/download_app - 📱 Baixar App\n\n'
            '🔐 **Lệnh Admin (chỉ dành cho admin):**\n'
            '/bulk - 📢 Gửi tin nhắn hàng loạt\n'
            '/manage_channels - ⚙️ Quản lý kênh chuyển tiếp\n'
            '/stats - 📊 Xem thống kê khách hàng\n'
            '/stop_bulk - 🛑 Dừng gửi tin nhắn hàng loạt\n'
            '/reload - 🔄 Reload bot (Admin only)\n'
            '/health - 🏥 Kiểm tra sức khỏe bot (Admin only)\n\n'
            '💡 **Dica:** Use os botões do menu para navegar facilmente!\n'
            '🔍 **Dica:** Digite / seguido do comando para usar qualquer função!'
        )

    # Adicionar outros comandos
    async def promotions_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando promotions"""
        keyboard = [
            [InlineKeyboardButton('👑 VIP Club', callback_data='vip_club')],
            [InlineKeyboardButton(
                '🤝 Programa de Referência',
                callback_data='referral'
            )],

            [InlineKeyboardButton(
                '💳 Pacotes de Depósito',
                callback_data='deposit_packages'
            )],
            [InlineKeyboardButton(
                '🌅 Primeiro Depósito do Dia',
                callback_data='daily_first_deposit'
            )],
            [InlineKeyboardButton(
                '🎡 Roda da Fortuna',
                callback_data='lucky_wheel'
            )],
            [InlineKeyboardButton(
                '🎰 Roleta VIP',
                callback_data='vip_roulette'
            )],
            [InlineKeyboardButton(
                '📱 Baixe o aplicativo de promoção',
                callback_data='download_app'
            )],
            [InlineKeyboardButton(
                '🆘 Compensação de Perda',
                callback_data='loss_compensation'
            )],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🎁 **Programas Promocionais ABCD.BET**\n\n'
            'Escolha o programa promocional que você gostaria de conhecer:',
            reply_markup=reply_markup
        )

    async def deposit_packages_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando deposit_packages"""
        keyboard = [
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '💳 **Pacotes de Depósito ABCD.BET**\n\n'
            '🎁 **Pacote de primeiro depósito:**\n'
            'Por exemplo: Valor máximo de depósito é de 1000 BRL. '
            'Deposite BRL 1000, e ganhe BRL 1000 de bônus.\n\n'
            '🎁 **Pacote de Segundo Depósito:**\n'
            'Por exemplo: Valor máximo de depósito é de 750 BRL. '
            'Deposite BRL 750, e ganhe 375 BRL de bônus.\n\n'
            '🎁 **Pacote de Terceiro Depósito:**\n'
            'Por exemplo: Valor máximo de depósito é de 500 BRL. '
            'Deposite BRL 500, e ganhe 375 BRL de bônus.\n\n'
            '🚀 **Comece agora e aproveite nossos pacotes exclusivos!**',
            reply_markup=reply_markup,
        )

    async def daily_first_deposit_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando daily_first_deposit"""
        keyboard = [
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '💎 **PROMOÇÃO ESPECIAL – DEPOSITE E RECEBA BÔNUS TODOS OS DIAS!** 💎\n\n'
            '👉 **Válido somente para o primeiro depósito do dia na ABCD.BET**\n\n'
            '🔹 **Deposite de R$ 20 a R$ 99** → Bônus de **+2%** diretamente na conta\n'
            '🔹 **Deposite de R$ 100 ou mais** → Bônus de **+3%** extremamente atrativo\n\n'
            '⚡ **O bônus será adicionado automaticamente após o depósito ser efetuado!**\n\n'
            '📌 **Observação importante:**\n\n'
            '• Cada conta pode receber apenas **1 bônus por dia**.\n'
            '• O bônus precisa ser apostado **10 vezes** para ser liberado e pode ser sacado ou continuado jogando.\n\n'
            '🔥 **Não perca a oportunidade de maximizar sua renda diária com a ABCD.BET!**\n\n'
            '⏰ **Cadastre-se agora!**',
            reply_markup=reply_markup,
        )

    async def support_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando support"""
        keyboard = [
            [InlineKeyboardButton(
                '🌐 Abrir Atendimento ao cliente online',
                url=('https://vm.vondokua.com/'
                     '1kdzfz0cdixxg0k59medjggvhv')
            )],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🆘 **Atendimento ao Cliente Online**\n\n'
            '🌐 **Link de Suporte:** Clique no botão abaixo para abrir a página de\n'
            'suporte\n\n'
            '👆 **Clique em "Abrir Suporte Online" para acessar agora!**',
            reply_markup=reply_markup,
        )

    async def register_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando register"""
        keyboard = [
            [InlineKeyboardButton(
                '🌐 Abrir página de cadastro',
                url=('https://www.abcd.bet/v2/index.html?'
                     'appName=0&pid=0&click_id=0&pixel_id=0&t=0#/Center')
            )],
            [InlineKeyboardButton(
                '📱 Baixar APP ABCD.BET',
                url='https://file.abcd.bet/app/abcdbet.apk'
            )],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🎉 Bem-vindo ao ABCDBET 🎉\n\n'
            '🔑 Assim que você se registrar e fizer o primeiro depósito, já começa aproveitando um dos pacotes mais lucrativos do mercado:\n\n'
            '✨ Pacote de Primeiro Depósito\n\n'
            'Deposite a partir de BRL 10\n'
            'Receba 200% de bônus imediato\n'
            'Ganhe até BRL 2.000 extras para jogar!\n\n'
            '💎 E não para por aí!\n'
            'Depois de ativar o primeiro pacote, você desbloqueia ainda mais vantagens:\n\n'
            '🥈 Segundo Depósito: +150% de bônus (até BRL 1.125)\n\n'
            '🥉 Terceiro Depósito: +175% de bônus (até BRL 875), disponível em até 7 dias após o primeiro depósito\n\n'
            '🚀 É simples assim:\n'
            '1️⃣ Cadastre-se em poucos segundos\n'
            '2️⃣ Faça seu primeiro depósito\n'
            '3️⃣ Receba bônus automáticos e aumente suas chances de ganhar 💵\n\n'
            '⚡ Não perca! Essa é a sua chance de começar com o pé direito e multiplicar seus ganhos desde o primeiro dia.\n\n'
            '👉 [Cadastre-se agora e aproveite os bônus]',
            reply_markup=reply_markup
        )

    async def deposit_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando deposit"""
        keyboard = [
            [InlineKeyboardButton(
                '❌ Depósito não creditado',
                callback_data='deposit_not_credited'
            )],
            [InlineKeyboardButton(
                '🚫 Não consegue depositar',
                callback_data='deposit_failed'
            )],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '💰 **PROBLEMA DE DEPÓSITO**\n\n'
            'Escolha o problema que você está enfrentando:',
            reply_markup=reply_markup,
        )

    async def withdraw_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando withdraw"""
        keyboard = [
            [InlineKeyboardButton(
                '❌ Saque não recebido',
                callback_data='withdraw_not_received'
            )],
            [InlineKeyboardButton(
                '🚫 Não consegue sacar',
                callback_data='withdraw_failed'
            )],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '💸 **PROBLEMA DE SAQUE**\n\n'
            'Escolha o problema que você está enfrentando:',
            reply_markup=reply_markup,
        )

    async def menu_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Comando menu - mostrar menu principal"""
        await show_main_menu(update, context)

    async def bulk_message_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Lệnh gửi tin nhắn hàng loạt (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Você não tem permissão para usar este comando!"
            )
            return

        # Hiển thị menu gửi tin nhắn hàng loạt
        language = context.user_data.get('bulk_language', 'vi')
        keyboard = get_bulk_messaging_menu_keyboard(language)
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            get_bulk_messaging_title(language),
            reply_markup=reply_markup,
        )

    async def admin_stats_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Lệnh xem thống kê (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Você não tem permissão para usar este comando!"
            )
            return

        # Lấy thống kê từ Google Sheets
        stats = sheets_manager.get_customer_stats()
        if stats:
            stats_message = f"""
📊 **THỐNG KÊ KHÁCH HÀNG**

👥 **Tổng số khách hàng:** {stats['total']}
📅 **Hôm nay:** {stats['today']}
📆 **Tuần này:** {stats['week']}
🗓️ **Tháng này:** {stats['month']}

🔄 **Cập nhật lần cuối:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        else:
            stats_message = "❌ Không thể lấy thống kê khách hàng"

        await update.message.reply_text(stats_message)

    async def manage_channels_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Lệnh quản lý kênh (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Você não tem permissão para usar este comando!"
            )
            return

        # Menu quản lý kênh
        current_channels = getattr(bot_config, 'FORWARD_CHANNELS', [])
        channel_count = len(current_channels)

        # Lấy ngôn ngữ hiện tại
        language = context.user_data.get('bulk_language', 'vi')

        if language == 'zh':
            keyboard = [
                [InlineKeyboardButton('➕ 添加新频道', callback_data='add_channel')],
                [InlineKeyboardButton('📋 查看频道列表', callback_data='list_channels')],
                [InlineKeyboardButton('❌ 删除频道', callback_data='remove_channel')],
                [InlineKeyboardButton('🎯 选择频道发送', callback_data='select_channels_to_send')],
                [InlineKeyboardButton('⬅️ 返回', callback_data='bulk_back')]
            ]
            title = f'⚙️ **频道管理**\n\n📊 **当前统计:**\n• 总频道数: {channel_count}\n• 状态: ✅ 活跃\n\n**选择您要使用的功能:**'
        elif language == 'en':
            keyboard = [
                [InlineKeyboardButton('➕ Add new channel', callback_data='add_channel')],
                [InlineKeyboardButton('📋 View channel list', callback_data='list_channels')],
                [InlineKeyboardButton('❌ Delete channel', callback_data='remove_channel')],
                [InlineKeyboardButton('🎯 Select channels to send', callback_data='select_channels_to_send')],
                [InlineKeyboardButton('⬅️ Back', callback_data='bulk_back')]
            ]
            title = f'⚙️ **CHANNEL MANAGEMENT**\n\n📊 **Current statistics:**\n• Total channels: {channel_count}\n• Status: ✅ Active\n\n**Select the function you want to use:**'
        else:
            keyboard = [
                [InlineKeyboardButton('➕ Thêm kênh mới', callback_data='add_channel')],
                [InlineKeyboardButton('📋 Xem danh sách kênh', callback_data='list_channels')],
                [InlineKeyboardButton('❌ Xóa kênh', callback_data='remove_channel')],
                [InlineKeyboardButton('🎯 Chọn kênh gửi', callback_data='select_channels_to_send')],
                [InlineKeyboardButton('⬅️ Quay lại', callback_data='bulk_back')]
            ]
            title = f'⚙️ **QUẢN LÝ KÊNH CHUYỂN TIẾP**\n\n📊 **Thống kê hiện tại:**\n• Tổng số kênh: {channel_count}\n• Trạng thái: ✅ Hoạt động\n\n**Chọn chức năng bạn muốn sử dụng:**'

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            title,
            reply_markup=reply_markup,
        )

    async def stop_bulk_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Lệnh dừng gửi tin nhắn hàng loạt (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Você não tem permissão para usar este comando!"
            )
            return

        try:
            # Dừng gửi tin nhắn hàng loạt
            bulk_messaging_manager.stop_bulk_messaging()
            await update.message.reply_text(
                "🛑 **ĐÃ DỪNG GỬI TIN NHẮN HÀNG LOẠT!**\n\n"
                "Bot sẽ dừng gửi tin nhắn sau khi hoàn thành tin nhắn hiện tại.",
            )
        except Exception as e:
            logger.error(f"Lỗi khi dừng gửi tin nhắn hàng loạt: {e}")
            await update.message.reply_text(
                f"❌ **LỖI KHI DỪNG GỬI TIN NHẮN**\n\nLỗi: {str(e)}",
            )

    # ===== CÁC LỆNH HẸN GIỜ CHUYỂN TIẾP =====

    async def scheduled_forward_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Lệnh hẹn giờ chuyển tiếp (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Bạn không có quyền sử dụng lệnh này!"
            )
            return

        try:
            # Lấy ngôn ngữ của user
            language = context.user_data.get('language', 'vi')

            # Hiển thị menu hẹn giờ chuyển tiếp
            title = get_scheduled_forward_title(language)
            keyboard = get_scheduled_forward_menu_keyboard(language)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                title,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Lỗi hiển thị menu hẹn giờ chuyển tiếp: {e}")
            await update.message.reply_text(
                f"❌ **LỖI HIỂN THỊ MENU**\n\nLỗi: {str(e)}"
            )

    # ===== CÁC LỆNH MỚI CHO KHÁCH HÀNG =====

    async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh VIP Club"""
        keyboard = [
            [InlineKeyboardButton('👑 VIP Benefits', callback_data='vip_club')],
            [InlineKeyboardButton('📊 VIP Levels', callback_data='vip_levels')],
            [InlineKeyboardButton('🎁 VIP Rewards', callback_data='vip_rewards')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '👑 **VIP CLUB**\n\n'
            'Bem-vindo ao clube VIP exclusivo da ABCDBET!\n\n'
            '🎯 **Benefícios VIP:**\n'
            '• Cashback exclusivo\n'
            '• Bônus personalizados\n'
            '• Suporte prioritário\n'
            '• Eventos exclusivos\n\n'
            'Escolha uma opção:',
            reply_markup=reply_markup,
        )

    async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Programa de Referência"""
        keyboard = [
            [InlineKeyboardButton('🤝 Como Funciona', callback_data='referral_how')],
            [InlineKeyboardButton('💰 Ganhe Bônus', callback_data='referral_bonus')],
            [InlineKeyboardButton('📊 Meus Referidos', callback_data='referral_stats')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🤝 **PROGRAMA DE REFERÊNCIA**\n\n'
            'Convide amigos e ganhe bônus!\n\n'
            '💡 **Como funciona:**\n'
            '• Compartilhe seu link de referência\n'
            '• Amigos se registram usando seu link\n'
            '• Você ganha bônus por cada amigo\n'
            '• Bônus crescem com o tempo\n\n'
            'Escolha uma opção:',
            reply_markup=reply_markup,
        )

    async def lucky_wheel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Roda da Fortuna"""
        keyboard = [
            [InlineKeyboardButton('🎡 Girar Roda', callback_data='lucky_wheel_spin')],
            [InlineKeyboardButton('🏆 Prêmios', callback_data='lucky_wheel_prizes')],
            [InlineKeyboardButton('📅 Próximo Sorteio', callback_data='lucky_wheel_next')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🎡 **RODA DA FORTUNA**\n\n'
            'Gire a roda e ganhe prêmios incríveis!\n\n'
            '🎁 **Prêmios disponíveis:**\n'
            '• Bônus de depósito\n'
            '• Free spins\n'
            '• Cashback\n'
            '• Prêmios em dinheiro\n\n'
            'Escolha uma opção:',
            reply_markup=reply_markup,
        )

    async def vip_roulette_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Roleta VIP"""
        keyboard = [
            [InlineKeyboardButton('🎰 Jogar Roleta', callback_data='vip_roulette_play')],
            [InlineKeyboardButton('🏆 Prêmios VIP', callback_data='vip_roulette_prizes')],
            [InlineKeyboardButton('📊 Histórico', callback_data='vip_roulette_history')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🎰 **ROLETA VIP**\n\n'
            'Roleta exclusiva para membros VIP!\n\n'
            '💎 **Prêmios VIP:**\n'
            '• Bônus exclusivos\n'
            '• Multiplicadores especiais\n'
            '• Prêmios em dinheiro\n'
            '• Experiências únicas\n\n'
            'Escolha uma opção:',
            reply_markup=reply_markup,
        )

    async def download_app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Baixar App"""
        keyboard = [
            [InlineKeyboardButton('📱 Android', callback_data='download_android')],
            [InlineKeyboardButton('🍎 iOS', callback_data='download_ios')],
            [InlineKeyboardButton('💻 Desktop', callback_data='download_desktop')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '📱 **BAIXAR APLICATIVO**\n\n'
            'Baixe o app ABCDBET em qualquer dispositivo!\n\n'
            '📲 **Plataformas disponíveis:**\n'
            '• Android (Google Play)\n'
            '• iOS (App Store)\n'
            '• Desktop (Windows/Mac)\n'
            '• Web (Navegador)\n\n'
            'Escolha sua plataforma:',
            reply_markup=reply_markup,
        )

    async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Alterar Idioma"""
        keyboard = [
            [InlineKeyboardButton('🇧🇷 Português', callback_data='lang_pt')],
            [InlineKeyboardButton('🇺🇸 English', callback_data='lang_en')],
            [InlineKeyboardButton('🇻🇳 Tiếng Việt', callback_data='lang_vi')],
            [InlineKeyboardButton('🇨🇳 中文', callback_data='lang_zh')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '🌐 **ALTERAR IDIOMA**\n\n'
            'Escolha o idioma de sua preferência:\n\n'
            '🇧🇷 **Português** - Padrão\n'
            '🇺🇸 **English** - English\n'
            '🇻🇳 **Tiếng Việt** - Tiếng Việt\n'
            '🇨🇳 **中文** - 中文\n\n'
            'Selecione um idioma:',
            reply_markup=reply_markup,
        )

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Status da Conta"""
        user_id = update.effective_user.id

        # Simular status da conta (có thể kết nối với database thực tế)
        await update.message.reply_text(
            f'📊 **STATUS DA CONTA**\n\n'
            f'🆔 **ID do Usuário:** `{user_id}`\n'
            f'📅 **Data de Registro:** {datetime.now().strftime("%d/%m/%Y")}\n'
            f'⏰ **Último Login:** {datetime.now().strftime("%H:%M:%S")}\n'
            f'🌐 **Idioma:** Português\n'
            f'👑 **Nível VIP:** Bronze\n'
            f'💰 **Saldo:** R$ 0,00\n'
            f'🎁 **Bônus Ativos:** 0\n\n'
            f'💡 **Dica:** Use /deposit para adicionar fundos à sua conta!'
        )

    async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Regras e Termos"""
        keyboard = [
            [InlineKeyboardButton('📋 Termos de Uso', callback_data='terms_use')],
            [InlineKeyboardButton('🔒 Política de Privacidade', callback_data='privacy_policy')],
            [InlineKeyboardButton('🎰 Regras dos Jogos', callback_data='game_rules')],
            [InlineKeyboardButton('💰 Política de Pagamento', callback_data='payment_policy')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '📜 **REGRAS E TERMOS**\n\n'
            'Leia atentamente todas as regras e termos antes de usar nossos serviços.\n\n'
            '📋 **Documentos disponíveis:**\n'
            '• Termos de Uso\n'
            '• Política de Privacidade\n'
            '• Regras dos Jogos\n'
            '• Política de Pagamento\n\n'
            'Escolha um documento:',
            reply_markup=reply_markup,
        )

    async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Perguntas Frequentes"""
        keyboard = [
            [InlineKeyboardButton('❓ Como Depositar', callback_data='faq_deposit')],
            [InlineKeyboardButton('❓ Como Sacar', callback_data='faq_withdraw')],
            [InlineKeyboardButton('❓ Como Jogar', callback_data='faq_play')],
            [InlineKeyboardButton('❓ Problemas Técnicos', callback_data='faq_technical')],
            [InlineKeyboardButton('❓ Segurança', callback_data='faq_security')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '❓ **PERGUNTAS FREQUENTES**\n\n'
            'Encontre respostas para as perguntas mais comuns.\n\n'
            '🔍 **Categorias:**\n'
            '• Como Depositar\n'
            '• Como Sacar\n'
            '• Como Jogar\n'
            '• Problemas Técnicos\n'
            '• Segurança\n\n'
            'Escolha uma categoria:',
            reply_markup=reply_markup,
        )

    async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh Contato Direto"""
        keyboard = [
            [InlineKeyboardButton('📧 Email', callback_data='contact_email')],
            [InlineKeyboardButton('💬 WhatsApp', callback_data='contact_whatsapp')],
            [InlineKeyboardButton('📱 Telegram', callback_data='contact_telegram')],
            [InlineKeyboardButton('🌐 Website', callback_data='contact_website')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '📞 **CONTATO DIRETO**\n\n'
            'Entre em contato conosco através de qualquer canal:\n\n'
            '📧 **Email:** suporte@abcdbet.com\n'
            '💬 **WhatsApp:** +55 11 99999-9999\n'
            '📱 **Telegram:** @ABCDBET_Support\n'
            '🌐 **Website:** www.abcdbet.com\n'
            '⏰ **Horário:** 24/7\n\n'
            'Escolha um canal:',
            reply_markup=reply_markup,
        )

    async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh reload bot (chỉ admin)"""
        user_id = update.effective_user.id

        # Kiểm tra quyền admin
        if user_id not in bot_config.ADMIN_USER_IDS:
            await update.message.reply_text(
                "❌ Você não tem permissão para usar este comando!"
            )
            return

        await update.message.reply_text(
            "🔄 Iniciando reload do bot...\n"
            "⚡ Isso pode levar alguns segundos..."
        )

        # Trigger graceful restart
        graceful_restart()

    def escape_text(text):
        """Escape text để tránh lỗi parse entities"""
        if not text:
            return ""
        return str(text).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

    async def health_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Báo cáo sức khỏe bot (phiên bản an toàn, không dùng parse_mode)."""
        # Lấy thông tin bot
        bot_info = await context.bot.get_me()

        # Hàm lọc ký tự an toàn
        def safe_str(s):
            return ''.join(c for c in str(s) if c.isalnum() or c in ' @._:-')

        # Kiểm tra Google Sheets
        try:
            if sheets_manager.service:
                sheets_manager.service.spreadsheets().get(
                    spreadsheetId=sheets_manager.spreadsheet_id).execute()
                sheets_status = 'Hoạt động bình thường'
            else:
                sheets_status = 'Chưa khởi tạo'
        except Exception as e:
            sheets_status = f'Lỗi: {safe_str(e)}'

        # Kiểm tra notification system
        notification_status = 'Đã khởi tạo' if get_notification_manager() else 'Chưa khởi tạo'

        # Kiểm tra bulk messaging
        bulk_status = 'Hoạt động bình thường' if bulk_messaging_manager else 'Chưa khởi tạo'

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report_lines = [
            '=== BÁO CÁO SỨC KHOE BOT ===',
            f'Ten bot     : {safe_str(bot_info.first_name)}',
            f'Username    : @{safe_str(bot_info.username)}',
            f'ID          : {bot_info.id}',
            '',
            '-- DICH VU --',
            f'Google Sheets   : {sheets_status}',
            f'Notification    : {notification_status}',
            f'Bulk Messaging  : {bulk_status}',
            '',
            f'Thoi gian kiem tra : {now_str}',
            'TONG KET          : OK',
            '=============================='
        ]
        await update.message.reply_text('\n'.join(report_lines))

    async def commands_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh hiển thị danh sách tất cả các lệnh có sẵn"""
        commands_text = (
            '📋 **LISTA COMPLETA DE COMANDOS**\n\n'
            '🚀 **COMANDOS PRINCIPAIS:**\n'
            '• `/start` - Iniciar bot\n'
            '• `/help` - Ajuda e comandos\n'
            '• `/menu` - Menu Principal\n'
            '• `/commands` - Esta lista de comandos\n\n'
            '🎁 **PROMOÇÕES E BÔNUS:**\n'
            '• `/promotions` - Promoções e bônus\n'
            '• `/deposit_packages` - Pacotes de Depósito\n'
            '• `/daily_first_deposit` - Primeiro Depósito do Dia\n'
            '• `/vip` - VIP Club\n'
            '• `/referral` - Programa de Referência\n'
            '• `/lucky_wheel` - Roda da Fortuna\n'
            '• `/vip_roulette` - Roleta VIP\n\n'
            '💰 **DEPÓSITO E SAQUE:**\n'
            '• `/register` - Cadastrar Conta\n'
            '• `/deposit` - Problema de Depósito\n'
            '• `/withdraw` - Problema de Saque\n'
            '• `/status` - Status da Conta\n\n'
            '🆘 **SUPORTE E INFORMAÇÕES:**\n'
            '• `/support` - Suporte ao Cliente\n'
            '• `/rules` - Regras e Termos\n'
            '• `/faq` - Perguntas Frequentes\n'
            '• `/contact` - Contato Direto\n\n'
            '🌐 **CONFIGURAÇÕES:**\n'
            '• `/language` - Alterar Idioma\n'
            '• `/download_app` - Baixar App\n\n'
            '🔐 **COMANDOS ADMIN:**\n'
            '• `/bulk` - Gửi tin nhắn hàng loạt\n'
            '• `/manage_channels` - Quản lý kênh\n'
            '• `/stats` - Thống kê khách hàng\n'
            '• `/stop_bulk` - Dừng gửi tin nhắn\n\n'
            '💡 **DICA:** Digite `/` seguido do comando para usar qualquer função!\n'
            '📱 **EXEMPLO:** `/vip`, `/status`, `/rules`'
        )

        await update.message.reply_text(
            commands_text,
        )

    async def quick_commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh hiển thị gợi ý lệnh nhanh với keyboard"""
        keyboard = [
            [InlineKeyboardButton('🚀 /start', callback_data='cmd_start'),
             InlineKeyboardButton('❓ /help', callback_data='cmd_help')],
            [InlineKeyboardButton('📋 /menu', callback_data='cmd_menu'),
             InlineKeyboardButton('📋 /commands', callback_data='cmd_commands')],
            [InlineKeyboardButton('🎁 /promotions', callback_data='cmd_promotions'),
             InlineKeyboardButton('👑 /vip', callback_data='cmd_vip')],
            [InlineKeyboardButton('💰 /deposit', callback_data='cmd_deposit'),
             InlineKeyboardButton('💸 /withdraw', callback_data='cmd_withdraw')],
            [InlineKeyboardButton('📝 /register', callback_data='cmd_register'),
             InlineKeyboardButton('📊 /status', callback_data='cmd_status')],
            [InlineKeyboardButton('🆘 /support', callback_data='cmd_support'),
             InlineKeyboardButton('📜 /rules', callback_data='cmd_rules')],
            [InlineKeyboardButton('❓ /faq', callback_data='cmd_faq'),
             InlineKeyboardButton('📞 /contact', callback_data='cmd_contact')],
            [InlineKeyboardButton('🌐 /language', callback_data='cmd_language'),
             InlineKeyboardButton('📱 /download_app', callback_data='cmd_download')],
            [InlineKeyboardButton('🎡 /lucky_wheel', callback_data='cmd_lucky_wheel'),
             InlineKeyboardButton('🎰 /vip_roulette', callback_data='cmd_vip_roulette')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            '⚡ **COMANDOS RÁPIDOS**\n\n'
            'Clique em qualquer comando abaixo para executá-lo:\n\n'
            '💡 **DICA:** Você também pode digitar `/` seguido do comando!\n'
            '📱 **EXEMPLO:** `/vip`, `/status`, `/rules`',
            reply_markup=reply_markup,
        )

    async def show_commands_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lệnh hiển thị gợi ý lệnh theo ngôn ngữ"""
        user_id = update.effective_user.id
        language = user_data.get(user_id, {}).get('language', 'pt')

        if language == 'zh':
            title = '💡 **命令提示**'
            hint_text = '输入 `/` 后跟命令名称来使用功能：\n\n'
            examples = '**常用命令示例：**\n• `/start` - 启动机器人\n• `/help` - 帮助信息\n• `/vip` - VIP俱乐部\n• `/status` - 账户状态'
        elif language == 'en':
            title = '💡 **Command Hints**'
            hint_text = 'Type `/` followed by command name to use features:\n\n'
            examples = '**Common Commands:**\n• `/start` - Start bot\n• `/help` - Help info\n• `/vip` - VIP Club\n• `/status` - Account status'
        elif language == 'vi':
            title = '💡 **Gợi Ý Lệnh**'
            hint_text = 'Gõ `/` theo sau là tên lệnh để sử dụng tính năng:\n\n'
            examples = '**Lệnh Thường Dùng:**\n• `/start` - Khởi động bot\n• `/help` - Thông tin trợ giúp\n• `/vip` - VIP Club\n• `/status` - Trạng thái tài khoản'
        else:
            title = '💡 **Dicas de Comandos**'
            hint_text = 'Digite `/` seguido do nome do comando para usar recursos:\n\n'
            examples = '**Comandos Comuns:**\n• `/start` - Iniciar bot\n• `/help` - Informações de ajuda\n• `/vip` - VIP Club\n• `/status` - Status da conta'

        keyboard = [
            [InlineKeyboardButton('📋 Ver Todos os Comandos', callback_data='show_all_commands')],
            [InlineKeyboardButton('⚡ Comandos Rápidos', callback_data='show_quick_commands')],
            [InlineKeyboardButton('❓ Ajuda', callback_data='show_help')],
            [InlineKeyboardButton('⬅️ Voltar', callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f'{title}\n\n{hint_text}{examples}\n\n'
            '💡 **Tip:** Use the buttons below for quick access!',
            reply_markup=reply_markup,
        )

    # Adicionar todos os comandos ao application
    # Đảm bảo chỉ có 1 handler cho mỗi lệnh
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('menu', menu_command))
    application.add_handler(
        CommandHandler('promotions', promotions_command)
    )
    application.add_handler(
        CommandHandler('deposit_packages', deposit_packages_command)
    )
    application.add_handler(
        CommandHandler('daily_first_deposit', daily_first_deposit_command)
    )
    application.add_handler(
        CommandHandler('support', support_command)
    )
    application.add_handler(
        CommandHandler('register', register_command)
    )
    application.add_handler(
        CommandHandler('deposit', deposit_command)
    )
    application.add_handler(
        CommandHandler('withdraw', withdraw_command)
    )
    application.add_handler(
        CommandHandler('vip', vip_command)
    )
    application.add_handler(
        CommandHandler('referral', referral_command)
    )
    application.add_handler(
        CommandHandler('lucky_wheel', lucky_wheel_command)
    )
    application.add_handler(
        CommandHandler('vip_roulette', vip_roulette_command)
    )
    application.add_handler(
        CommandHandler('download_app', download_app_command)
    )
    application.add_handler(
        CommandHandler('language', language_command)
    )
    application.add_handler(
        CommandHandler('status', status_command)
    )
    application.add_handler(
        CommandHandler('rules', rules_command)
    )
    application.add_handler(
        CommandHandler('faq', faq_command)
    )
    application.add_handler(
        CommandHandler('contact', contact_command)
    )
    application.add_handler(
        CommandHandler('commands', commands_list_command)
    )
    application.add_handler(
        CommandHandler('quick', quick_commands_command)
    )
    application.add_handler(
        CommandHandler('hint', show_commands_hint)
    )
    application.add_handler(
        CommandHandler('bulk', bulk_message_command)
    )
    application.add_handler(
        CommandHandler('manage_channels', manage_channels_command)
    )
    application.add_handler(
        CommandHandler('stop_bulk', stop_bulk_command)
    )
    application.add_handler(
        CommandHandler('scheduled_forward', scheduled_forward_command)
    )
    application.add_handler(
        CommandHandler('stats', admin_stats_command)
    )
    application.add_handler(
        CommandHandler('reload', reload_command)
    )
    application.add_handler(
        CommandHandler('health', health_check_command)
    )

    # Adicionar handler para callbacks dos botões
    application.add_handler(CallbackQueryHandler(button_handler))

    # Adicionar handler para mensagens de texto (bulk messaging) - EXCLUIR comandos
    # Chỉ xử lý tin nhắn văn bản KHÔNG phải lệnh
    text_filter = filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^/')
    application.add_handler(MessageHandler(text_filter, handle_text_message))

    # Adicionar handler para media (hình ảnh, video, file, audio, sticker, GIF, voice, video note)
    # Chỉ xử lý media, không xử lý lệnh
    media_filter = filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO
    application.add_handler(MessageHandler(media_filter, handle_media_message))

    # Configurar comandos do bot trước khi khởi động
    # (post_init đã được gán ở trên, không cần gán lại)

    # Iniciar bot
    print("🤖 ABCDBET Customer Service Bot está iniciando...")
    print("🔔 Notification System: Integrado")
    print("📋 Form Builder: Integrado")
    print("🔗 Ecosystem Integration: Integrado")
    print("🎁 ABCD.BET Promotions: Integrado")
    print("🎉 Welcome Message System: Integrado")

    # Chạy bot
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\n🛑 Bot đã được dừng bởi người dùng")
    except Exception as e:
        print(f"❌ Lỗi khi chạy bot: {e}")
        logger.error(f"Lỗi khi chạy bot: {e}")


if __name__ == '__main__':
    main()
