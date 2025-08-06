# app.py
import os
from flask import Flask, render_template, request, abort # 導入 abort
from dotenv import load_dotenv
from recommender import recommend_stores_by_sentence
from cal_total_score import cal_total_score, cal_total_scoremc # 確保這個有引入
from db import create_connection as create_db_connection
from make_df_from_sql import fetch_tasks_from_db, add_ai_scores_async,fetch_tasks_for_user_with_join
import asyncio



load_dotenv()

app = Flask(__name__)
#-----------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

async def _async_mycard_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    # extracted 現在預期是字串，或在找不到時為空列表/None
    extracted = recs.get('extracted_stores') 
    conn = create_db_connection()
    if conn is None:
        raise ConnectionError('❌ 無法連接到資料庫。')

    # fetch_tasks_from_db 的參數 extracted_stores 接收到字串，這在 SQL 的 LIKE 查詢中是正常的
    df = fetch_tasks_from_db(conn, extracted)
    
    # --- 關鍵修正 (1): 檢查 DataFrame 是否為空，這是防止 KeyError 的最重要步驟 ---
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊，將返回空結果。")
        # 即使 df 為空，依然將 OpenAI 提取的資訊回傳給前端顯示
        return [], extracted
    # --- 關鍵修正 (2): 修改篩選邏輯以符合 extracted 是字串的前提 ---
    # 如果 extracted 是一個非空字串，就用它來過濾 DataFrame
    if isinstance(extracted, str) and extracted:
        # 使用 str.contains 來篩選 store 欄位
        df = df[df['store'].str.contains(extracted, na=False)]
    
    # 如果經過篩選後 df 變空了，也直接返回
    if df.empty:
        app.logger.warning(f"根據使用者指定商店 '{extracted}' 篩選後，無任何相符卡片資訊。")
        return [], extracted
    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_scoremc(added_df) 
    results = result_df.to_dict(orient='records')
    
    return results, extracted

@app.route('/mycard', methods=['POST'])
def mycard():
    sentence = request.form.get('sentence', '').strip()
    try:
        # 在 Flask 同步路由中執行非同步邏輯
        results, extracted= asyncio.run(_async_mycard_logic(sentence))
        return render_template('mycard.html', results=results, extracted=extracted)
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
    # extracted 現在預期是字串，或在找不到時為空列表/None
    extracted = recs.get('extracted_stores')

    conn = create_db_connection()
    if conn is None:
        raise ConnectionError('❌ 無法連接到資料庫。')

    df = fetch_tasks_from_db(conn, extracted)
    
    # --- 關鍵修正 (1): 檢查 DataFrame 是否為空，這是防止 KeyError 的最重要步驟 ---
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊，將返回空結果。")
        return [], extracted

    # --- 關鍵修正 (2): 修改篩選邏輯以符合 extracted 是字串的前提 ---
    if isinstance(extracted, str) and extracted:
        df = df[df['store'].str.contains(extracted, na=False)]

    # 如果經過篩選後 df 變空了，也直接返回
    if df.empty:
        app.logger.warning(f"根據使用者指定商店 '{extracted}' 篩選後，無任何相符卡片資訊。")
        return [], extracted

    added_df = await add_ai_scores_async(df)
    _, result_df = cal_total_score(added_df) 
    results = result_df.to_dict(orient='records')
    
    return results, extracted

@app.route('/result', methods=['POST'])
def result():
    sentence = request.form.get('sentence', '').strip()
    try:
        # 在 Flask 同步路由中執行非同步邏輯
        results, extracted= asyncio.run(_async_result_logic(sentence))
        return render_template('result.html', results=results, extracted=extracted)
    except ConnectionError as e: # 捕獲自定義的連線錯誤
        return render_template('result.html', error=str(e))
    except Exception as e:
        app.logger.error(f"result 路由處理資料時發生錯誤：{e}")
        return render_template('result.html', error=f'❌ 處理資料時發生錯誤：{e}')
#----網頁版結束----#

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
    """
    處理所有文字訊息的總入口 (已整合「可中斷查詢」與「單次流程」邏輯)
    """
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_token = event.reply_token

    app.logger.info(f"使用者 {user_id} 傳入訊息: {text}")

    try:
        state = get_state(user_id)

        # --- 階段一：優先檢查是否為「觸發型指令」 ---
        # 這個區塊的順序至關重要。把所有能開啟一個新流程的指令放在最前面。
        # 這樣使用者無論處於何種狀態，都能透過點擊選單來啟動一個全新的功能。

        # 指令：我的卡夾 (單次性指令，執行完就結束)
        if text == "我的卡夾":
            clear_state(user_id) # 清除可能存在的舊狀態 (例如查詢中)
            cards = get_user_cards(user_id)
            reply_text = "您的卡夾目前有：\n" + "\n".join(cards) if cards else "您的卡夾目前是空的喔！"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # 指令：我要新增卡片 (開啟一個新的多步驟流程)
        if text == "我要新增卡片":
            set_state(user_id, "add", "input_card") # 設定新狀態，會覆蓋舊的
            cards = get_all_cards()
            if not cards:
                reply(reply_token, [TextMessage(text="抱歉，目前系統中沒有可新增的卡片。")])
                clear_state(user_id)
                return
            
            menu = "請從下方列表輸入您要新增的卡片ID：\n\n"
            menu += "\n".join([f"▶️ {c['card_id']}：{c['bank_name']} - {c['card_name']}" for c in cards])
            reply(reply_token, [TextMessage(text=menu)])
            return

        # 指令：我要刪除卡片 (開啟一個新的多步驟流程)
        if text == "我要刪除卡片":
            my_card_names = get_user_cards(user_id)
            if not my_card_names:
                reply(reply_token, [TextMessage(text="您的卡夾是空的，沒有可以刪除的卡片。")])
                return

            set_state(user_id, "delete", "input_card") # 設定新狀態，會覆蓋舊的
            menu = "請輸入您要刪除的卡片ID (您的卡片列表如下)：\n\n"
            
            # 建議未來優化: 在 conversation.py 新增一個函式直接回傳含ID的卡片資訊
            all_cards_info = {c['card_name']: c for c in get_all_cards()}
            user_card_details = []
            for name in my_card_names:
                card_name_part = name.split(' - ')[1] if ' - ' in name else name
                if card_name_part in all_cards_info:
                    card_info = all_cards_info[card_name_part]
                    user_card_details.append(f"▶️ {card_info['card_id']}：{name}")

            menu += "\n".join(user_card_details) if user_card_details else "無法獲取您的卡片詳細資訊。"
            reply(reply_token, [TextMessage(text=menu)])
            return

        # 指令：信用卡推薦 (查詢個人卡片) -> 開啟查詢模式
        if text == "我想去買東西！但我不知道我的卡當中哪個合適！":
            set_state(user_id, "mycard_query", "querying") # 設定新狀態
            reply_text = "好的，您已進入【查詢個人卡片】模式。\n請告訴我您想去哪裡消費？（可隨時點選單切換功能）"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # 指令：信用卡推薦 (推薦新卡片) -> 開啟查詢模式
        if text == "我想去買東西，但我不知道哪些信用卡最合適！":
            set_state(user_id, "recommend_query", "querying") # 設定新狀態
            reply_text = "好的，您已進入【推薦新卡片】模式。\n請告訴我您想去哪裡消費？（可隨時點選單切換功能）"
            reply(reply_token, [TextMessage(text=reply_text)])
            return
        
        if text == "關於我們":
            reply_text = (
        "✨ 卡哩嗨 功能介紹 ✨\n"
        "我們旨在解決您的信用卡選擇困難，讓每次消費都享受到最佳回饋！\n\n"
        "💳 核心功能\n"
        "我要購物 🛍️：\n"
        "聰明推薦！根據您消費的商店，我們會從您的卡片中，"
        "精選出最適合、回饋最佳的信用卡，讓您不漏掉任何優惠。\n\n"
        "我的卡夾 💼：\n"
        "輕鬆管理！在這裡您可以一覽所有已新增至系統的信用卡清單，所有資訊一目瞭然。\n\n"
        "推薦新卡 🌟：\n"
        "專屬推薦！為您發掘更適合特定商店，且您尚未擁有的潛力好卡，"
        "幫您省更多，聰明消費！\n\n"
        "🛠️ 卡片管理\n"
        "新增卡片 ➕：\n"
        "快速建檔！將您持有的信用卡輕鬆加入系統，立即開始智慧管理您的每一筆消費。\n\n"
        "刪除卡夾 🗑️：\n"
        "彈性調整！隨時移除您不再使用或想刪除的信用卡資訊，讓您的卡夾保持最新。\n"
        "(Ex：Line Pay卡是822005，那就在輸入匡裡輸入：822005）"
    )
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        # --- 階段二：如果不是指令，再根據「現有狀態」處理 ---
        # 只有當使用者的輸入不是上述任何一個指令時，才會進到這裡。
        if state:
            # 狀態：正在等待輸入卡片ID (新增/刪除的第二步)
            if state.get('step') == 'input_card':
                action = state.get('action')
                card_id_input = text
                reply_text = ""
                
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
                
                # 【關鍵】: 不論成功或失敗，完成此單次流程後就清除狀態。
                clear_state(user_id) 
                reply(reply_token, [TextMessage(text=reply_text)])
                return

            # 狀態：正在連續查詢信用卡
            if state.get('step') == 'querying':
                action = state.get('action')
                if action == "mycard_query":
                    app.logger.info(f"使用者 {user_id} 處於 mycard_query 狀態，查詢: {text}")
                    results, extracted = asyncio.run(_async_mycard_logic(text, user_id))
                    format_and_reply_results(reply_token, results, extracted)
                elif action == "recommend_query":
                    app.logger.info(f"使用者 {user_id} 處於 recommend_query 狀態，查詢: {text}")
                    results, extracted = asyncio.run(_async_result_logic(text))
                    format_and_reply_results(reply_token, results, extracted)
                return
            

        # --- 階段三：預設回覆 ---
        # 如果以上所有條件都不滿足，代表使用者輸入了未知的指令
        fallback_text = "您好！請使用圖文選單來選擇服務：\n\n💳 **信用卡推薦**\n- 我想去買東西！但我不知道我的卡當中哪個合適！\n- 我想去買東西，但我不知道哪些信用卡最合適！\n\n🗂️ **個人卡夾管理**\n- 我的卡夾\n- 我要新增卡片\n- 我要刪除卡片"
        reply(reply_token, [TextMessage(text=fallback_text)])

    except Exception as e:
        app.logger.error(f"❌ 處理訊息時發生錯誤：{e}", exc_info=True)
        # 清除狀態以避免使用者卡在錯誤流程中
        clear_state(user_id)
        reply(reply_token, [TextMessage(text=f"處理您的請求時發生錯誤，系統已重置您的對話狀態，請再試一次。")])



# =================================================================
# ==                 輔助函式 (Helper Functions)                   ==
# =================================================================

def format_and_reply_results(reply_token, results, extracted):
    """將查詢結果格式化並發送"""
    reply_messages = []

    info_parts = []
    if extracted and isinstance(extracted, str) and extracted.strip():
        info_parts.append(f"您可能感興趣的商店：{extracted}")
    else:
        info_parts.append("無法抽取到明確商店。")

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
        reply_messages.append(TextMessage(text="抱歉，根據您的輸入，目前找不到合適的卡片推薦。請嘗試其他商店或關鍵字。"))

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
async def _async_mycard_logic(sentence: str, user_id: str):
    """
    【JOIN 版本】根據使用者擁有的卡片進行推薦。
    """
    # 1. 透過 OpenAI 推薦相關商店
    recs = recommend_stores_by_sentence(sentence)
    extracted = recs.get('extracted_stores') 

    
    # 2. 連接資料庫並直接呼叫新的 JOIN 函式
    conn = create_db_connection()
    if conn is None: 
        raise ConnectionError('❌ 無法連接到資料庫。')
    
    # 直接呼叫新函式，把 user_id 傳入，讓資料庫完成所有篩選
    df = fetch_tasks_for_user_with_join(
        conn,
        user_id, # 傳入使用者的 Line ID
        extracted
        )
    # 如果 DataFrame 為空，表示在該使用者的卡片中找不到符合條件的優惠
    if df.empty:
        app.logger.warning(f"在使用者 {user_id} 的卡片中，查無任何相關商店資訊。")
        return [], extracted

    # 3. 進行 AI 評分與計算總分 (後續流程完全不變)
    added_df = await add_ai_scores_async(df)
    result_df = cal_total_scoremc(added_df) 
    results = result_df.to_dict(orient='records')
    
    return results, extracted

async def _async_result_logic(sentence):
    recs = recommend_stores_by_sentence(sentence)
    extracted = recs.get('extracted_stores')

    conn = create_db_connection()
    if conn is None: raise ConnectionError('❌ 無法連接到資料庫。')
    df = fetch_tasks_from_db(
        conn, 
        extracted
        )
    if df.empty:
        app.logger.warning("資料庫查無任何相關商店資訊。")
        return [], extracted
    added_df = await add_ai_scores_async(df)
    result_df = cal_total_score(added_df) 
    results = result_df.to_dict(orient='records')

    return results, extracted

if __name__ == '__main__':
    # 執行時請確保 _async_mycard_logic 和 _async_result_logic 函式已定義或引入
    # from your_logic_file import _async_mycard_logic, _async_result_logic
    app.run(debug=True, port=5001)