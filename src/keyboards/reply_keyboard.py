from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom menu keyboard (reply keyboard)."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 /start")],  # Matches screenshot
            [KeyboardButton(text="💰 /price")],
            [KeyboardButton(text="💳 Баланс")],  # ← NEW: Balance button
            [KeyboardButton(text="💰 Пополнить")],  # ← NEW: Top-up button
            [KeyboardButton(text="🛑 /end")],
        ],
        resize_keyboard=True,  # Fits screen
        one_time_keyboard=False,  # Persistent
        is_persistent=True,
    )
    return keyboard