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
            "根據輸入的句子，提取句中的商店。若未明言，則根據語意，先判斷其取向，例如：「我想出國旅行」判斷是「旅遊」，則根據旅遊推論出「中華航空」或「雄獅旅遊」；「我想買水果」判斷是「生活食品」則根據生活食品推論出「全聯」或「愛買」。"
            "得出商店後查詢其是否有其他名稱，有的話則以最簡短且具辨別性的名稱優先提取為「商家名稱」，例如：推論出的商店為「台北101購物中心」，且該店之其他名稱為「台北101」、「台北101百貨」，則只提取「台北101」此一名稱；推論出的商店為「王品牛排」，且該店之其他名稱為「王品」、「王品集團」，則只提取「王品」此一名稱。"
            "若根據語意判斷是在其他國家中消費，則只提取該國家而不提取商店，並將「『國家名稱』實體商店」作為「商家名稱」，例如：「我想去日本玩」判斷是在「日本」消費，則「商家名稱」為「日本實體商店」。"
            "最後以 JSON 格式回傳，不要有說明、引言等其他文字，只會有一個商店名稱的項目，例如：[商家名稱]。"
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
        content_store = json.loads(content_str)
        content_extract = content_store[0]
        logger.info(f"推薦商店: {content_extract}")
        
        return {
            "extracted_stores": content_extract
        }
    except Exception as e:
        logger.error(f"推薦商店時發生錯誤: {e}")
        return {
            "extracted_stores": [],
        }