from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_rating_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="rating_1"),
            InlineKeyboardButton(text="2", callback_data="rating_2"),
            InlineKeyboardButton(text="3", callback_data="rating_3"),
            InlineKeyboardButton(text="4", callback_data="rating_4"),
            InlineKeyboardButton(text="5", callback_data="rating_5")
        ],
        [
            InlineKeyboardButton(text="6", callback_data="rating_6"),
            InlineKeyboardButton(text="7", callback_data="rating_7"),
            InlineKeyboardButton(text="8", callback_data="rating_8"),
            InlineKeyboardButton(text="9", callback_data="rating_9"),
            InlineKeyboardButton(text="10", callback_data="rating_10")
        ]
    ])
    return keyboard

def get_restart_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Начать заново", callback_data="restart")]
    ])
    return keyboard