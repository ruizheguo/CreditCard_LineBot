# rich_menu_config.py

from linebot.v3.messaging import (
    RichMenuRequest,
    RichMenuSize,
    RichMenuArea,
    RichMenuBounds,
    MessageAction,
)

def create_rich_menu_config():
    """
    建立 Line Bot 圖文選單的 Python 配置物件。
    使用 Line Bot SDK V3 版本。
    """
    rich_menu_config = RichMenuRequest(
        size=RichMenuSize(width=2500, height=1686),
        selected=True,
        name="選單",
        chat_bar_text="選取服務內容",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=848, y=18, width=806, height=817),
                action=MessageAction(text='我想去買東西，但我不知道哪些信用卡最合適！')
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=1670, y=20, width=798, height=796),
                action=MessageAction(text='關於我們') # 點擊後發送 "推薦新卡片" 這個文字訊息
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=10, y=7, width=823, height=833),
                action=MessageAction(text='我想去買東西！但我不知道我的卡當中哪個合適！') # 點擊後發送 "我的卡片查詢" 這個文字訊息
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=17, y=849, width=814, height=806),
                action=MessageAction(text='我的卡夾')
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=852, y=844, width=807, height=810),
                action=MessageAction(text='我要刪除卡片')
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=1678, y=828, width=797, height=834),
                action=MessageAction(text='我要新增卡片'),
            )
        ]
    )
    return rich_menu_config