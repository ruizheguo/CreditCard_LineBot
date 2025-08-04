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
            database='card_db',
            user='root',
            password='pythongeneration',
            charset='utf8mb4',
            port=3307
        )
        if connection.is_connected():
            logger.info('✅ 成功連接到 MySQL 資料庫')
            return connection
    except Error as e:
        logger.error(f'❌ 連接錯誤: {e}')
        return None
