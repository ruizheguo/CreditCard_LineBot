# recommender.py
import os
import logging
import numpy as np
import pickle
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
import logging
from typing import Optional
import json

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

# --- 1. 應用程式級別的全域快取 ---
# 這個變數會在應用程式啟動時被填滿一次，之後的所有請求都會共用它
APP_WIDE_VECTORS_CACHE = {}


# --- 2. 補回必要的輔助函式 ---

def get_openai_client() -> OpenAI:
    """獲取 OpenAI 客戶端"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("🔑 請在 .env 裡設定 OPENAI_API_KEY")
    return OpenAI(api_key=api_key)

def get_embedding(text: str, client: OpenAI, model="text-embedding-3-small") -> list[float]:
    """獲取單一段落文字的 embedding 向量"""
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """計算兩個向量的餘弦相似度"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# --- 3. 專門用於啟動時載入的函式 ---

def load_vectors_into_global_cache(conn):
    """
    【資料庫版】
    從資料庫讀取向量，並直接載入到全域變數 APP_WIDE_VECTORS_CACHE 中。
    這個函式應該只在應用程式啟動時執行一次。
    """
    global APP_WIDE_VECTORS_CACHE
    if APP_WIDE_VECTORS_CACHE: # 如果快取已存在，就不要重複載入
        logger.info("✅ 全域向量快取已存在，跳過載入。")
        return

    logger.info("⏳ 正在從資料庫載入預先計算好的店家向量至全域快取...")
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT store, store_vector FROM Main WHERE store_vector IS NOT NULL;"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        temp_cache = {}
        for row in rows:
            store_name = row['store']
            vector_blob = row['store_vector']
            vector = pickle.loads(vector_blob)
            temp_cache[store_name] = vector
        
        APP_WIDE_VECTORS_CACHE = temp_cache
        logger.info(f"✅ 成功將 {len(APP_WIDE_VECTORS_CACHE)} 個店家向量載入到全域快取。")

    except Exception as e:
        logger.error(f"❌ 從資料庫載入向量到全域快取時發生錯誤: {e}")


# --- 4. 改造後提供給 app.py 呼叫的主函式 ---

def find_best_matching_store_vector(sentence: str):
    """
    【高效版】
    使用已載入到記憶體的全域快取進行向量比對。
    不再需要傳入 conn 物件。
    """
    # 檢查全域快取是否已準備好
    if not APP_WIDE_VECTORS_CACHE:
        logger.error("店家向量全域快取為空，無法進行比對。請檢查應用程式啟動流程。")
        return {"extracted_stores": []}

    client = get_openai_client()
    try:
        # 1. 向量化使用者句子 (這部分不變)
        query_vector = get_embedding(sentence, client)

        # 2. 計算所有店家的相似度分數，並存入一個列表
        all_scores = []
        for store_name, store_vector in APP_WIDE_VECTORS_CACHE.items():
            similarity = cosine_similarity(query_vector, store_vector)
            # 將 (分數, 店家名稱) 作為一個元組存起來，方便後續排序
            all_scores.append((similarity, store_name))
        
        # 3. 根據分數(元組的第一個元素 a[0])由高到低進行排序
        all_scores.sort(key=lambda a: a[0], reverse=True)

        # 4. 取出前 K (top_k=5) 個結果
        top_k = 5
        top_results = all_scores[:top_k]

        # --- 5. 根據您的要求，印出前 K 名的分數 ---
        print("--- Top-K 向量比對結果 ---")
        if not top_results:
            print("沒有任何比對結果。")
        else:
            for score, name in top_results:
                print(f"店家: {name}, 相似度分數: {score:.4f}")
        print("------------------------")
        # --- Print 結束 ---

        # 6. 過濾掉分數低於門檻的結果，並只保留店家名稱
        similarity_threshold = 0.1 # 建議保留一個合理的門檻，避免不相關的結果
        
        extracted_stores_list = [
            name for score, name in top_results if score > similarity_threshold
        ]
        
        # 7. 回傳結果
        if extracted_stores_list:
            # 如果有符合條件的店家，回傳第一個店家名稱
            return {"extracted_stores": extracted_stores_list[0]}
        else:
            # 如果過濾後沒有任何結果，也回傳空列表
            logger.warning(f"所有匹配結果均未達門檻 {similarity_threshold}，視為無匹配結果。")
            return {"extracted_stores": []}

    except Exception as e:
        logger.error(f"向量搜尋過程中發生錯誤: {e}")
        return {"extracted_stores": []}


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
            temperature=0.4,
            seed=1,
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