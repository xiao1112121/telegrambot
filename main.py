import threading
import os
from flask import Flask
from bot import main as run_bot
from create_credentials import create_credentials_from_env


# Tạo Flask app cho health check
app = Flask(__name__)


@app.route('/')
def health_check():
    return "ABCD.BET Bot is running!", 200


@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running", "service": "abcdbet-bot"}, 200


def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


def run_telegram_bot():
    run_bot()


if __name__ == '__main__':
    # Tạo credentials.json từ biến môi trường (nếu có)
    create_credentials_from_env()

    # Chạy Flask server trong thread riêng
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Chạy Telegram bot trong thread chính
    run_telegram_bot()
