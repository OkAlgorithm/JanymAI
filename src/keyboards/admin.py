from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_receipt_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard sent to admin to approve / request resend for a specific user's receipt."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобряю", callback_data=f"receipt_is_valid:{user_id}")],
        [InlineKeyboardButton(text="🔁 Повторно отправить чек", callback_data=f"receipt_is_not_valid:{user_id}")]
    ])