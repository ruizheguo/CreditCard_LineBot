# app.py
import os
from flask import Flask, render_template, request, abort # 導入 abort
from dotenv import load_dotenv
from recommender import recommend_stores_by_sentence
from cal_total_score import cal_total_score, cal_total_scoremc # 確保這個有引入
from db import create_connection as create_db_connection
from make_df_from_sql import fetch_tasks_from_db, add_ai_scores_async
import asyncio

load_dotenv()

app = Flask(__name__)
#-----------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

async def _async_mycard_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    # extractedd 現在預期是字串，或在找不到時為空列表/None
    extractedd = recs.get('extracted_stores') 
    recommend_store1 = recs.get('recommend_store1')
    recommend_store2 = recs.get('recommend_store2')

    conn = create_db_connection()
    if conn is None:
        raise ConnectionError('❌ 無法連接到資料庫。')

    # fetch_tasks_from_db 的參數 extracted_stores 接收到字串，這在 SQL 的 LIKE 查詢中是正常的
    df = fetch_tasks_from_db(conn, extractedd, recommend_store1, recommend_store2)
    
    # --- 關鍵修正 (1): 檢查 DataFrame 是否為空，這是防止 KeyError 的最重要步驟 ---
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊，將返回空結果。")
        # 即使 df 為空，依然將 OpenAI 提取的資訊回傳給前端顯示
        return [], extractedd, recommend_store1, recommend_store2

    # --- 關鍵修正 (2): 修改篩選邏輯以符合 extractedd 是字串的前提 ---
    # 如果 extractedd 是一個非空字串，就用它來過濾 DataFrame
    if isinstance(extractedd, str) and extractedd:
        # 使用 str.contains 來篩選 store 欄位
        df = df[df['store'].str.contains(extractedd, na=False)]
    
    # 如果經過篩選後 df 變空了，也直接返回
    if df.empty:
        app.logger.warning(f"根據使用者指定商店 '{extractedd}' 篩選後，無任何相符卡片資訊。")
        return [], extractedd, recommend_store1, recommend_store2

    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_scoremc(added_df) 
    results = result_df.to_dict(orient='records')
    
    return results, extractedd, recommend_store1, recommend_store2

@app.route('/mycard', methods=['POST'])
def mycard():
    sentence = request.form.get('sentence', '').strip()
    try:
        # 在 Flask 同步路由中執行非同步邏輯
        results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_mycard_logic(sentence))
        return render_template('mycard.html', results=results, extracted=extractedd,recommend_store1=recommend_store1, recommend_store2=recommend_store2)
    except ConnectionError as e: # 捕獲自定義的連線錯誤
        return render_template('mycard.html', error=str(e))
    except Exception as e:
        app.logger.error(f"mycard 路由處理資料時發生錯誤：{e}")
        return render_template('mycard.html', error=f'❌ 處理資料時發生錯誤：{e}')

    # 3. 呼叫 make_df_from_sql.py 的處理邏輯
#----------------------------------------------

# app.py

async def _async_result_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    # extractedd 現在預期是字串，或在找不到時為空列表/None
    extractedd = recs.get('extracted_stores')
    recommend_store1 = recs.get('recommend_store1')
    recommend_store2 = recs.get('recommend_store2')

    conn = create_db_connection()
    if conn is None:
        raise ConnectionError('❌ 無法連接到資料庫。')

    df = fetch_tasks_from_db(conn, extractedd, recommend_store1, recommend_store2)
    
    # --- 關鍵修正 (1): 檢查 DataFrame 是否為空，這是防止 KeyError 的最重要步驟 ---
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊，將返回空結果。")
        return [], extractedd, recommend_store1, recommend_store2

    # --- 關鍵修正 (2): 修改篩選邏輯以符合 extractedd 是字串的前提 ---
    if isinstance(extractedd, str) and extractedd:
        df = df[df['store'].str.contains(extractedd, na=False)]

    # 如果經過篩選後 df 變空了，也直接返回
    if df.empty:
        app.logger.warning(f"根據使用者指定商店 '{extractedd}' 篩選後，無任何相符卡片資訊。")
        return [], extractedd, recommend_store1, recommend_store2

    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_score(added_df) 
    results = result_df.to_dict(orient='records')
    
    return results, extractedd, recommend_store1, recommend_store2

@app.route('/result', methods=['POST'])
def result():
    sentence = request.form.get('sentence', '').strip()
    try:
        # 在 Flask 同步路由中執行非同步邏輯
        results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_result_logic(sentence))
        return render_template('result.html', results=results, extracted=extractedd,recommend_store1=recommend_store1, recommend_store2=recommend_store2)
    except ConnectionError as e: # 捕獲自定義的連線錯誤
        return render_template('result.html', error=str(e))
    except Exception as e:
        app.logger.error(f"result 路由處理資料時發生錯誤：{e}")
        return render_template('result.html', error=f'❌ 處理資料時發生錯誤：{e}')
#----網頁版結束----#

import os
import asyncio
from flask import Flask, request, abort

# --- v3 的主要模組 ---
# 移除了所有來自 linebot.models (v2) 的引入
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,  # v3 中用來回覆訊息的標準請求物件
    TextMessage       # v3 的文字訊息物件
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent  # v3 中代表文字訊息內容的類別
)

# 假設您的 Flask app 物件叫做 app，以及其他商業邏輯函式已定義
# from some_logic_file import _async_mycard_logic, _async_result_logic
app = Flask(__name__)


# --- Line Bot 相關設定 (純 v3 版本) ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數尚未設定！")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
# v3 使用 WebhookParser 來解析請求，取代了 v2 的 WebhookHandler
parser = WebhookParser(LINE_CHANNEL_SECRET)


# --- Line Bot Webhook Callback Endpoint (純 v3 寫法) ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        # parser.parse 會解析請求並回傳一個事件(event)的列表
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        app.logger.error("簽名驗證失敗，請檢查您的 Channel Secret。")
        abort(400)

    # v3 的標準做法是迴圈處理所有事件
    for event in events:
        # 只處理訊息事件，且內容為文字
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_text_message(event)

    return 'OK'

# 用於儲存使用者狀態的字典
user_states = {} # ⚠️ 警告：這只是一個簡單的範例，應用程式重啟後狀態會丟失。

# 將原本的 handle_message 邏輯獨立成一個函式
def handle_text_message(event: MessageEvent):
    """處理文字訊息事件的函式"""
    user_input = event.message.text.strip()
    user_id = event.source.user_id
    reply_token = event.reply_token

    app.logger.info(f"使用者 {user_id} 傳入訊息: {user_input}")

    try:
        # --- 邏輯順序調整：優先判斷是否為「功能選擇」指令 ---

        # 功能一：查詢我的卡片
        if user_input == "我想去買東西！但我不知道我的卡當中哪個合適！":
            reply_text = "好的，您已進入【查詢個人卡片】模式。請告訴我您想去哪裡消費？（可連續查詢不同店家）"
            user_states[user_id] = "mycard_query"  # 設定狀態
            reply(reply_token, [TextMessage(text=reply_text)])
            return # 設定完狀態後，直接結束本次函式，等待使用者輸入店家

        # 功能二：推薦新卡片
        if user_input == "我想去買東西，但我不知道哪些信用卡最合適！":
            reply_text = "好的，您已進入【推薦新卡片】模式。請告訴我您想去哪裡消費？我會根據你給我的商家推薦你適合的信用卡"
            user_states[user_id] = "recommend_query" # 設定狀態
            reply(reply_token, [TextMessage(text=reply_text)])
            return # 設定完狀態後，直接結束本次函式，等待使用者輸入店家

        # 其他功能：關於我們 (這是一個無狀態的功能)
        if user_input == "關於我們":
            reply_text = "我們是一個信用卡推薦機器人，旨在幫助您找到最適合您的信用卡！"
            reply(reply_token, [TextMessage(text=reply_text)])
            return # 執行完畢後直接結束

        # --- 如果不是功能選擇指令，才檢查當前狀態並執行查詢 ---
        current_state = user_states.get(user_id)
        
        # 如果使用者處於「查詢個人卡片」模式
        if current_state == "mycard_query":
            app.logger.info(f"使用者 {user_id} 處於 mycard_query 狀態，查詢: {user_input}")
            results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_mycard_logic(user_input))
            # 關鍵：我們不再刪除狀態！使用者可以繼續查詢
            format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2)
        
        # 如果使用者處於「推薦新卡片」模式
        elif current_state == "recommend_query":
            app.logger.info(f"使用者 {user_id} 處於 recommend_query 狀態，查詢: {user_input}")
            results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_result_logic(user_input))
            # 關鍵：我們不再刪除狀態！使用者可以繼續查詢
            format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2)
        
        # 如果使用者沒有任何狀態，且輸入的不是功能指令
        else:
            app.logger.info(f"使用者 {user_id} 未設定狀態，提供預設回覆。")
            reply_text = "您好！請使用下方的圖文選單來啟動服務，或直接輸入您想查詢的商店/消費類型，我會為您推薦信用卡喔！"
            reply(reply_token, [TextMessage(text=reply_text)])

    except ConnectionError as e:
        app.logger.error(f"❌ 資料庫連線錯誤：{e}")
        reply(reply_token, [TextMessage(text=f"❌ 資料庫連線錯誤，請稍後再試。")])
    except Exception as e:
        app.logger.error(f"❌ 處理訊息時發生錯誤：{e}", exc_info=True)
        reply(reply_token, [TextMessage(text=f"處理您的請求時發生錯誤，請稍後再試。")])
        
        # --- 格式化查詢結果 ---
        format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2)

    except ConnectionError as e:
        app.logger.error(f"❌ 資料庫連線錯誤：{e}")
        reply(reply_token, [TextMessage(text=f"❌ 資料庫連線錯誤，請稍後再試。")])
    except Exception as e:
        app.logger.error(f"❌ 處理訊息時發生錯誤：{e}", exc_info=True)
        reply(reply_token, [TextMessage(text=f"處理您的請求時發生錯誤，請稍後再試。")])


def format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2):
    """將查詢結果格式化並發送"""
    reply_messages = []

    # 組合第一則訊息：基本資訊
    info_parts = []
    if extractedd:
        # 確保 extractedd 是可迭代的字串列表
        stores = extractedd if isinstance(extractedd, list) else [str(extractedd)]
        info_parts.append(f"您感興趣的商店：{', '.join(stores)}")
    else:
        info_parts.append("無法抽取到明確商店。")

    recommended_stores_list = [s for s in [recommend_store1, recommend_store2] if s]
    if recommended_stores_list:
        info_parts.append(f"推薦的同類商店：{', '.join(recommended_stores_list)}")

    reply_messages.append(TextMessage(text="\n".join(info_parts)))

    # 組合第二則訊息：卡片推薦
    if results:
        card_recommendations = "✨ 最佳信用卡推薦任務：\n"
        for r in results:
            card_recommendations += (
                f"💳 卡片：{r.get('card_name', 'N/A')}\n"
                f"🏪 商店：{r.get('store', 'N/A')}\n"
                f"💰 總回饋：{r.get('總回饋', 'N/A')}\n"
                f"📝 任務說明：{r.get('task', 'N/A')}\n"
                f"📊 AI評分總分：{r.get('total_score', 'N/A')}\n"
                f"--------------------\n"
            )
        reply_messages.append(TextMessage(text=card_recommendations.strip()))
    else:
        reply_messages.append(TextMessage(text="抱歉，根據您的輸入，目前找不到合適的卡片推薦。"))

    # 一次性回覆所有訊息
    reply(reply_token, reply_messages)

def reply(reply_token: str, messages: list):
    """v3 標準回覆訊息的輔助函式"""
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

if __name__ == '__main__':
    # 執行時請確保 _async_mycard_logic 和 _async_result_logic 函式已定義或引入
    # from your_logic_file import _async_mycard_logic, _async_result_logic
    app.run(debug=True, port=5001)