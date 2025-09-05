import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Import bot_config.py
import bot_config
import time
import traceback


class GoogleSheetsManager:
    def __init__(self):
        self.credentials = None
        self.service = None
        self.spreadsheet_id = bot_config.SPREADSHEET_ID
        self.worksheet_name = bot_config.WORKSHEET_NAME
        self._authenticate()

    def _authenticate(self):
        """Xác thực với Google Sheets API"""
        try:
            if os.path.exists(bot_config.GOOGLE_SHEETS_CREDENTIALS_FILE):
                self.credentials = Credentials.from_service_account_file(
                    bot_config.GOOGLE_SHEETS_CREDENTIALS_FILE,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets'
                    ]
                )
                self.service = build(
                    'sheets', 'v4', credentials=self.credentials
                )
            else:
                print("⚠️ Không tìm thấy file credentials.json - "
                      "Google Sheets bị vô hiệu hóa")
                print("💡 Tạo file credentials.json để kích hoạt "
                      "tính năng Google Sheets")
        except Exception as e:
            print(f"❌ Lỗi xác thực Google Sheets: {e}")

    def _get_worksheet_id(self):
        """Lấy ID của worksheet"""
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == self.worksheet_name:
                    return sheet['properties']['sheetId']

            return None
        except Exception as e:
            print(f"❌ Lỗi lấy worksheet ID: {e}")
            return None

    def create_worksheet_if_not_exists(self):
        """Tạo worksheet nếu chưa tồn tại"""
        try:
            # Kiểm tra worksheet có tồn tại không
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            worksheet_exists = any(
                sheet['properties']['title'] == self.worksheet_name
                for sheet in spreadsheet['sheets']
            )

            if not worksheet_exists:
                # Tạo worksheet mới
                request = {
                    'addSheet': {
                        'properties': {
                            'title': self.worksheet_name
                        }
                    }
                }

                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()

                # Thêm header theo cấu trúc mới
                headers = [
                    'User ID', 'Username', 'Full Name', 'Time', 'Action', 'Chat ID', 'Message Type'
                ]
                self.add_row(headers)

                print(f"✅ Đã tạo worksheet '{self.worksheet_name}'")

        except Exception as e:
            print(f"❌ Lỗi tạo worksheet: {e}")

    def _execute_with_retry(self, func, *args, retries: int = 3, backoff: float = 1.0, **kwargs):
        """Thực thi request với cơ chế retry để chịu transient errors."""
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                print(f"⚠️ GoogleSheets request failed (attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    time.sleep(backoff * attempt)
                else:
                    print(f"❌ All retries failed: {e}")
        # raise the last exception so caller can handle/log
        raise last_exc

    def add_customer(self, customer_data):
        """Thêm khách hàng mới vào Google Sheets (không trùng lặp)"""
        print(f"📝 add_customer called with: {customer_data}")
        try:
            if not self.service:
                print("❌ Google Sheets không khả dụng - bỏ qua việc lưu dữ liệu")
                return False

            # Tạo worksheet nếu chưa có
            self.create_worksheet_if_not_exists()

            # Kiểm tra trùng lặp trước khi thêm
            user_id = customer_data.get('user_id', '')
            if not user_id:
                print("⚠️ Không có User ID - bỏ qua")
                return False

            existing_row = self._is_user_exists(user_id)
            if existing_row:
                # Khách hàng đã tồn tại - cập nhật thông tin
                print(f"🔄 Khách hàng đã tồn tại (User ID: {user_id}) - cập nhật thông tin mới")
                return self.update_customer(customer_data)

            # Khách hàng mới - thêm mới
            row_data = [
                user_id,
                customer_data.get('username', ''),
                customer_data.get('full_name', ''),
                customer_data.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                customer_data.get('action', ''),
                customer_data.get('chat_id', ''),
                customer_data.get('message_type', '')
            ]

            range_name = f"{self.worksheet_name}!A:G"
            body = {'values': [row_data]}

            # Thực hiện append với retry
            try:
                self._execute_with_retry(
                    lambda: self.service.spreadsheets().values().append(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        insertDataOption='INSERT_ROWS',
                        body=body
                    ).execute()
                )
            except Exception as e:
                print(f"❌ Lỗi khi append row cho user {user_id}: {e}")
                traceback.print_exc()
                return False

            print(f"✅ Đã thêm khách hàng mới: {customer_data.get('full_name', 'Unknown')} (User ID: {user_id})")
            return True

        except Exception as e:
            print(f"❌ Lỗi thêm khách hàng: {e}")
            traceback.print_exc()
            return False

    def _is_user_exists(self, user_id):
        """Kiểm tra xem user_id đã tồn tại chưa và trả về vị trí dòng"""
        try:
            if not self.service:
                return None

            range_name = f"{self.worksheet_name}!A:A"

            try:
                result = self._execute_with_retry(
                    lambda: self.service.spreadsheets().values().get(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name
                    ).execute()
                )
            except Exception as e:
                print(f"❌ Lỗi khi lấy cột A để kiểm tra trùng lặp: {e}")
                traceback.print_exc()
                return None

            values = result.get('values', [])

            # Bỏ qua header (dòng đầu tiên)
            if values and len(values) > 1:
                for i, row in enumerate(values[1:], 2):  # Bắt đầu từ dòng 2 (sau header)
                    if row and row[0] and str(row[0]) == str(user_id):
                        return i

            return None

        except Exception as e:
            print(f"❌ Lỗi kiểm tra trùng lặp: {e}")
            traceback.print_exc()
            return None

    def update_customer(self, customer_data):
        """Cập nhật thông tin khách hàng nếu đã tồn tại"""
        try:
            if not self.service:
                return False

            user_id = customer_data.get('user_id', '')
            if not user_id:
                return False

            row_number = self._is_user_exists(user_id)
            if not row_number:
                return False

            row_data = [
                user_id,
                customer_data.get('username', ''),
                customer_data.get('full_name', ''),
                customer_data.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                customer_data.get('action', ''),
                customer_data.get('chat_id', ''),
                customer_data.get('message_type', '')
            ]

            range_name = f"{self.worksheet_name}!A{row_number}:G{row_number}"
            body = {'values': [row_data]}

            try:
                self._execute_with_retry(
                    lambda: self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body=body
                    ).execute()
                )
            except Exception as e:
                print(f"❌ Lỗi khi update row {row_number} cho user {user_id}: {e}")
                traceback.print_exc()
                return False

            print(f"✅ Đã cập nhật khách hàng: {customer_data.get('full_name', 'Unknown')} (User ID: {user_id})")
            return True

        except Exception as e:
            print(f"❌ Lỗi cập nhật khách hàng: {e}")
            traceback.print_exc()
            return False

    def add_row(self, row_data):
        """Thêm một dòng dữ liệu"""
        try:
            if not self.service:
                return False

            range_name = f"{self.worksheet_name}!A:G"
            body = {'values': [row_data]}

            try:
                self._execute_with_retry(
                    lambda: self.service.spreadsheets().values().append(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        insertDataOption='INSERT_ROWS',
                        body=body
                    ).execute()
                )
            except Exception as e:
                print(f"❌ Lỗi thêm dòng: {e}")
                traceback.print_exc()
                return False

            return True

        except Exception as e:
            print(f"❌ Lỗi thêm dòng: {e}")
            traceback.print_exc()
            return False

    def get_customer_stats(self):
        """Lấy thống kê khách hàng"""
        try:
            if not self.service:
                return None

            range_name = f"{self.worksheet_name}!A:A"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                return {
                    'total': 0,
                    'today': 0,
                    'week': 0,
                    'month': 0
                }

            # Bỏ qua header
            total_customers = len(values) - 1

            # Tính khách hàng theo thời gian
            today = datetime.now().date()
            today_count = 0
            week_count = 0
            month_count = 0

            for i, row in enumerate(values[1:], 1):  # Bỏ qua header
                if row and len(row) > 0:
                    try:
                        date_str = row[3] if len(row) > 3 else ''  # Time field is at index 3
                        if date_str:
                            customer_date = datetime.strptime(
                                date_str.split()[0], '%Y-%m-%d'
                            ).date()

                            if customer_date == today:
                                today_count += 1

                            # Tuần này (7 ngày qua)
                            if (today - customer_date).days <= 7:
                                week_count += 1

                            # Tháng này
                            if (today - customer_date).days <= 30:
                                month_count += 1
                    except Exception:
                        continue

            return {
                'total': total_customers,
                'today': today_count,
                'week': week_count,
                'month': month_count
            }

        except Exception as e:
            print(f"❌ Lỗi lấy thống kê: {e}")
            return None

    def search_customer(self, search_term):
        """Tìm kiếm khách hàng"""
        try:
            if not self.service:
                return None

            range_name = f"{self.worksheet_name}!A:G"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                return None

            search_term = search_term.lower()
            found_customers = []

            for i, row in enumerate(values[1:], 1):  # Bỏ qua header
                if len(row) >= 3:  # Ít nhất có User ID, Username, Full Name
                    user_id = row[0] if len(row) > 0 else ''
                    username = row[1].lower() if len(row) > 1 else ''
                    full_name = row[2].lower() if len(row) > 2 else ''

                    if search_term in username or search_term in full_name:
                        found_customers.append({
                            'row': i + 1,
                            'user_id': user_id,
                            'username': row[1] if len(row) > 1 else '',
                            'full_name': row[2] if len(row) > 2 else '',
                            'action': row[4] if len(row) > 4 else '',
                            'time': row[3] if len(row) > 3 else ''
                        })

            return found_customers

        except Exception as e:
            print(f"❌ Lỗi tìm kiếm khách hàng: {e}")
            return None

    def export_to_excel(self, filename='customers_export.xlsx'):
        """Xuất dữ liệu ra file Excel"""
        try:
            import pandas as pd

            if not self.service:
                return False

            range_name = f"{self.worksheet_name}!A:G"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                return False

            # Tạo DataFrame
            headers = [
                'User ID', 'Username', 'Full Name', 'Time', 'Action', 'Chat ID', 'Message Type'
            ]

            df = pd.DataFrame(values[1:], columns=headers)
            df.to_excel(filename, index=False)

            print(f"✅ Đã xuất dữ liệu ra file: {filename}")
            return True

        except Exception as e:
            print(f"❌ Lỗi xuất Excel: {e}")
            return False

    def get_all_customers(self):
        """Lấy danh sách tất cả khách hàng"""
        try:
            if not self.service:
                return None

            range_name = f"{self.worksheet_name}!A:G"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                return []

            customers = []
            for i, row in enumerate(values[1:], 1):  # Bỏ qua header
                if len(row) >= 3:  # Ít nhất có User ID, Username, Full Name
                    customers.append({
                        'row': i + 1,
                        'user_id': row[0] if len(row) > 0 else '',
                        'username': row[1] if len(row) > 1 else '',
                        'full_name': row[2] if len(row) > 2 else '',
                        'action': row[4] if len(row) > 4 else '',
                        'time': row[3] if len(row) > 3 else '',
                        'chat_id': row[5] if len(row) > 5 else '',
                        'message_type': row[6] if len(row) > 6 else ''
                    })

            return customers

        except Exception as e:
            print(f"❌ Lỗi lấy danh sách khách hàng: {e}")
            return None

    def get_customers_by_filter(self, filter_type=None, filter_value=None):
        """Lấy khách hàng theo bộ lọc"""
        try:
            customers = self.get_all_customers()
            if not customers:
                return []

            if not filter_type or not filter_value:
                return customers

            filtered_customers = []
            for customer in customers:
                if filter_type == 'action' and customer.get('action') == filter_value:
                    filtered_customers.append(customer)
                elif filter_type == 'date' and customer.get('time', '').startswith(filter_value):
                    filtered_customers.append(customer)
                elif filter_type == 'username' and filter_value.lower() in customer.get('username', '').lower():
                    filtered_customers.append(customer)

            return filtered_customers

        except Exception as e:
            print(f"❌ Lỗi lọc khách hàng: {e}")
            return []

    def update_customer_message_status(self, user_id, message_sent=True, message_type='bulk_message'):
        """Cập nhật trạng thái tin nhắn đã gửi"""
        try:
            if not self.service:
                return False

            # Tìm khách hàng theo user_id
            customers = self.get_all_customers()
            if not customers:
                return False

            for customer in customers:
                if customer.get('user_id') == str(user_id):
                    row_number = customer['row']

                    # Cập nhật trạng thái tin nhắn
                    range_name = f"{self.worksheet_name}!H{row_number}"
                    body = {
                        'values': [['Đã gửi' if message_sent else 'Chưa gửi']]
                    }

                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body=body
                    ).execute()

                    print(f"✅ Đã cập nhật trạng thái tin nhắn cho user {user_id}")
                    return True

            return False

        except Exception as e:
            print(f"❌ Lỗi cập nhật trạng thái tin nhắn: {e}")
            return False

    def add_message_log(self, user_id, message_content, message_type='bulk_message', status='sent'):
        """Ghi log tin nhắn đã gửi"""
        try:
            if not self.service:
                return False

            # Tạo worksheet log nếu chưa có
            log_worksheet = f"{self.worksheet_name}_Log"

            # Kiểm tra worksheet log có tồn tại không
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            log_exists = any(
                sheet['properties']['title'] == log_worksheet
                for sheet in spreadsheet['sheets']
            )

            if not log_exists:
                # Tạo worksheet log mới
                request = {
                    'addSheet': {
                        'properties': {
                            'title': log_worksheet
                        }
                    }
                }

                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()

                # Thêm header cho log
                headers = ['Timestamp', 'User ID', 'Message Type', 'Message Content', 'Status']
                self._add_log_row(log_worksheet, headers)

            # Thêm log tin nhắn
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_data = [timestamp, user_id, message_type, message_content, status]
            self._add_log_row(log_worksheet, log_data)

            return True

        except Exception as e:
            print(f"❌ Lỗi ghi log tin nhắn: {e}")
            return False

    def _add_log_row(self, worksheet_name, row_data):
        """Thêm dòng vào worksheet log"""
        try:
            range_name = f"{worksheet_name}!A:E"
            body = {
                'values': [row_data]
            }

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return True

        except Exception as e:
            print(f"❌ Lỗi thêm dòng log: {e}")
            return False
