#!/usr/bin/env python3
"""
Script tải lên thủ công cho server SSH
Sử dụng: python manual_upload.py
"""

import os
import subprocess

# Cấu hình server
SERVER_IP = "185.175.58.109"
USERNAME = "root"
REMOTE_DIR = "/root/abcdbetkf"

# Danh sách file cần tải lên
FILES_TO_UPLOAD = [
    "bot.py",
    "bot_config.py", 
    "requirements.txt",
    "start_bot.py",
    "run_bot.py"
]


def check_file_exists(filename):
    """Kiểm tra file có tồn tại không"""
    if os.path.exists(filename):
        return True
    else:
        print(f"❌ Không tìm thấy file: {filename}")
        return False


def upload_single_file(filename):
    """Tải lên một file duy nhất"""
    if not check_file_exists(filename):
        return False
    
    print(f"📤 Đang tải {filename}...")
    
    # Tạo thư mục trên server trước
    mkdir_cmd = f'ssh -o StrictHostKeyChecking=no {USERNAME}@{SERVER_IP} "mkdir -p {REMOTE_DIR}"'
    try:
        subprocess.run(mkdir_cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"⚠️  Không thể tạo thư mục {REMOTE_DIR} trên server")
    
    # Tải file lên
    scp_cmd = f'scp -o StrictHostKeyChecking=no {filename} {USERNAME}@{SERVER_IP}:{REMOTE_DIR}/'
    
    try:
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Đã tải {filename} thành công!")
            return True
        else:
            print(f"❌ Lỗi khi tải {filename}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi khi thực hiện SCP: {e}")
        return False


def upload_all_files():
    """Tải lên tất cả file"""
    print("🚀 Bắt đầu tải lên tất cả file...")
    
    success_count = 0
    total_files = len(FILES_TO_UPLOAD)
    
    for filename in FILES_TO_UPLOAD:
        if upload_single_file(filename):
            success_count += 1
        print("-" * 50)
    
    print(f"\n📊 Kết quả: {success_count}/{total_files} file được tải lên thành công")
    
    if success_count == total_files:
        print("🎉 Tất cả file đã được tải lên thành công!")
        print("\n📋 HƯỚNG DẪN SAU KHI TẢI LÊN:")
        print(f"1. SSH vào server: ssh {USERNAME}@{SERVER_IP}")
        print(f"2. Di chuyển vào thư mục: cd {REMOTE_DIR}")
        print("3. Cài đặt dependencies: pip install -r requirements.txt")
        print("4. Chạy bot: python bot.py")
        print("5. Hoặc dùng script: python start_bot.py")
    else:
        print("⚠️  Một số file không thể tải lên. Vui lòng kiểm tra lại.")


def interactive_upload():
    """Chế độ tải lên tương tác"""
    print("🎯 CHẾ ĐỘ TẢI LÊN TƯƠNG TÁC")
    print("=" * 50)
    
    while True:
        print("\n📁 Danh sách file có thể tải lên:")
        for i, filename in enumerate(FILES_TO_UPLOAD, 1):
            status = "✅" if os.path.exists(filename) else "❌"
            print(f"  {i}. {filename} {status}")
        
        print("\n🔧 Tùy chọn:")
        print("  a - Tải lên tất cả file")
        print("  s - Tải lên file cụ thể")
        print("  q - Thoát")
        
        choice = input("\n👉 Chọn tùy chọn: ").strip().lower()
        
        if choice == 'a':
            upload_all_files()
            break
        elif choice == 's':
            try:
                file_num = int(input("👉 Nhập số thứ tự file (1-{}): ".format(len(FILES_TO_UPLOAD))))
                if 1 <= file_num <= len(FILES_TO_UPLOAD):
                    filename = FILES_TO_UPLOAD[file_num - 1]
                    upload_single_file(filename)
                else:
                    print("❌ Số thứ tự không hợp lệ!")
            except ValueError:
                print("❌ Vui lòng nhập số!")
        elif choice == 'q':
            print("👋 Tạm biệt!")
            break
        else:
            print("❌ Tùy chọn không hợp lệ!")


def main():
    """Hàm chính"""
    print("🚀 SCRIPT TẢI LÊN THỦ CÔNG CHO SERVER SSH")
    print("=" * 60)
    print(f"🌐 Server: {SERVER_IP}")
    print(f"👤 User: {USERNAME}")
    print(f"📂 Thư mục đích: {REMOTE_DIR}")
    print("=" * 60)
    
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
    
    # Chọn chế độ tải lên
    print("\n🎯 Chọn chế độ tải lên:")
    print("1. Tải lên tất cả file")
    print("2. Chế độ tương tác")
    print("3. Thoát")
    
    try:
        mode = input("\n👉 Chọn chế độ (1-3): ").strip()
        
        if mode == "1":
            upload_all_files()
        elif mode == "2":
            interactive_upload()
        elif mode == "3":
            print("👋 Tạm biệt!")
        else:
            print("❌ Tùy chọn không hợp lệ!")
            
    except KeyboardInterrupt:
        print("\n\n👋 Đã hủy bởi người dùng!")


if __name__ == "__main__":
    main()
