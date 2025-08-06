# db.py
import mysql.connector
from mysql.connector import Error
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='credit_card_bot',
            user='root',
            password='RootPassword',
            charset='utf8mb4',
            port=3307
        )
        if connection.is_connected():
            logger.info('✅ 成功連接到 MySQL 資料庫')
            return connection
    except Error as e:
        logger.error(f'❌ 連接錯誤: {e}')
        return None
