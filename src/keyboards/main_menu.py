from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard():
    """Main menu keyboard shown before /start is used"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать анализ", callback_data="main_start")],
        [InlineKeyboardButton(text="💰 Узнать цену", callback_data="main_price")],
        [InlineKeyboardButton(text="💳 Баланс", callback_data="show_balance")],  # ← NEW: Balance button
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="top_up")],  # ← NEW: Top-up button
    ])
    return keyboard

def get_analysis_menu_keyboard():
    """Menu keyboard shown during analysis (/start is active)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Завершить", callback_data="main_end")],
    ])
    return keyboard

def get_exit_confirmation_keyboard():
    """Confirmation keyboard when user tries to exit"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, завершить", callback_data="confirm_end"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_end"),
        ]
    ])
    return keyboard