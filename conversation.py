# conversation.py (已根據您的資料表設計修改)
import logging
from db import create_connection
from mysql.connector import Error

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 使用者狀態管理 (這部分不變)
user_state = {}

def set_state(line_user_id: str, action: str, step: str):
    user_state[line_user_id] = {'action': action, 'step': step}
    logger.info(f"使用者 {line_user_id} 的狀態已設定為: {user_state[line_user_id]}")

def get_state(line_user_id: str):
    return user_state.get(line_user_id)

def clear_state(line_user_id: str):
    if line_user_id in user_state:
        del user_state[line_user_id]
        logger.info(f"已清除使用者 {line_user_id} 的狀態。")

# --- 資料庫操作 (已修改對應您的資料表) ---

def ensure_user_record(line_user_id: str):
    """確保使用者紀錄存在，對應您的 `User` 表"""
    conn = create_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        # 欄位名稱 `line_user_id` 保持不變
        query = "INSERT IGNORE INTO `User` (line_user_id) VALUES (%s)"
        cursor.execute(query, (line_user_id,))
        conn.commit()
        logger.info(f"已確認資料庫中存在使用者紀錄: {line_user_id}")
    except Error as e:
        logger.error(f"確保使用者紀錄時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def _get_user_pk(line_user_id: str) -> int | None:
    """根據 line_user_id 獲取主鍵 LineUserId_id"""
    conn = create_connection()
    if not conn:
        return None
        
    user_pk = None
    try:
        cursor = conn.cursor(dictionary=True)
        # 查詢的欄位 LineUserId_id 和 line_user_id 保持不變
        query = "SELECT LineUserId_id FROM `User` WHERE line_user_id = %s"
        cursor.execute(query, (line_user_id,))
        row = cursor.fetchone()
        if row:
            # 欄位名稱 `LineUserId_id` 符合您的設計，不需更改
            user_pk = row['LineUserId_id']
    except Error as e:
        logger.error(f"獲取使用者 PK 時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return user_pk

def _get_card_pk(card_id: int) -> int | None:
    """根據業務ID (card_id) 獲取在 `UserCard` 表中要使用的主鍵 (CardId_id)"""
    conn = create_connection()
    if not conn:
        return None
        
    card_pk = None
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: 查詢的欄位改為 `CardId_id`，因為這是 UserCard 會用到的ID
        query = "SELECT CardId_id FROM `Card` WHERE card_id = %s"
        cursor.execute(query, (card_id,))
        row = cursor.fetchone()
        if row:
            # 修改: 返回的欄位是 `card_id`
            card_pk = row['CardId_id']
    except Error as e:
        logger.error(f"獲取卡片 PK 時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return card_pk

def get_all_cards() -> list[dict]:
    """從 `Card` 獲取所有卡片資料"""
    conn = create_connection()
    if not conn:
        return []
        
    cards = []
    try:
        cursor = conn.cursor(dictionary=True)
        # 查詢的欄位 card_id, bank_name, card_name 符合您的設計，不需更改
        query = "SELECT card_id, bank_name, card_name FROM `Card`"
        cursor.execute(query)
        cards = cursor.fetchall()
    except Error as e:
        logger.error(f"獲取所有卡片時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return cards

def add_user_card(line_user_id: str, card_id: int) -> bool:
    """為使用者新增卡片，操作 `UserCard` 表"""
    ensure_user_record(line_user_id)
    user_pk = _get_user_pk(line_user_id)
    card_pk = _get_card_pk(card_id)

    if not user_pk or not card_pk:
        logger.warning(f"無法新增卡片：找不到使用者 PK ({user_pk}) 或卡片 PK ({card_pk})")
        return False

    conn = create_connection()
    if not conn:
        return False
        
    success = False
    try:
        cursor = conn.cursor()
        # 修改: 查詢的欄位改為 `LineUserId_id` 和 `CardId_id` 以符合您的設計
        # 表格名稱 `UserCard` 符合您的設計，不需更改
        query = "INSERT IGNORE INTO `UserCard` (LineUserId_id, CardId_id) VALUES (%s, %s)"
        cursor.execute(query, (user_pk, card_pk))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"成功為使用者 {line_user_id} 新增卡片 ID: {card_id}")
        else:
            logger.warning(f"使用者 {line_user_id} 可能已擁有卡片 ID: {card_id}，未執行新增。")
    except Error as e:
        logger.error(f"新增使用者卡片時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return success

def delete_user_card(line_user_id: str, card_id: int) -> bool:
    """刪除使用者的卡片，操作 `UserCard` 表"""
    user_pk = _get_user_pk(line_user_id)
    card_pk = _get_card_pk(card_id)

    if not user_pk or not card_pk:
        logger.warning(f"無法刪除卡片：找不到使用者 PK ({user_pk}) 或卡片 PK ({card_pk})")
        return False

    conn = create_connection()
    if not conn:
        return False
        
    success = False
    try:
        cursor = conn.cursor()
        # 修改: 查詢的欄位改為 `LineUserId_id` 和 `CardId_id`
        query = "DELETE uc FROM `UserCard` uc WHERE LineUserId_id = %s AND CardId_id = %s"
        cursor.execute(query, (user_pk, card_pk))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"成功為使用者 {line_user_id} 刪除卡片 ID: {card_id}")
        else:
            logger.warning(f"使用者 {line_user_id} 未擁有卡片 ID: {card_id}，未執行刪除。")
    except Error as e:
        logger.error(f"刪除使用者卡片時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return success

def get_user_cards(line_user_id: str) -> list[str]:
    """獲取使用者擁有的所有卡片名稱"""
    user_pk = _get_user_pk(line_user_id)
    if not user_pk:
        return []

    conn = create_connection()
    if not conn:
        return []
        
    card_names = []
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: JOIN 的表格和欄位名稱全部更新為您的設計
        query = """
            SELECT c.card_name 
            FROM `Card` c
            JOIN `UserCard` uc ON uc.CardId_id = c.CardId_id
            WHERE uc.LineUserId_id = %s
        """
        cursor.execute(query, (user_pk,))
        rows = cursor.fetchall()
        card_names = [row['card_name'] for row in rows]
    except Error as e:
        logger.error(f"獲取使用者卡片時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return card_names