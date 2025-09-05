import os
import json

def create_credentials_from_env():
    """Tạo file credentials.json từ biến môi trường"""
    credentials_data = {
        "type": "service_account",
        "project_id": os.getenv('GOOGLE_PROJECT_ID', ''),
        "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID', ''),
        "private_key": os.getenv('GOOGLE_PRIVATE_KEY', '').replace('\\n', '\n'),
        "client_email": os.getenv('GOOGLE_CLIENT_EMAIL', ''),
        "client_id": os.getenv('GOOGLE_CLIENT_ID', ''),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL', '')}",
        "universe_domain": "googleapis.com"
    }
    
    # Chỉ tạo file nếu có đủ thông tin
    if all([credentials_data['project_id'], credentials_data['private_key'], credentials_data['client_email']]):
        with open('credentials.json', 'w') as f:
            json.dump(credentials_data, f, indent=2)
        print("✅ Đã tạo credentials.json từ biến môi trường")
        return True
    else:
        print("❌ Thiếu thông tin Google Sheets credentials")
        return False

if __name__ == "__main__":
    create_credentials_from_env()
