from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardRemove
from src.states.analysis_states import AnalysisStates
from src.keyboards.main_menu import get_main_menu_keyboard, get_exit_confirmation_keyboard
from src.keyboards.reply_keyboard import get_reply_keyboard
import src.config.settings as settings
from src.database import get_user_data

router = Router()

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()

    # FIXED: Remove any cached keyboard FIRST
    await message.answer(
        "👋 Привет! Добро пожаловать в FlirtAI!\n\n"
        "Я помогу тебе проанализировать Instagram профиль и получить персональную стратегию знакомства.",
        reply_markup=ReplyKeyboardRemove(remove_keyboard=True),  # ← NEW: Clears bottom menu
    )

    await message.answer(
        "👋 Привет! Добро пожаловать в FlirtAI!\n\n"
        "Я помогу тебе проанализировать Instagram профиль и получить персональную стратегию знакомства.",
        reply_markup=get_main_menu_keyboard()
    )

    # OPTIONAL: Add /clear command for manual reset
    @router.message(F.text == "/clear")
    async def clear_keyboard_handler(message: Message):
        """Manually remove keyboard."""
        await message.answer(
            "✅ Клавиатура сброшена!",
            reply_markup=ReplyKeyboardRemove(remove_keyboard=True)
        )

    await state.set_state(AnalysisStates.in_main_menu)

# NEW: Balance button handler (text-based)
@router.message(F.text == "💳 Баланс")
async def balance_button_handler(message: Message):
    """Show user balance and analyses as table (via button)."""
    user_id = message.from_user.id
    balance, analyses = await get_user_data(user_id)

    table = f"""
💳 <b>Ваш баланс:</b>

| Параметр              | Значение      |
|-----------------------|---------------|
| Баланс (KZT)          | {balance:.2f} ₸ |
| Доступных анализов    | {analyses}    |

💡 Каждый анализ: {settings.PAYMENT_AMOUNT} / 3 = {settings.PAYMENT_AMOUNT_FLOAT / 3:.0f} ₸
    """
    await message.answer(table, parse_mode=ParseMode.HTML, reply_markup=get_reply_keyboard())  # Keep menu
@router.message(F.text == "/end")
async def end_command_handler(message: Message, state: FSMContext):
    """Handle /end command"""
    current_state = await state.get_state()

    if current_state == AnalysisStates.in_main_menu:
        await message.answer(
            "👋 Спасибо за использование FlirtAI! Используйте /start чтобы начать снова."
        )
        await state.clear()
        return

    await message.answer(
        "⚠️ Вы в процессе анализа. Вы уверены?",
        reply_markup=get_exit_confirmation_keyboard()
    )

@router.message(F.text == "/price")
async def price_command_handler(message: Message, state: FSMContext):
    """Handle /price command"""
    pricing_text = settings.PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", settings.PAYMENT_AMOUNT)
    await message.answer(pricing_text, parse_mode=ParseMode.HTML)


# UPDATED: Handle both /balance command and "💳 Баланс" button
@router.message(F.text.in_(["/balance", "💳 Баланс"]))  # ← Covers command & button
async def balance_handler(message: Message):
    """Show user balance and analyses as table (command or button)."""
    user_id = message.from_user.id
    balance, analyses = await get_user_data(user_id)

    table = f"""
💳 <b>Ваш баланс:</b>

| Параметр              | Значение      |
|-----------------------|---------------|
| Баланс (KZT)          | {balance:.2f} ₸ |
| Доступных анализов    | {analyses}    |

💡 Каждый анализ: {settings.PAYMENT_AMOUNT} / 3 = {settings.PAYMENT_AMOUNT_FLOAT / 3:.0f} ₸
    """
    await message.answer(table, parse_mode=ParseMode.HTML)