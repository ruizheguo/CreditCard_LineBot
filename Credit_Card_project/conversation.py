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
    """確保使用者紀錄存在，對應您的 `_User` 表"""
    conn = create_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: 表格名稱從 `User` 改為 `_User`
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

def check_or_create_user(line_user_id: str) -> bool:
    """
    檢查使用者是否存在於 _User 資料表，如果不存在則新增。
    
    Args:
        line_user_id: Line 使用者的 ID。
    
    Returns:
        bool: 如果成功找到或新增使用者則返回 True，否則返回 False。
    """
    conn = create_connection()
    if not conn:
        logger.error("❌ 無法連接到資料庫。")
        return False

    cursor = conn.cursor()
    success = False

    try:
        # 檢查使用者是否存在
        cursor.execute("SELECT line_user_id FROM User WHERE line_user_id = %s", (line_user_id,))
        user = cursor.fetchone()

        if user:
            # 使用者已存在，無需新增
            success = True
            logger.debug(f"✅ 使用者 {line_user_id} 已存在。")
        else:
            # 使用者不存在，新增一筆記錄
            query = "INSERT INTO `User` (line_user_id) VALUES (%s)"
            cursor.execute(query, (line_user_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                success = True
                logger.info(f"✅ 成功為使用者 {line_user_id} 建立新紀錄。")
            else:
                success = False
                logger.warning(f"⚠️ 建立新使用者 {line_user_id} 失敗。")

    except Exception as e:
        logger.error(f"❌ 檢查或建立使用者時發生錯誤: {e}", exc_info=True)
        if conn and conn.is_connected():
            conn.rollback()
        success = False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    return success



def _get_user_pk(line_user_id: str) -> int | None:
    """根據 line_user_id 獲取主鍵 LineUserId_id"""
    conn = create_connection()
    if not conn:
        return None
        
    user_pk = None
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: 表格名稱從 `User` 改為 `_User`
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
    """
    根據業務ID (card_id) 獲取在 `UserCard` 表中要使用的主鍵 (CardId_id)。
    注意：這裡我們假設 `Card_Table` 中的 `card_id` 欄位就是 `UserCard` 中要用到的 `CardId_id`。
    如果 `Card_Table` 也有自己的獨立主鍵，這裡的邏輯需要調整。
    """
    conn = create_connection()
    if not conn:
        return None
        
    card_pk = None
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: 表格名稱從 `Card` 改為 `Card_Table`
        # 修改: 查詢的欄位改為 `card_id`，因為這是 UserCard 會用到的ID
        query = "SELECT card_id FROM `Card` WHERE card_id = %s"
        cursor.execute(query, (card_id,))
        row = cursor.fetchone()
        if row:
            # 修改: 返回的欄位是 `card_id`
            card_pk = row['card_id']
    except Error as e:
        logger.error(f"獲取卡片 PK 時發生錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return card_pk

def get_all_cards() -> list[dict]:
    """從 `Card_Table` 獲取所有卡片資料"""
    conn = create_connection()
    if not conn:
        return []
        
    cards = []
    try:
        cursor = conn.cursor(dictionary=True)
        # 修改: 表格名稱從 `Card` 改為 `Card_Table`
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
    """
    為指定使用者新增信用卡。
    使用 INSERT IGNORE 處理重複新增，並根據 cursor.rowcount 判斷是否成功。
    
    Args:
        line_user_id: Line 使用者的 ID。
        card_id: 信用卡 ID。
    
    Returns:
        bool: 如果成功新增一筆新紀錄則返回 True，否則返回 False。
    """
    conn = create_connection()
    if not conn:
        logger.error("❌ 無法連接到資料庫。")
        return False

    cursor = conn.cursor()
    success = False

    try:
        # 首先，查詢 line_user_id 和 card_id 對應的內部主鍵
        cursor.execute("SELECT LineUserId_id FROM User WHERE line_user_id = %s", (line_user_id,))
        user_pk = cursor.fetchone()
        
        # 檢查是否找到使用者
        if not user_pk:
            logger.warning(f"⚠️ 找不到使用者 LineUserId: {line_user_id}")
            return False
        user_pk = user_pk[0]

        cursor.execute("SELECT card_id FROM Card WHERE card_id = %s", (card_id,))
        card_pk = cursor.fetchone()
        
        # 檢查是否找到卡片
        if not card_pk:
            logger.warning(f"⚠️ 找不到卡片 ID: {card_id}")
            return False
        card_pk = card_pk[0]

        # 使用 INSERT IGNORE 語句
        query = "INSERT IGNORE INTO `UserCard` (LineUserId_id, CardId_id) VALUES (%s, %s)"
        cursor.execute(query, (user_pk, card_pk))
        
        # 提交變更
        conn.commit()

        # 檢查是否有行受到影響（即是否成功新增）
        if cursor.rowcount > 0:
            success = True
            logger.info(f"✅ 成功為使用者 {line_user_id} 新增卡片 ID: {card_id}")
        else:
            logger.warning(f"⚠️ 新增失敗：使用者 {line_user_id} 可能已擁有卡片 ID: {card_id}，未執行新增。")
            success = False

    except Exception as e:
        logger.error(f"❌ 新增卡片時發生錯誤: {e}", exc_info=True)
        conn.rollback() # 出錯時回滾事務
        success = False
    finally:
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
        query = "DELETE FROM `UserCard` WHERE LineUserId_id = %s AND CardId_id = %s"
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
            FROM `UserCard` uc
            JOIN `Card` c ON uc.CardId_id = c.card_id
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