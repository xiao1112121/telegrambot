#!/usr/bin/env python3
"""
Script chạy bot Telegram đơn giản
"""

import subprocess
import sys


def check_dependencies():
    """Kiểm tra dependencies"""
    try:
        # Kiểm tra các thư viện chính
        import telegram
        import google.auth
        # Sử dụng các import để tránh lỗi linter
        _ = telegram.__version__
        _ = google.auth.__version__
        print("✅ Tất cả dependencies đã được cài đặt")
        return True
    except ImportError as e:
        print(f"❌ Thiếu dependency: {e}")
        print("🔧 Cài đặt bằng: pip install -r requirements.txt")
        return False


def run_bot():
    """Chạy bot"""
    print("🤖 Đang khởi động ABCDBET Customer Service Bot...")
    print("📱 Bot sẽ hoạt động khi bạn gửi /start")
    print("⏹️  Nhấn Ctrl+C để dừng bot")
    print("-" * 50)

    try:
        # Chạy bot
        subprocess.run([sys.executable, "bot.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Bot đã được dừng bởi người dùng")
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi chạy bot: {e}")
    except FileNotFoundError:
        print("❌ Không tìm thấy file bot.py")


if __name__ == "__main__":
    if check_dependencies():
        run_bot()
    else:
        sys.exit(1)
