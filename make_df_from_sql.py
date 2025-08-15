#我根據我的recommender抓出我要的資料並建立df
import os
import pandas as pd
import mysql.connector
from mysql.connector import Error
import logging
from dotenv import load_dotenv
from recommender import get_openai_client
import re
from openai import AsyncOpenAI # <--- 新增

# 引入 asyncio 以便並行運行協程
import asyncio # <--- 新增
# 載入環境變數
load_dotenv()

# Logging 設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 資料庫連線函數 - 作為備用方案
def create_connection(connection_pool=None):
    """創建資料庫連線（優先使用連線池，如果提供的話）
    
    Args:
        connection_pool: 資料庫連線池，如果提供則優先使用
        
    Returns:
        資料庫連線物件，如果連線失敗則返回 None
    """
    # 如果提供了連線池，則從連線池獲取連線
    if connection_pool is not None:
        try:
            connection = connection_pool.get_connection()
            logger.info("✅ 從連線池獲取 MySQL 連線成功")
            return connection
        except Error as e:
            logger.error(f"❌ 從連線池獲取連線錯誤: {e}")
    
    # 備用方案：直接建立連線
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "credit_card_bot"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "RootPassword"),
            charset="utf8mb4",
            port=int(os.getenv("DB_PORT", 3307))
        )
        if connection.is_connected():
            logger.info("✅ 成功連接到 MySQL 資料庫")
            return connection
    except Error as e:
        logger.error(f"❌ 資料庫連線錯誤: {e}")
        return None
    
#設定要抓的資料庫的表格

def fetch_tasks_for_user_with_join(conn, line_user_id: str, extracted_stores, table_name: str = 'Main') -> pd.DataFrame:
    """
    使用 JOIN 直接從資料庫獲取特定使用者的卡片任務。
    """
    df = pd.DataFrame()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 這個查詢會先 JOIN 4張表，再進行商店篩選
        query = f"""
            SELECT
                c.card_name ,m.store, m.task, m.basic_pt, m.bonus_pt, m.type, m.cooper, m.diver, m.note
            FROM
                {table_name} AS m
            JOIN
                Card AS c ON c.card_id = m.card_id
            JOIN
                UserCard AS uc ON uc.CardId_id = c.CardId_id
            JOIN
                User AS u ON u.LineUserId_id = uc.LineUserId_id
            WHERE
                u.line_user_id = %s AND m.store LIKE %s
        """
        params = (
            line_user_id,
            f"%{extracted_stores}%"
        )

        cursor.execute(query, params)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows)

        if df.empty:
            logger.warning(f"⚠️ 在使用者 {line_user_id} 的卡片中，找不到符合條件的資料")
        else:
            logger.info(f"✅ 成功為使用者 {line_user_id} 獲取到 {len(df)} 條個人化任務資料")
        
        cursor.close()
        return df

    except Error as e:
        logger.error(f"❌ 獲取使用者任務資料時發生錯誤: {e}")
        return df


def fetch_tasks_from_db(conn, extracted_stores,table_name:str='Main') -> pd.DataFrame:
    """從資料庫獲取任務資料
    
    Args:
        conn: 資料庫連線
        table_name: 資料表名稱
        
    Returns:
        包含任務資料的 DataFrame
    """
    df = pd.DataFrame()
    try:
        cursor = conn.cursor(dictionary=True)
        query = f"""
        SELECT
            c.card_name, m.store, m.task, m.basic_pt, m.bonus_pt, m.type, m.cooper, m.diver, m.note
        FROM
            {table_name} AS m
        JOIN
            Card AS c ON c.card_id = m.card_id
        WHERE m.store LIKE %s
        """
        params = (
            f"%{extracted_stores}%",
)
        cursor.execute(query,params)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows)
        if df.empty:
            logger.warning(f"⚠️ 資料表 {table_name} 中沒有資料")
        else:
            logger.info(f"✅ 從資料表 {table_name} 獲取到 {len(df)} 條任務資料")
        cursor.close()
        return df
    
    except Error as e:
        logger.error(f"❌ 獲取任務資料錯誤: {e}")
        return df

# -----------------------

async def add_ai_scores_async(df, openai_client_async=None, model="gpt-3.5-turbo-1106", temperature=0.4,seed=3): # <--- 函數名稱變更為 add_ai_scores_async
    if openai_client_async is None:
        # 獲取非同步的 OpenAI 客戶端實例
        # 您需要修改 get_openai_client() 來返回 AsyncOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("🔑 請在 .env 裡設定 OPENAI_API_KEY")
        openai_client_async = AsyncOpenAI(api_key=api_key) # <--- 使用 AsyncOpenAI
    tasks_to_evaluate = []
    for index, row in df.iterrows(): # 使用 index 以便之後將結果放回正確的位置
        task = row["task"]
        tasks_to_evaluate.append((index, task))

    # 定義一個內部協程來處理單個任務的評分
    async def evaluate_single_task(task_index, task_content):
        try:
            logger.info(f"🧠 評估任務內容中：{task_content}")
            response = await openai_client_async.chat.completions.create( # <--- 使用 await
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位精準的任務分析師。請從我提供的內容，根據「執行難度」、「執行的時間」與「機會成本」給出 1~5 分，其中 5 分為難度最低越值得去做，1 分為難度最高越不值得做，取到小數點第二位。"
                        "最後只以「分數：X.X」的固定格式回傳，不要有說明、引言等其他文字，例如：「分數：3.45」。"
                    },
                    {"role": "user", "content": task_content}
                ],
                temperature=temperature,
                seed=seed
            )

            content = response.choices[0].message.content
            print(f"AI 評分回應：{content}") # 可以調整日誌輸出
            match = re.search(r"分數[:：]?\s*([1-5]\.\d{0,2})", content)
            score = float(match.group(1)) if match else 5
            print(f"評分完成：{score} for task: {task_content}")

        except Exception as e:
            logger.error(f"❌ 任務評分失敗（{task_content}）：{e}")
            score = 0.0
        return task_index, score
        
    # 使用 asyncio.gather 來並行運行所有評估任務
    # 將所有 evaluate_single_task 協程加入到一個列表中
    evaluation_coroutines = [evaluate_single_task(idx, task_content) for idx, task_content in tasks_to_evaluate]

    # 同步等待所有協程完成，並收集結果
    # results 會是一個包含 (index, score) 元組的列表
    all_scores_with_index = await asyncio.gather(*evaluation_coroutines)

    # 將結果按照原始 DataFrame 的索引順序放回 scores 列表中
    # 可以創建一個新的 Series 或直接映射回 DataFrame
    scores_dict = {idx: score for idx, score in all_scores_with_index}
    df["task_score"] = df.index.map(scores_dict) # 確保按照索引正確匹配
    logger.info(f"✅ 完成對 {len(df)} 條任務的 AI 評分。")
    return df

