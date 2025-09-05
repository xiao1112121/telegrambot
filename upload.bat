@echo off
chcp 65001 >nul
title Script Tải Lên Server SSH

echo.
echo ========================================
echo    SCRIPT TẢI LÊN SERVER SSH
echo ========================================
echo.
echo 🌐 Server: 185.175.58.109
echo 👤 User: root
echo 📂 Thư mục: /root/abcdbetkf
echo.

:menu
echo 📋 CHỌN TÙY CHỌN:
echo.
echo 1. Tải lên bot.py
echo 2. Tải lên bot_config.py
echo 3. Tải lên requirements.txt
echo 4. Tải lên start_bot.py
echo 5. Tải lên run_bot.py
echo 6. Tải lên tất cả file
echo 7. Thoát
echo.

set /p choice="👉 Chọn tùy chọn (1-7): "

if "%choice%"=="1" goto upload_bot
if "%choice%"=="2" goto upload_config
if "%choice%"=="3" goto upload_requirements
if "%choice%"=="4" goto upload_start
if "%choice%"=="5" goto upload_run
if "%choice%"=="6" goto upload_all
if "%choice%"=="7" goto exit
echo ❌ Tùy chọn không hợp lệ!
goto menu

:upload_bot
echo.
echo 📤 Đang tải bot.py...
scp -o StrictHostKeyChecking=no bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 (
    echo ✅ Đã tải bot.py thành công!
) else (
    echo ❌ Lỗi khi tải bot.py!
)
goto menu

:upload_config
echo.
echo 📤 Đang tải bot_config.py...
scp -o StrictHostKeyChecking=no bot_config.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 (
    echo ✅ Đã tải bot_config.py thành công!
) else (
    echo ❌ Lỗi khi tải bot_config.py!
)
goto menu

:upload_requirements
echo.
echo 📤 Đang tải requirements.txt...
scp -o StrictHostKeyChecking=no requirements.txt root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 (
    echo ✅ Đã tải requirements.txt thành công!
) else (
    echo ❌ Lỗi khi tải requirements.txt!
)
goto menu

:upload_start
echo.
echo 📤 Đang tải start_bot.py...
scp -o StrictHostKeyChecking=no start_bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 (
    echo ✅ Đã tải start_bot.py thành công!
) else (
    echo ❌ Lỗi khi tải start_bot.py!
)
goto menu

:upload_run
echo.
echo 📤 Đang tải run_bot.py...
scp -o StrictHostKeyChecking=no run_bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 (
    echo ✅ Đã tải run_bot.py thành công!
) else (
    echo ❌ Lỗi khi tải run_bot.py!
)
goto menu

:upload_all
echo.
echo 🚀 Đang tải tất cả file...
echo.

echo 📤 Tải bot.py...
scp -o StrictHostKeyChecking=no bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 echo ✅ bot.py OK

echo 📤 Tải bot_config.py...
scp -o StrictHostKeyChecking=no bot_config.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 echo ✅ bot_config.py OK

echo 📤 Tải requirements.txt...
scp -o StrictHostKeyChecking=no requirements.txt root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 echo ✅ requirements.txt OK

echo 📤 Tải start_bot.py...
scp -o StrictHostKeyChecking=no start_bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 echo ✅ start_bot.py OK

echo 📤 Tải run_bot.py...
scp -o StrictHostKeyChecking=no run_bot.py root@185.175.58.109:/root/abcdbetkf/
if %errorlevel%==0 echo ✅ run_bot.py OK

echo.
echo 🎉 Hoàn thành tải lên tất cả file!
echo.
echo 📋 HƯỚNG DẪN SAU KHI TẢI LÊN:
echo 1. SSH vào server: ssh root@185.175.58.109
echo 2. Di chuyển vào thư mục: cd /root/abcdbetkf
echo 3. Cài đặt dependencies: pip install -r requirements.txt
echo 4. Chạy bot: python bot.py
echo 5. Hoặc dùng script: python start_bot.py
echo.
pause
goto menu

:exit
echo.
echo 👋 Tạm biệt!
echo.
pause
exit
