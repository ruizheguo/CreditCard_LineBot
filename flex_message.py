# flex_messages.py

from linebot.v3.messaging import (
    FlexMessage,
    FlexBubble,
    FlexBox,
    FlexText,
    FlexSeparator,
    FlexCarousel,
    FlexButton,
    MessageAction
)

def create_card_carousel(results: list) -> FlexMessage:
    """
    根據查詢結果，建立一個包含最多3張信用卡推薦的 Flex Message 輪播卡片。
    """
    if not results:
        return None

    bubbles = []
    # 最多只取前三筆資料來製作卡片
    for r in results[:3]:
        # 對於每一筆結果，建立一個 Bubble (一張卡片)
        bubble = FlexBubble(
            # -- 卡片的標頭 (Header) --
            header=FlexBox(
                layout='vertical',
                contents=[
                    FlexText(
                        text='⭐ 最佳信用卡推薦',
                        weight='bold',
                        color='#FFD700', # 金色
                        size='sm'
                    ),
                    FlexText(
                        text=r.get('card_name', 'N/A'), #卡片的名稱
                        weight='bold',
                        size='xl',
                        margin='md',
                        wrap=True
                    )
                ]
            ),
            # -- 卡片的主體 (Body) --
            body=FlexBox(
                layout='vertical',
                spacing='md',
                contents=[
                    # 商店資訊
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text='商店:', color='#aaaaaa', size='sm', flex=2),
                            FlexText(text=r.get('store', 'N/A'), color='#666666', size='sm', flex=5, wrap=True)
                        ]
                    ),
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text='付款方式:', color='#aaaaaa', size='sm', flex=2),
                            FlexText(text=r.get('platform', 'N/A'), color='#666666', size='sm', flex=5, wrap=True)
                        ]
                    ),
                    # 總回饋
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text='總回饋:', color='#aaaaaa', size='sm', flex=2),
                            FlexText(text=str(r.get('總回饋', 'N/A')), color='#1DB446', size='xl', weight='bold', flex=5)
                        ]
                    ),
                    # AI 評分
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text='AI 評分:', color='#aaaaaa', size='sm', flex=2),
                            FlexText(text=f"{float(r.get('total_score', 0.0)):.2f}", color='#666666', size='sm', flex=5)
                        ]
                    ),
                    FlexSeparator(margin='lg'),
                    FlexBox(
                        layout='vertical',
                        contents=[
                            FlexText(text='任務說明', size='md', weight='bold'),
                            FlexText(
                                text=r.get('task') if r.get('task') not in [None, ""] else '無特定任務說明',
                                wrap=True,
                                color='#666666',
                                size='sm',
                                margin='md'
                            )
                        ]
                    ),
                    FlexBox(
                        layout='vertical',
                        contents=[                            
                            FlexText(text='備註', size='sm', weight='bold'),
                            FlexText(
                                text=r.get('note') if r.get('note') not in [None, ""] else '無特定備註',
                                wrap=True,
                                color='#666666',
                                size='sm',
                                margin='md'
                            )
                        ]
                    )
                ]
            ),
        )
        bubbles.append(bubble)

    carousel_container = FlexCarousel(contents=bubbles)

    return FlexMessage(
        alt_text='為您推薦了幾張信用卡！',
        contents=carousel_container)


def create_bank_grouped_carousel(grouped_data: dict) -> FlexMessage:
    """
    根據以銀行分組的資料，建立一個讓使用者新增卡片的 Flex Message 輪播。
    """
    if not grouped_data:
        return None

    bubbles = []
    # 遍歷每一家銀行
    for bank_name, cards in grouped_data.items():
        
        buttons = []
        for card in cards:
            button = FlexButton(
                action=MessageAction(
                    label=card['name'],  # 按鈕上顯示卡片簡稱
                    text=card['id']      # 按下後，實際送出卡片 ID
                ),
                style='link',
                height='sm',
                margin='sm'
            )
            buttons.append(button)
        
        bubble = FlexBubble(
            header=FlexBox(
                layout='vertical',
                contents=[
                    FlexText(text=bank_name, weight='bold', size='lg', align='center')
                ]
            ),
            body=FlexBox(
                layout='vertical',
                spacing='sm',
                contents=buttons
            )
        )
        bubbles.append(bubble)

    carousel_container = FlexCarousel(contents=bubbles)

    return FlexMessage(
        alt_text='請選擇您要新增的信用卡',
        contents=carousel_container
    )
