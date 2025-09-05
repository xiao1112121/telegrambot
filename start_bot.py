#!/usr/bin/env python3
"""
Script khởi động ABCDBET Customer Service Bot
"""

import sys
import signal
from pathlib import Path


def check_environment():
    """Kiểm tra môi trường"""
    print("🔍 Kiểm tra môi trường...")

    # Kiểm tra Python version
    if sys.version_info < (3, 8):
        print("❌ Cần Python 3.8 trở lên")
        return False

    # Kiểm tra file bot.py
    if not Path("bot.py").exists():
        print("❌ Không tìm thấy bot.py")
        return False

    # Kiểm tra bot_config.py
    if not Path("bot_config.py").exists():
        print("❌ Không tìm thấy bot_config.py")
        return False

    print("✅ Môi trường OK")
    return True


def check_dependencies():
    """Kiểm tra dependencies"""
    print("📦 Kiểm tra dependencies...")

    required_modules = [
        'telegram',
        'google.auth',
        'pandas',
        'aiohttp'
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"❌ Thiếu modules: {', '.join(missing_modules)}")
        print("🔧 Cài đặt bằng: pip install -r requirements.txt")
        return False

    print("✅ Dependencies OK")
    return True


def signal_handler(signum, frame):
    """Xử lý signal để dừng bot gracefully"""
    print(f"\n🛑 Nhận signal {signum}, đang dừng bot...")
    sys.exit(0)


def start_bot():
    """Khởi động bot"""
    print("🚀 Khởi động ABCDBET Customer Service Bot...")
    print("=" * 50)

    try:
        # Import và chạy bot
        print("✅ Bot đã khởi động thành công!")
        print("📱 Gửi /start trên Telegram để test")
        print("⏹️  Nhấn Ctrl+C để dừng")

        # Chạy bot
        import subprocess
        subprocess.run([sys.executable, "bot.py"])

    except ImportError as e:
        print(f"❌ Lỗi import: {e}")
        return False
    except Exception as e:
        print(f"❌ Lỗi khởi động bot: {e}")
        return False

    return True


def main():
    """Hàm chính"""
    print("🤖 ABCDBET Customer Service Bot Launcher")
    print("=" * 50)

    # Kiểm tra môi trường
    if not check_environment():
        sys.exit(1)

    # Kiểm tra dependencies
    if not check_dependencies():
        sys.exit(1)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)

    # Khởi động bot
    if start_bot():
        print("🎉 Bot đang chạy! Kiểm tra Telegram của bạn.")
    else:
        print("❌ Không thể khởi động bot")
        sys.exit(1)


if __name__ == "__main__":
    main()
