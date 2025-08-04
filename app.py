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
from conversation import (
    get_state,
    set_state,
    clear_state,
    get_all_cards,
    get_user_cards,
    add_user_card,
    delete_user_card
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
'''
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
'''

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        app.logger.error("簽名驗證失敗，請檢查您的 Channel Secret。")
        abort(400)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_text_message(event)

    return 'OK'


def handle_text_message(event: MessageEvent):
    """處理所有文字訊息的總入口"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_token = event.reply_token

    app.logger.info(f"使用者 {user_id} 傳入訊息: {text}")

    try:
        # 獲取使用者當前的對話狀態
        state = get_state(user_id)

        # --- 階段一：處理卡夾管理的多步驟對話 ---
        if state:
            action = state.get('action')
            
            # 如果是等待輸入卡片ID的步驟
            if state.get('step') == 'input_card':
                card_id_input = text
                reply_text = ""
                success = False
                
                try:
                    card_id = int(card_id_input)
                    if action == "add":
                        success = add_user_card(user_id, card_id)
                        reply_text = "✅ 新增成功！" if success else "新增失敗，可能您已擁有此卡，或卡片ID不正確。"
                    elif action == "delete":
                        success = delete_user_card(user_id, card_id)
                        reply_text = "✅ 刪除成功！" if success else "刪除失敗，請確認您是否擁有此卡，或卡片ID不正確。"
                except ValueError:
                    reply_text = "⚠️ 輸入格式錯誤，請輸入數字卡片ID。"
                except Exception as e:
                    app.logger.error(f"卡片操作時發生錯誤: {e}")
                    reply_text = "處理您的請求時發生錯誤，請稍後再試。"
                
                clear_state(user_id) # 無論成功失敗，都清除狀態
                reply(reply_token, [TextMessage(text=reply_text)])
                return

        # --- 階段二：處理單次指令 (卡夾管理 & 信用卡推薦) ---
        
        # 指令：我的卡夾
        if text == "我的卡夾":
            cards = get_user_cards(user_id)
            if cards:
                reply_text = "您的卡夾目前有：\n" + "\n".join(cards)
            else:
                reply_text = "您的卡夾目前沒有任何卡片。\n您可以使用「我要新增卡片」來加入您的信用卡喔！"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # 指令：我要新增卡片
        if text == "我要新增卡片":
            set_state(user_id, "add", "input_card")
            cards = get_all_cards()
            if not cards:
                reply(reply_token, [TextMessage(text="抱歉，目前系統中沒有可新增的卡片。")])
                clear_state(user_id)
                return
            
            menu = "請從下方列表輸入您要新增的卡片ID：\n"
            menu += "\n".join([f"▶️ {c['card_id']}：{c['bank_name']} - {c['card_name']}" for c in cards])
            reply(reply_token, [TextMessage(text=menu)])
            return

        # 指令：我要刪除卡片
        if text == "我要刪除卡片":
            my_cards = get_user_cards(user_id)
            if not my_cards:
                reply(reply_token, [TextMessage(text="您的卡夾是空的，沒有可以刪除的卡片。")])
                return

            set_state(user_id, "delete", "input_card")
            menu = "請輸入您要刪除的卡片ID (您的卡片列表如下)：\n"
            # 為了讓使用者知道ID，我們需要重新查詢一次
            all_cards_map = {f"{c['bank_name']} - {c['card_name']}": c['card_id'] for c in get_all_cards()}
            
            user_card_details = []
            for card_full_name in my_cards:
                # 假設 get_user_cards 回傳的是 '銀行 - 卡名' 格式
                card_name_part = card_full_name.split(' - ')[1] if ' - ' in card_full_name else card_full_name
                
                # 找到對應的ID
                found_id = None
                for c in get_all_cards():
                    if c['card_name'] == card_name_part:
                        found_id = c['card_id']
                        break
                if found_id:
                     user_card_details.append(f"▶️ {found_id}：{card_full_name}")

            if not user_card_details:
                 menu += "無法獲取您的卡片詳細資訊。"
            else:
                 menu += "\n".join(user_card_details)

            reply(reply_token, [TextMessage(text=menu)])
            return

        # 指令：信用卡推薦 (查詢個人卡片)
        if text == "我想去買東西！但我不知道我的卡當中哪個合適！":
            reply_text = "好的，您已進入【查詢個人卡片】模式。請告訴我您想去哪裡消費？（可連續查詢不同店家）"
            set_state(user_id, "mycard_query", "querying")
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # 指令：信用卡推薦 (推薦新卡片)
        if text == "我想去買東西，但我不知道哪些信用卡最合適！":
            reply_text = "好的，您已進入【推薦新卡片】模式。請告訴我您想去哪裡消費？我會根據您給我的商家推薦適合的信用卡。"
            set_state(user_id, "recommend_query", "querying")
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # 指令：關於我們
        if text == "關於我們":
            reply_text = "我們是一個信用卡推薦機器人，旨在幫助您找到最適合您的信用卡！"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # --- 階段三：處理信用卡推薦的連續查詢 ---
        if state and state.get('step') == 'querying':
            action = state.get('action')
            if action == "mycard_query":
                app.logger.info(f"使用者 {user_id} 處於 mycard_query 狀態，查詢: {text}")
                results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_mycard_logic(text))
                format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2)
            elif action == "recommend_query":
                app.logger.info(f"使用者 {user_id} 處於 recommend_query 狀態，查詢: {text}")
                results, extractedd, recommend_store1, recommend_store2 = asyncio.run(_async_result_logic(text))
                format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2)
            return

        # --- 階段四：預設回覆 ---
        fallback_text = "您好！請使用圖文選單來選擇服務：\n\n💳 **信用卡推薦**\n- 我想去買東西！但我不知道我的卡當中哪個合適！\n- 我想去買東西，但我不知道哪些信用卡最合適！\n\n🗂️ **個人卡夾管理**\n- 我的卡夾\n- 我要新增卡片\n- 我要刪除卡片"
        reply(reply_token, [TextMessage(text=fallback_text)])

    except ConnectionError as e:
        app.logger.error(f"❌ 資料庫連線錯誤：{e}")
        reply(reply_token, [TextMessage(text=f"❌ 資料庫連線錯誤，請稍後再試。")])
    except Exception as e:
        app.logger.error(f"❌ 處理訊息時發生錯誤：{e}", exc_info=True)
        reply(reply_token, [TextMessage(text=f"處理您的請求時發生錯誤，請稍後再試。")])


# =================================================================
# ==                 輔助函式 (Helper Functions)                   ==
# =================================================================

def format_and_reply_results(reply_token, results, extractedd, recommend_store1, recommend_store2):
    """將查詢結果格式化並發送"""
    reply_messages = []

    info_parts = []
    if extractedd and isinstance(extractedd, str) and extractedd.strip():
        info_parts.append(f"您感興趣的商店：{extractedd}")
    else:
        info_parts.append("無法抽取到明確商店。")

    recommended_stores_list = [s for s in [recommend_store1, recommend_store2] if s and isinstance(s, str) and s.strip()]
    if recommended_stores_list:
        info_parts.append(f"推薦的同類商店：{', '.join(recommended_stores_list)}")

    if info_parts:
        reply_messages.append(TextMessage(text="\n".join(info_parts)))

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

    reply(reply_token, reply_messages)

def reply(reply_token: str, messages: list):
    """v3 標準回覆訊息的輔助函式"""
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        )
    )

# --- 信用卡推薦的核心非同步邏輯 ---
async def _async_mycard_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    extractedd = recs.get('extracted_stores') 
    recommend_store1 = recs.get('recommend_store1')
    recommend_store2 = recs.get('recommend_store2')
    conn = create_db_connection()
    if conn is None: raise ConnectionError('❌ 無法連接到資料庫。')
    df = fetch_tasks_from_db(conn, extractedd, recommend_store1, recommend_store2)
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊。")
        return [], extractedd, recommend_store1, recommend_store2
    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_scoremc(added_df) 
    results = result_df.to_dict(orient='records')
    return results, extractedd, recommend_store1, recommend_store2

async def _async_result_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    extractedd = recs.get('extracted_stores')
    recommend_store1 = recs.get('recommend_store1')
    recommend_store2 = recs.get('recommend_store2')
    conn = create_db_connection()
    if conn is None: raise ConnectionError('❌ 無法連接到資料庫。')
    df = fetch_tasks_from_db(conn, extractedd, recommend_store1, recommend_store2)
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊。")
        return [], extractedd, recommend_store1, recommend_store2
    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_score(added_df) 
    results = result_df.to_dict(orient='records')
    return results, extractedd, recommend_store1, recommend_store2

if __name__ == '__main__':
    # 執行時請確保 _async_mycard_logic 和 _async_result_logic 函式已定義或引入
    # from your_logic_file import _async_mycard_logic, _async_result_logic
    app.run(debug=True, port=5001)