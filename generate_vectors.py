# generate_vectors.py
import os
import logging
import pickle  # 用於將 Python 物件序列化為二進位格式
from tqdm import tqdm # 好用的進度條工具，可用 pip install tqdm 安裝
from dotenv import load_dotenv
from openai import OpenAI
from db import create_connection

# 設定
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_embedding(text: str, client: OpenAI, model="text-embedding-3-large") -> list[float]:
    """獲取文字的 embedding 向量"""
    try:
        text = text.replace("\n", " ")
        response = client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"獲取 embedding 失敗 for text '{text}': {e}")
        return None

def main():
    """主執行函式"""
    logger.info("--- 開始執行離線向量生成腳本 ---")

    # 1. 建立連線
    conn = create_connection()
    if not conn:
        logger.error("❌ 無法連接到資料庫，腳本終止。")
        return

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    cursor = conn.cursor(dictionary=True)

    try:
        # 2. 找出所有尚未被向量化的店家
        logger.info("🔍 正在查詢尚未處理的店家...")
        query_select = "SELECT store FROM Main WHERE store_vector IS NULL"
        cursor.execute(query_select)
        stores_to_process = cursor.fetchall()

        if not stores_to_process:
            logger.info("✅ 所有店家皆已向量化，無需執行。")
            return

        logger.info(f"⏳ 找到 {len(stores_to_process)} 個新店家需要進行向量化...")

        # 3. 遍歷店家，獲取向量並更新回資料庫
        for row in tqdm(stores_to_process, desc="向量化進度"):
            store_name = row['store']

            # 獲取向量
            vector = get_embedding(store_name, client)

            if vector:
                # 將向量 list 序列化成二進位資料
                vector_blob = pickle.dumps(vector)

                # 準備 UPDATE 指令
                query_update = "UPDATE Main SET store_vector = %s WHERE store = %s"
                cursor.execute(query_update, (vector_blob, store_name))

        # 4. 提交所有變更
        conn.commit()
        logger.info("✅ 所有新店家的向量已成功生成並存入資料庫！")

    except Exception as e:
        logger.error(f"處理過程中發生嚴重錯誤: {e}")
        conn.rollback() # 出錯時回滾
    finally:
        cursor.close()
        conn.close()
        logger.info("--- 腳本執行完畢 ---")

if __name__ == '__main__':
    main()