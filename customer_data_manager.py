import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class CustomerDataManager:
    def __init__(self, data_file: str = 'customers.json'):
        self.data_file = data_file
        self.customers = self._load_customers()
    
    def _load_customers(self) -> List[Dict]:
        """Tải dữ liệu khách hàng từ file JSON"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Lỗi tải dữ liệu khách hàng: {e}")
            return []
    
    def _save_customers(self) -> bool:
        """Lưu dữ liệu khách hàng vào file JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.customers, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Lỗi lưu dữ liệu khách hàng: {e}")
            return False
    
    def add_customer(self, customer_data: Dict) -> bool:
        """Thêm khách hàng mới"""
        try:
            # Thêm timestamp
            customer_data['timestamp'] = datetime.now().isoformat()
            customer_data['id'] = len(self.customers) + 1
            
            # Thêm vào danh sách
            self.customers.append(customer_data)
            
            # Lưu file
            return self._save_customers()
        except Exception as e:
            print(f"Lỗi thêm khách hàng: {e}")
            return False
    
    def get_customer(self, user_id: int) -> Optional[Dict]:
        """Lấy thông tin khách hàng theo user_id"""
        for customer in self.customers:
            if customer.get('user_id') == user_id:
                return customer
        return None
    
    def update_customer(self, user_id: int, update_data: Dict) -> bool:
        """Cập nhật thông tin khách hàng"""
        try:
            for i, customer in enumerate(self.customers):
                if customer.get('user_id') == user_id:
                    self.customers[i].update(update_data)
                    self.customers[i]['updated_at'] = datetime.now().isoformat()
                    return self._save_customers()
            return False
        except Exception as e:
            print(f"Lỗi cập nhật khách hàng: {e}")
            return False
    
    def get_all_customers(self) -> List[Dict]:
        """Lấy tất cả khách hàng"""
        return self.customers
    
    def get_customers_count(self) -> int:
        """Đếm số lượng khách hàng"""
        return len(self.customers)
    
    def get_customers_today(self) -> int:
        """Đếm số khách hàng hôm nay"""
        today = datetime.now().date().isoformat()
        count = 0
        for customer in self.customers:
            if customer.get('timestamp', '').startswith(today):
                count += 1
        return count
    
    def export_to_csv(self, filename: str = None) -> str:
        """Xuất dữ liệu ra file CSV"""
        if not filename:
            filename = f"customers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                if self.customers:
                    fieldnames = self.customers[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.customers)
            return filename
        except Exception as e:
            print(f"Lỗi xuất CSV: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Lấy thống kê khách hàng"""
        total = self.get_customers_count()
        today = self.get_customers_today()
        
        # Thống kê theo nguồn
        sources = {}
        for customer in self.customers:
            source = customer.get('source', 'Không xác định')
            sources[source] = sources.get(source, 0) + 1
        
        return {
            'total': total,
            'today': today,
            'sources': sources,
            'last_updated': datetime.now().isoformat()
        }

# Khởi tạo global instance
customer_manager = CustomerDataManager()
