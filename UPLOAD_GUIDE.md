# 📤 HƯỚNG DẪN TẢI LÊN SERVER SSH

## 🌐 Thông tin Server
- **IP**: 185.175.58.109
- **Username**: root
- **Thư mục đích**: /root/abcdbetkf

## 🚀 Các Script Tải Lên

### 1. Script Python Chính (`manual_upload.py`)
Script tải lên đầy đủ với giao diện tương tác.

**Cách sử dụng:**
```bash
python manual_upload.py
```

**Tính năng:**
- ✅ Kiểm tra kết nối SSH
- ✅ Tải lên tất cả file
- ✅ Chế độ tương tác
- ✅ Xử lý lỗi chi tiết

### 2. Script Tải Lên Nhanh (`quick_upload.py`)
Script tải lên một file cụ thể nhanh chóng.

**Cách sử dụng:**
```bash
# Tải lên bot.py
python quick_upload.py bot.py

# Tải lên bot_config.py
python quick_upload.py bot_config.py

# Tải lên requirements.txt
python quick_upload.py requirements.txt

# Tải lên start_bot.py
python quick_upload.py start_bot.py

# Tải lên run_bot.py
python quick_upload.py run_bot.py
```

### 3. Script Batch Windows (`upload.bat`)
Script batch để chạy trên Windows Command Prompt.

**Cách sử dụng:**
```cmd
upload.bat
```

**Tính năng:**
- ✅ Menu tương tác
- ✅ Tải lên từng file riêng lẻ
- ✅ Tải lên tất cả file
- ✅ Giao diện tiếng Việt

### 4. Script PowerShell (`upload.ps1`)
Script PowerShell với giao diện màu sắc đẹp.

**Cách sử dụng:**
```powershell
.\upload.ps1
```

**Tính năng:**
- ✅ Giao diện màu sắc
- ✅ Kiểm tra kết nối SSH
- ✅ Menu tương tác
- ✅ Xử lý lỗi tốt

## 📁 Danh Sách File Cần Tải Lên

| File | Mô tả |
|------|-------|
| `bot.py` | File bot chính |
| `bot_config.py` | Cấu hình bot |
| `requirements.txt` | Dependencies Python |
| `start_bot.py` | Script khởi động bot |
| `run_bot.py` | Script chạy bot |

## 🔧 Cài Đặt Trước Khi Sử Dụng

### Windows
1. Cài đặt OpenSSH (có sẵn từ Windows 10 1809)
2. Hoặc cài đặt Git Bash, WSL, hoặc PuTTY

### Linux/macOS
```bash
# Kiểm tra SSH
ssh -V

# Nếu chưa có, cài đặt:
# Ubuntu/Debian
sudo apt install openssh-client

# CentOS/RHEL
sudo yum install openssh-clients

# macOS
brew install openssh
```

## 📋 Các Lệnh SCP Thủ Công

Nếu không muốn dùng script, có thể dùng lệnh SCP trực tiếp:

### Tải lên từng file:
```bash
# Tạo thư mục trên server
ssh root@185.175.58.109 "mkdir -p /root/abcdbetkf"

# Tải lên bot.py
scp -o StrictHostKeyChecking=no bot.py root@185.175.58.109:/root/abcdbetkf/

# Tải lên bot_config.py
scp -o StrictHostKeyChecking=no bot_config.py root@185.175.58.109:/root/abcdbetkf/

# Tải lên requirements.txt
scp -o StrictHostKeyChecking=no requirements.txt root@185.175.58.109:/root/abcdbetkf/

# Tải lên start_bot.py
scp -o StrictHostKeyChecking=no start_bot.py root@185.175.58.109:/root/abcdbetkf/

# Tải lên run_bot.py
scp -o StrictHostKeyChecking=no run_bot.py root@185.175.58.109:/root/abcdbetkf/
```

### Tải lên tất cả file cùng lúc:
```bash
# Tạo thư mục
ssh root@185.175.58.109 "mkdir -p /root/abcdbetkf"

# Tải lên tất cả file
scp -o StrictHostKeyChecking=no *.py *.txt root@185.175.58.109:/root/abcdbetkf/
```

## 🎯 Sau Khi Tải Lên

1. **SSH vào server:**
   ```bash
   ssh root@185.175.58.109
   ```

2. **Di chuyển vào thư mục:**
   ```bash
   cd /root/abcdbetkf
   ```

3. **Kiểm tra file:**
   ```bash
   ls -la
   ```

4. **Cài đặt dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Chạy bot:**
   ```bash
   # Cách 1: Chạy trực tiếp
   python bot.py
   
   # Cách 2: Dùng script khởi động
   python start_bot.py
   
   # Cách 3: Dùng script chạy
   python run_bot.py
   ```

## ⚠️ Xử Lý Lỗi Thường Gặp

### Lỗi "Permission denied"
```bash
# Kiểm tra quyền SSH
ssh -v root@185.175.58.109
```

### Lỗi "Connection refused"
- Kiểm tra IP server có đúng không
- Kiểm tra server có bật SSH không
- Kiểm tra firewall có chặn port 22 không

### Lỗi "Host key verification failed"
```bash
# Xóa host key cũ
ssh-keygen -R 185.175.58.109

# Hoặc dùng StrictHostKeyChecking=no
ssh -o StrictHostKeyChecking=no root@185.175.58.109
```

## 🔐 Bảo Mật

- **Không lưu password trong script** (sử dụng SSH key)
- **Sử dụng SSH key thay vì password:**
  ```bash
  # Tạo SSH key
  ssh-keygen -t rsa -b 4096
  
  # Copy key lên server
  ssh-copy-id root@185.175.58.109
  ```

## 📞 Hỗ Trợ

Nếu gặp vấn đề, kiểm tra:
1. Kết nối mạng
2. IP server
3. Username/password
4. Quyền truy cập SSH
5. Firewall settings
