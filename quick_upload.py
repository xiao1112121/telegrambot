#!/usr/bin/env python3
"""
Script tải lên nhanh cho server SSH
Sử dụng: python quick_upload.py <tên_file>
Ví dụ: python quick_upload.py bot.py
"""

import os
import subprocess
import sys

# Cấu hình server
SERVER_IP = "185.175.58.109"
USERNAME = "root"
REMOTE_DIR = "/root/abcdbetkf"


def upload_file(filename):
    """Tải lên một file duy nhất"""
    if not os.path.exists(filename):
        print(f"❌ Không tìm thấy file: {filename}")
        return False
    
    print(f"📤 Đang tải {filename} lên server...")
    
    # Tạo thư mục trên server trước
    print("🔧 Tạo thư mục trên server...")
    mkdir_cmd = f'ssh -o StrictHostKeyChecking=no {USERNAME}@{SERVER_IP} "mkdir -p {REMOTE_DIR}"'
    try:
        subprocess.run(mkdir_cmd, shell=True, check=True, capture_output=True)
        print("✅ Đã tạo thư mục trên server")
    except subprocess.CalledProcessError:
        print("⚠️  Không thể tạo thư mục trên server")
    
    # Tải file lên
    print(f"📤 Đang tải {filename}...")
    scp_cmd = f'scp -o StrictHostKeyChecking=no {filename} {USERNAME}@{SERVER_IP}:{REMOTE_DIR}/'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Đã tải {filename} thành công!")
            print(f"📁 File đã được lưu tại: {REMOTE_DIR}/{filename}")
            return True
        else:
            print(f"❌ Lỗi khi tải {filename}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi khi thực hiện SCP: {e}")
        return False


def main():
    """Hàm chính"""
    if len(sys.argv) != 2:
        print("🚀 SCRIPT TẢI LÊN NHANH CHO SERVER SSH")
        print("=" * 50)
        print(f"🌐 Server: {SERVER_IP}")
        print(f"👤 User: {USERNAME}")
        print(f"📂 Thư mục đích: {REMOTE_DIR}")
        print("=" * 50)
        print("\n📋 Cách sử dụng:")
        print("  python quick_upload.py <tên_file>")
        print("\n📁 Ví dụ:")
        print("  python quick_upload.py bot.py")
        print("  python quick_upload.py bot_config.py")
        print("  python quick_upload.py requirements.txt")
        print("  python quick_upload.py start_bot.py")
        print("  python quick_upload.py run_bot.py")
        return
    
    filename = sys.argv[1]
    
    # Kiểm tra kết nối SSH
    print("🔍 Kiểm tra kết nối SSH...")
    try:
        test_cmd = f'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no {USERNAME}@{SERVER_IP} "echo Kết nối thành công"'
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✅ Kết nối SSH thành công!")
        else:
            print("❌ Không thể kết nối SSH!")
            print("💡 Kiểm tra:")
            print("   - IP server có đúng không")
            print("   - Server có bật SSH không")
            print("   - Username/password có đúng không")
            return
            
    except subprocess.TimeoutExpired:
        print("❌ Kết nối SSH bị timeout!")
        return
    except Exception as e:
        print(f"❌ Lỗi kiểm tra kết nối: {e}")
        return
    
    # Tải file lên
    if upload_file(filename):
        print("\n🎯 HƯỚNG DẪN SAU KHI TẢI LÊN:")
        print(f"1. SSH vào server: ssh {USERNAME}@{SERVER_IP}")
        print(f"2. Di chuyển vào thư mục: cd {REMOTE_DIR}")
        print(f"3. Kiểm tra file: ls -la {filename}")
        print("4. Nếu là requirements.txt: pip install -r requirements.txt")
        print("5. Nếu là bot: python bot.py hoặc python start_bot.py")


if __name__ == "__main__":
    main()
