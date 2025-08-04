# recommender.py
import os
import logging
from typing import Optional
import json
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
from safe_utils import safe_json_parse

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
           "根據輸入的句子，提取句中的商店。若未明言，則根據語意推論可能的實際商店名稱，例如：我想去日本玩，可以推測「中華航空」或「雄獅旅遊」。最後得到商家1。"
           "限制：商家須為台灣實際存在、具名品牌，且網路可查。不可回傳泛稱（如「水果攤」、「餐廳」）。"
           "查詢「商家1」的性質，依其性質推薦另外兩家在台灣「性質相近、網路上找得到商家」得到商店2、商店3"
           "回傳時只輸出這三間商店，以請以 JSON 格式回傳，不要說明文字、引言、格式說明。例如：[商家1,商店2,商店3]"
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
        content_recommend1 = content_all_stores[1]
        content_recommend2 = content_all_stores[2]
        
        return {
            "extracted_stores": content_extract,
            "recommend_store1": content_recommend1,
            "recommend_store2": content_recommend2
        }
    except Exception as e:
        logger.error(f"推薦商店時發生錯誤: {e}")
        return {
            "extracted_stores": [],
            "recommend_store1": None,
            "recommend_store2": None
        }