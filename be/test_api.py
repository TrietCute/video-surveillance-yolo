# test_api.py
import requests

API_URL = "http://127.0.0.1:8000/rooms"

# Dữ liệu JSON chính xác mà backend mong đợi
new_room_data = {"name": "Test Room From Script"}

print(f">>> Gửi dữ liệu: {new_room_data} đến {API_URL}")

try:
    # Gửi yêu cầu POST
    response = requests.post(API_URL, json=new_room_data)

    # In ra kết quả
    print(f"\n<<< Mã trạng thái nhận được: {response.status_code}")
    print(f"<<< Dữ liệu phản hồi:")
    print(response.json())

except requests.exceptions.RequestException as e:
    print(f"!!! Lỗi kết nối đến server: {e}")