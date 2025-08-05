import os
import requests
import json
from dotenv import load_dotenv
from linebot.v3.messaging import (
    MessagingApi, 
    RichMenuRequest, 
    ApiClient, 
    Configuration,
    ApiException
)
# 建議也引入 SDK 的錯誤類別，雖然此例中主要會觸發 requests 的錯誤

from manage_richmenu import create_rich_menu_config

load_dotenv()

def upload_and_set_rich_menu():
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("❌ .env 沒有設定 LINE_CHANNEL_ACCESS_TOKEN")

    configuration = Configuration(access_token=access_token)
    api_client = ApiClient(configuration)
    messaging_api = MessagingApi(api_client)

    rich_menu_id = None # 先宣告變數，以便在 exception 區塊中使用
    try:
        # 1. 建立圖文選單結構
        print("1. 正在建立圖文選單結構...")
        rich_menu_request: RichMenuRequest = create_rich_menu_config()
        
        # 【修正點 1】從回傳的物件中，正確取出 .rich_menu_id 字串
        rich_menu_id_response = messaging_api.create_rich_menu(rich_menu_request)
        rich_menu_id = rich_menu_id_response.rich_menu_id
        print(f"✅ 成功建立圖文選單，ID: {rich_menu_id}")

        # 您是 Mac 使用者，請確認此絕對路徑正確
        image_path = "/Users/wdwddaniel/Desktop/creditcard_not_code/image/all3.jpg"
        if os.path.exists(image_path):
            print("2. 正在上傳圖片 (使用 requests)...")
            
            # 【修正點 2】圖片上傳的 Hostname 應為 "api-data.line.me"
            upload_image_url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"

            image_headers = {
                'Content-Type': 'image/jpeg',  # 確保 Content-Type 正確
                'Authorization': f'Bearer {access_token}'
            }

            with open(image_path, 'rb') as f:
                # 這段 requests 的邏輯是您原本的，現在應該可以正常運作
                image_response = requests.post(upload_image_url, headers=image_headers, data=f)
                # raise_for_status() 會在收到 4xx 或 5xx 狀態碼時拋出例外
                image_response.raise_for_status()
            
            print(f"✅ 成功上傳圖片至圖文選單 {rich_menu_id}")
        else:
            print(f"⚠️ 找不到圖片檔案：{image_path}")
            # 如果找不到圖片，建議刪除剛建立的空選單
            if rich_menu_id:
                messaging_api.delete_rich_menu(rich_menu_id)
                print(f"🗑️ 已將空圖文選單 {rich_menu_id} 刪除。")
            return

        # 3. 設定為預設圖文選單
        print("3. 正在設定為預設圖文選單...")
        # 這裡的 rich_menu_id 也因為修正而變為正確的字串了
        messaging_api.set_default_rich_menu(rich_menu_id)
        print(f"✅ 設定 {rich_menu_id} 為預設 rich menu 成功！")

    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP 請求錯誤: {e}")
        if e.response is not None:
            print(f"❌ 錯誤狀態碼: {e.response.status_code}")
            try:
                # LINE API 的錯誤回應通常是 JSON 格式
                error_details = e.response.json()
                print(f"❌ API 錯誤細節: {error_details}")
            except json.JSONDecodeError:
                print(f"❌ API 回應內容 (非JSON): {e.response.text}")
        
        # 如果發生錯誤，且已建立選單ID，就嘗試刪除它，避免遺留垃圾資料
        if rich_menu_id:
            print(f"正在嘗試刪除建立失敗的圖文選單 {rich_menu_id}...")
            try:
                messaging_api.delete_rich_menu(rich_menu_id)
                print(f"🗑️ 成功刪除圖文選單 {rich_menu_id}。")
            except ApiException as del_e:
                print(f"🗑️ 刪除圖文選單 {rich_menu_id} 失敗: {del_e.body}")
                
    except Exception as e:
        print(f"❌ 發生未預期的錯誤：{e}")

if __name__ == "__main__":
    upload_and_set_rich_menu()