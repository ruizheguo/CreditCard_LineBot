# recommender.py
import os
import logging
from typing import Optional
import json
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

def get_openai_client() -> OpenAI:
    """獲取 OpenAI 客戶端
    
    Returns:
        OpenAI 客戶端
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("🔑 請在 .env 裡設定 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)

async def get_async_openai_client() -> AsyncOpenAI: # <--- 新增一個非同步客戶端獲取函數
    """獲取非同步 OpenAI 客戶端"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("🔑 請在 .env 裡設定 OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key) # <--- 返回 AsyncOpenAI 實例


def recommend_stores_by_sentence(sentence, client: Optional[OpenAI] = None):
    # 如果沒有提供 client，則創建一個
    if client is None:
        client = get_openai_client()
        
    try:
        all_stores_prompt = (
           "根據輸入的句子，提取句中的商店。若未明言，則根據語意，先判斷其取向或商品"
           "判斷商品的範例：「我想買水果」判斷是「水果」就可以根據水果，推論出可能會賣水果的店家像是：「全聯」或「愛買」"
           "判斷取向的範例：「我想去日本」判斷是「旅遊取向」就可以根據服飾推論出「華航」或「雄獅旅遊」等旅遊相關商店"
           "推論出的商家必須要是網路上實際存在並查詢的到的商店名稱。最後得到商家1。"
           "請以 JSON 格式回傳，不要說明文字、引言、格式說明。例如：[商家1]"
        )
        response_all_stores = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            temperature=0.7,
            messages=[
                {"role": "system", "content": all_stores_prompt},
                {"role": "user", "content": sentence}
            ]
        )
        content_str = response_all_stores.choices[0].message.content.strip()
        content_all_stores = json.loads(content_str)
        content_extract = content_all_stores[0]

        
        return {
            "extracted_stores": content_extract,
        }
    except Exception as e:
        logger.error(f"推薦商店時發生錯誤: {e}")
        return {
            "extracted_stores": [],
        }