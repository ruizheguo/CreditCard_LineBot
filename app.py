from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage
from config import CHANNEL_SECRET, CHANNEL_ACCESS_TOKEN
from conversation import (
    set_state, get_state, clear_state,
    get_all_cards, add_user_card, delete_user_card, get_user_cards
)

app = Flask(__name__)

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add('message')
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)

    # No pending step: interpret commands
    if not state:
        if text == "我的卡夾":
            cards = get_user_cards(user_id)
            if cards:
                reply = "你的卡夾目前有：\n" + "\n".join(cards)
            else:
                reply = "你的卡夾目前沒有任何卡片。"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        if text == "我要新增卡片":
            set_state(user_id, "add")
            cards = get_all_cards()
            menu = "請輸入你要新增的卡片 (輸入卡片ID)：\n"
            menu += "\n".join([f"{c['card_id']}：{c['bank_name']} - {c['card_name']}" for c in cards])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=menu))
            return

        if text == "我要刪除卡片":
            set_state(user_id, "delete")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入您要刪除的卡片 (輸入卡片ID)："))
            return

        # 未识别命令
        fallback = "請輸入「我的卡夾」、「我要新增卡片」或「我要刪除卡片」。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=fallback))
        return

    # Pending input_card step
    if state.get('step') == 'input_card':
        card_id = text
        action = state.get('action')
        success = False

        if action == "add":
            success = add_user_card(user_id, card_id)
            reply = "新增成功！" if success else "新增失敗，請確認卡片ID是否正確。"
        elif action == "delete":
            success = delete_user_card(user_id, card_id)
            reply = "刪除成功！" if success else "刪除失敗，請確認卡片ID是否正確或是否新增過。"
        else:
            reply = "未知操作，請重新輸入。"

        clear_state(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    # Run on 0.0.0.0:5000
    app.run(host='0.0.0.0', port=5000)