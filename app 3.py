# app.py
import os
from flask import Flask, request, abort # 導入 abort
from dotenv import load_dotenv
from recommender import load_vectors_into_global_cache, find_best_matching_store_vector, recommend_stores_by_sentence
from cal_total_score import cal_total_score, cal_total_scoremc # 確保這個有引入
from db import create_connection as create_db_connection
from make_df_from_sql import fetch_tasks_from_db, add_ai_scores_async,fetch_tasks_for_user_with_join


load_dotenv()
app = Flask(__name__)
import asyncio
from flask import Flask, request, abort
from flex_message import create_card_carousel, create_bank_grouped_carousel
from collections import defaultdict

# --- v3 的主要模組 ---
# 移除了所有來自 linebot.models (v2) 的引入
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from conversation import (
    get_state,
    set_state,
    clear_state,
    get_all_cards,
    get_user_cards,
    add_user_card,
    delete_user_card,
    check_or_create_user
)

# --- Line Bot 相關設定 (純 v3 版本) ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數尚未設定！")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
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
        user_id = event.source.user_id
        if not check_or_create_user(user_id):
            app.logger.error(f"無法為使用者 {user_id} 建立資料庫紀錄，停止處理事件。")
            continue

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_text_message(event)

    return 'OK'

def get_and_group_cards_from_db():
    # 這個函式將取代原本硬編碼的邏輯
    # 稍後我們會來實現它
    conn = create_db_connection()
    if not conn:
        app.logger.error("無法連接到資料庫以獲取卡片列表。")
        return None
    # 假設您在 make_df_from_sql.py 中新增了一個函式來獲取卡片
    from make_df_from_sql import fetch_all_cards 
    all_cards = fetch_all_cards(conn) # 這會回傳一個像 [{'card_id': '822001', 'bank_name': '中國信託', 'card_name': '中油聯名卡'}, ...] 的列表
    conn.close()

    if not all_cards:
        return None

    grouped_cards = defaultdict(list)
    for card in all_cards:
        grouped_cards[card['bank_name']].append({
            "id": card['card_id'],
            "name": card['card_name']
        })
    return grouped_cards

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
        if text == "我的卡夾":
            clear_state(user_id)
            cards = get_user_cards(user_id)
            reply_text = "您的卡夾目前有：\n" + "\n".join(cards) if cards else "您的卡夾目前是空的喔！"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        if text == "我要新增卡片":
            # 【關鍵】我們重新啟用 set_state，因為後續的處理流程需要它
            set_state(user_id, "add", "input_card") 
            
           # 從資料庫動態獲取卡片資料
            grouped_cards = get_and_group_cards_from_db()
            
            if not grouped_cards:
                reply(reply_token, [TextMessage(text="抱歉，目前系統中沒有可新增的卡片。")])
                clear_state(user_id) # 如果沒有卡片，也要清除狀態
                return

            add_card_message = create_bank_grouped_carousel(grouped_cards)
            reply(reply_token, [add_card_message])
            return


        if text == "我要刪除卡片":
            my_card_names = get_user_cards(user_id)
            if not my_card_names:
                reply(reply_token, [TextMessage(text="您的卡夾是空的，沒有可以刪除的卡片。")])
                return

            set_state(user_id, "delete", "input_card")
            menu = "請輸入您要刪除的卡片ID (您的卡片列表如下)：\n\n"
            
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

        if text == "我想去買東西！但我不知道我的卡當中哪個合適！":
            set_state(user_id, "mycard_query", "querying")
            reply_text = "好的，您已進入【個人卡片查詢】模式。\n請告訴我您在哪裡消費？(例如：我在全聯買東西)\n\n"
            reply(reply_token, [TextMessage(text=reply_text)])
            return

        if text == "我想去買東西，但我不知道哪些信用卡最合適！":
            set_state(user_id, "recommend_query", "querying")
            reply_text = "好的，您已進入【推薦新卡片】模式。\n請告訴我您想在哪使用信用卡？（例如：我想搭華航去日本）\n\n"
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
        if state:
            if state.get('step') == 'input_card':
                action = state.get('action')
                card_id_input = text  # text 此時會是 "013003" 這種卡片ID
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
                
                clear_state(user_id) 
                reply(reply_token, [TextMessage(text=reply_text)])
                return

            if state.get('step') == 'querying':
                action = state.get('action')
                if action == "mycard_query":
                    app.logger.info(f"使用者 {user_id} 處於 mycard_query 狀態，查詢: {text}")
                    results, extractedd = asyncio.run(_async_mycard_logic(text, user_id))
                    format_and_reply_results(reply_token, results, extractedd)
                elif action == "recommend_query":
                    app.logger.info(f"使用者 {user_id} 處於 recommend_query 狀態，查詢: {text}")
                    results, extractedd = asyncio.run(_async_result_logic(text))
                    format_and_reply_results(reply_token, results, extractedd)
                return
            
        # --- 階段三：預設回覆 ---
        fallback_text = "您好！請使用圖文選單來選擇服務：\n\n💳 **信用卡推薦**\n- 我想去買東西！但我不知道我的卡當中哪個合適！\n- 我想去買東西，但我不知道哪些信用卡最合適！\n\n🗂️ **個人卡夾管理**\n- 我的卡夾\n- 我要新增卡片\n- 我要刪除卡片"
        reply(reply_token, [TextMessage(text=fallback_text)])

    except Exception as e:
        app.logger.error(f"❌ 處理訊息時發生錯誤：{e}", exc_info=True)
        clear_state(user_id)
        reply(reply_token, [TextMessage(text=f"處理您的請求時發生錯誤，系統已重置您的對話狀態，請再試一次。")])

# =================================================================
# ==                 輔助函式 (Helper Functions)                   ==
# =================================================================


# 【修改點 3】: 修改此函式以呼叫新的 create_card_carousel
def format_and_reply_results(reply_token, results, extractedd):
    """將查詢結果格式化並發送 (新版：使用 Flex Message)"""
    reply_messages = []

    # 1. 建立開頭的文字說明
    info_parts = []
    if extractedd and isinstance(extractedd, str) and extractedd.strip():
        info_parts.append(f"根據您的需求，我們分析出相關商店為：「{extractedd}」。")
    else:
        info_parts.append("我們將為您進行廣泛的信用卡推薦。")
    
    # 必定發送開頭的文字訊息
    reply_messages.append(TextMessage(text="\n".join(info_parts)))

    # 2. 檢查是否有結果，並產生對應的訊息 (Flex 或 Text)
    if results:
        card_carousel_message = create_card_carousel(results)
        if card_carousel_message:
            reply_messages.append(card_carousel_message)
        else:
            # 備用方案，萬一 Flex Message 建立失敗
            reply_messages.append(TextMessage(text="抱歉，無法產生卡片推薦樣式，請稍後再試。"))
    else:
        # 如果沒有任何結果，發送提示文字
        reply_messages.append(TextMessage(text="抱歉，根據您的輸入，目前找不到合適的卡片推薦。請嘗試其他商店或關鍵字。"))

    # 3. 一次性回覆所有訊息
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
# (這部分的邏輯保持不變)
async def _async_mycard_logic(sentence: str, user_id: str):
    """
    【全新混合驗證策略 - GPT 優先版】
    1. 嘗試 GPT 提取並立即驗證 DB。
    2. 如果 DB 無結果，才嘗試向量搜尋並再次驗證 DB。
    """
    # 導入 pandas 以便創建空的 DataFrame
    import pandas as pd
    
    df = pd.DataFrame()
    final_extractedd = None

    # --- 1. 主要方案：GPT 提取 & 首次驗證 ---
    app.logger.info("--- Phase 1: 執行 GPT 提取 ---")
    recs_gpt = recommend_stores_by_sentence(sentence)
    extracted_gpt = recs_gpt.get('extracted_stores')
    
    if extracted_gpt:
        app.logger.info(f"GPT 提取到候選店家: {extracted_gpt}")
        conn = create_db_connection()
        # 立即驗證資料庫中是否有此店家的優惠
        df = fetch_tasks_for_user_with_join(conn, user_id, extracted_gpt)
        conn.close()
        
        if not df.empty:
            # 如果成功找到優惠，確定使用這個店家名稱
            final_extractedd = extracted_gpt
            app.logger.info(f"✅ 成功！GPT 提取的店家 '{final_extractedd}' 在DB中找到 {len(df)} 筆優惠。")
        else:
            app.logger.warning(f"GPT 提取的店家 '{extracted_gpt}' 在DB中無對應優惠，準備嘗試向量備用方案。")
    
    # --- 2. 備用方案：向量搜尋 & 二次驗證 ---
    # 只有在主要方案的資料庫驗證失敗後 (df 依然是空的)，才執行這部分
    if df.empty:
        app.logger.info("--- Phase 2: 執行向量搜尋備用方案 ---")
        recs_vec = find_best_matching_store_vector(sentence)
        extracted_vec = recs_vec.get('extracted_stores')

        if extracted_vec and extracted_vec != extracted_gpt: # 避免重複查詢
            app.logger.info(f"向量搜尋找到候選店家: {extracted_vec}")
            conn = create_db_connection()
            # 再次驗證資料庫
            df = fetch_tasks_for_user_with_join(conn, user_id, extracted_vec)
            conn.close()
            final_extractedd = extracted_vec # 無論有無結果，都以最後一次嘗試的店家為準
            if not df.empty:
                 app.logger.info(f"✅ 成功！向量搜尋的店家 '{final_extractedd}' 在DB中找到 {len(df)} 筆優惠。")
            else:
                 app.logger.warning(f"向量搜尋的店家 '{final_extractedd}' 在DB中也無對應優惠。")
        else:
            # 如果向量也沒東西，或跟上次一樣，就沿用第一次的結果
            final_extractedd = extracted_gpt

    # --- 3. 最終處理 ---
    # 如果 df 最終仍然是空的，直接回傳
    if df.empty:
        return [], final_extractedd

    # 如果 df 有資料，才進行後續的 AI 評分和計算
    added_df = await add_ai_scores_async(df)
    result_df = cal_total_scoremc(added_df)
    results = result_df.to_dict(orient='records')
    return results, final_extractedd



async def _async_result_logic(sentence):
    """
    【全新混合驗證策略 - GPT 優先版】 - 推薦新卡版
    """
    # 導入 pandas 以便創建空的 DataFrame
    import pandas as pd

    df = pd.DataFrame()
    final_extractedd = None

    # --- 1. 主要方案：GPT 提取 & 首次驗證 ---
    app.logger.info("--- Phase 1: 執行 GPT 提取 ---")
    recs_gpt = recommend_stores_by_sentence(sentence)
    extracted_gpt = recs_gpt.get('extracted_stores')
    
    if extracted_gpt:
        app.logger.info(f"GPT 提取到候選店家: {extracted_gpt}")
        conn = create_db_connection()
        # 立即驗證資料庫中是否有此店家的優惠
        df = fetch_tasks_from_db(conn, extracted_gpt)
        conn.close()
        
        if not df.empty:
            final_extractedd = extracted_gpt
            app.logger.info(f"✅ 成功！GPT 提取的店家 '{final_extractedd}' 在DB中找到 {len(df)} 筆優惠。")
        else:
            app.logger.warning(f"GPT 提取的店家 '{extracted_gpt}' 在DB中無對應優惠，準備嘗試向量備用方案。")

    # --- 2. 備用方案：向量搜尋 & 二次驗證 ---
    if df.empty:
        app.logger.info("--- Phase 2: 執行向量搜尋備用方案 ---")
        recs_vec = find_best_matching_store_vector(sentence)
        extracted_vec = recs_vec.get('extracted_stores')

        if extracted_vec and extracted_vec != extracted_gpt:
            app.logger.info(f"向量搜尋找到候選店家: {extracted_vec}")
            conn = create_db_connection()
            df = fetch_tasks_from_db(conn, extracted_vec)
            conn.close()
            final_extractedd = extracted_vec
            if not df.empty:
                 app.logger.info(f"✅ 成功！向量搜尋的店家 '{final_extractedd}' 在DB中找到 {len(df)} 筆優惠。")
            else:
                 app.logger.warning(f"向量搜尋的店家 '{final_extractedd}' 在DB中也無對應優惠。")
        else:
            final_extractedd = extracted_gpt

    # --- 3. 最終處理 ---
    if df.empty:
        return [], final_extractedd

    added_df = await add_ai_scores_async(df)
    result_df = cal_total_score(added_df)
    results = result_df.to_dict(orient='records')
    return results, final_extractedd


print("--- 應用程式啟動：開始預先載入店家向量 ---")
try:
    preload_conn = create_db_connection()
    if preload_conn:
        # 呼叫新的函式，它會直接填充 recommender.py 中的全域快取
        load_vectors_into_global_cache(preload_conn)
        preload_conn.close()
    else:
        print("!!! 警告：無法連接到資料庫，跳過向量預載入 !!!")
except Exception as e:
    print(f"!!! 錯誤：預載入向量時發生問題: {e} !!!")

if __name__ == '__main__':
    # 為了讓 Flask 在開發模式下能正常執行，需要設定 asyncio 的事件循環策略 (僅限 Windows)
    # 在 macOS 或 Linux 上通常不需要這行
    # import platform
    # if platform.system() == "Windows":
    #    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True)