import pymysql
from config import DB_CONFIG

# In-memory user session state
# user_state: { line_user_id: { action: "add"/"delete", step: "input_card" } }
user_state = {}

def set_state(line_user_id, action):
    user_state[line_user_id] = { 'action': action, 'step': 'input_card' }

def get_state(line_user_id):
    return user_state.get(line_user_id)

def clear_state(line_user_id):
    user_state.pop(line_user_id, None)

def _get_connection():
    return pymysql.connect(**DB_CONFIG)

def ensure_user_record(line_user_id):
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO `User` (line_user_id) VALUES (%s)",
                (line_user_id,)
            )
        conn.commit()
    finally:
        conn.close()

def _get_user_pk(line_user_id):
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT LineUserId_id FROM `User` WHERE line_user_id=%s",
                (line_user_id,)
            )
            row = cursor.fetchone()
            return row['LineUserId_id'] if row else None
    finally:
        conn.close()

def _get_card_pk(card_id):
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT CardId_id FROM `Card` WHERE card_id=%s",
                (card_id,)
            )
            row = cursor.fetchone()
            return row['CardId_id'] if row else None
    finally:
        conn.close()

def get_all_cards():
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT card_id, bank_name, card_name FROM `Card`"
            )
            return cursor.fetchall()
    finally:
        conn.close()

def add_user_card(line_user_id, card_id):
    ensure_user_record(line_user_id)
    user_pk = _get_user_pk(line_user_id)
    card_pk = _get_card_pk(card_id)
    if not user_pk or not card_pk:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO `UserCard` (LineUserId_id, CardId_id) VALUES (%s, %s)",
                (user_pk, card_pk)
            )
        conn.commit()
        return True
    finally:
        conn.close()

def delete_user_card(line_user_id, card_id):
    user_pk = _get_user_pk(line_user_id)
    card_pk = _get_card_pk(card_id)
    if not user_pk or not card_pk:
        return False
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE uc FROM `UserCard` uc "
                "WHERE uc.LineUserId_id=%s AND uc.CardId_id=%s",
                (user_pk, card_pk)
            )
        conn.commit()
        return True
    finally:
        conn.close()

def get_user_cards(line_user_id):
    user_pk = _get_user_pk(line_user_id)
    if not user_pk:
        return []
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT c.card_name FROM `UserCard` uc "
                "JOIN `Card` c ON uc.CardId_id=c.CardId_id "
                "WHERE uc.LineUserId_id=%s",
                (user_pk,)
            )
            rows = cursor.fetchall()
            return [r['card_name'] for r in rows]
    finally:
        conn.close()
