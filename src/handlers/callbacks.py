from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from src.states.analysis_states import AnalysisStates
from src.keyboards.main_menu import get_exit_confirmation_keyboard  # Added missing import
from src.keyboards.strategy import get_strategy_keyboard
from src.services.ollama_services import analyze_profile_with_ollama, generate_strategy  # Note: This is async in our setup
from src.services.redis_service import get_user_state_data, update_user_state_data, set_user_state
from src.utils.validators import truncate_caption
import src.config.settings as settings  # From previous fix
from src.utils.logger import logger
from src.core.bot import redis_storage  # ← NEW: Import redis_storage directly
from src.database import credit_payment, get_user_data, use_analysis

router = Router()

@router.callback_query(F.data == "main_start")
async def main_start_callback(callback: CallbackQuery, state: FSMContext):
    """Start analysis from main menu"""
    await callback.message.edit_text(
        "👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать.",
        reply_markup=None
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()

@router.callback_query(F.data == "main_price")
async def main_price_callback(callback: CallbackQuery, state: FSMContext):
    """Show pricing"""
    pricing_text = settings.PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", settings.PAYMENT_AMOUNT)
    await callback.message.answer(pricing_text, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "main_end")
async def main_end_callback(callback: CallbackQuery, state: FSMContext):
    """Ask for exit confirmation"""
    await callback.message.edit_text(
        "⚠️ Вы уверены?",
        reply_markup=get_exit_confirmation_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_end")
async def confirm_end_callback(callback: CallbackQuery, state: FSMContext):
    """Confirm end"""
    await callback.message.edit_text(
        "👋 Спасибо за использование FlirtAI!\n\nИспользуйте /start чтобы начать снова."
    )
    await state.clear()
    await callback.answer("✅ Анализ завершен.")

@router.callback_query(F.data == "cancel_end")
async def cancel_end_callback(callback: CallbackQuery, state: FSMContext):
    """Cancel exit"""
    current_state = await state.get_state()

    if current_state == AnalysisStates.waiting_for_link:
        await callback.message.edit_text(
            "👋 Пришли ссылку на Instagram-профиль."
        )
    elif current_state == AnalysisStates.waiting_for_strategy_choice:
        await callback.message.edit_text(
            "👇 Выбери один из трёх вариантов стратегии:",
            reply_markup=get_strategy_keyboard()
        )
    else:
        await callback.message.edit_text("Продолжаем анализ...")

    await callback.answer("✅ Продолжаем!")

@router.callback_query(F.data.startswith("receipt_is_valid:"))
async def handle_receipt_approve(callback: CallbackQuery):
    """
    Admin approves receipt - REFACTORED with proper FSM handling
    """
    try:
        _, user_id_str = callback.data.split(":", 1)
        user_id = int(user_id_str)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        await callback.answer("❌ Ошибка данных callback.")
        return

    # Quick ack to prevent timeout
    await callback.answer("✅ Чек одобрен — обрабатываю...")  # ← FIXED: Answer immediately
    # NEW: Credit on manual approval
    await credit_payment(user_id, float(settings.PAYMENT_AMOUNT_FLOAT))

    # Edit admin message
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=f"{callback.message.caption}\n\n✅ Чек одобрен администратором."
            )
        else:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n✅ Чек одобрен администратором."
            )
    except Exception as e:
        logger.debug(f"Couldn't edit message: {e}")

    await callback.answer("✅ Чек одобрен — пользователь уведомлён.")

    # Get user state and data using helper function
    try:
        # Notify user
        await callback.bot.send_message(user_id, "✅ Ваш чек одобрен! Начинаю анализ профиля...")

        # Get user data using helper function (FIX: Use redis_storage directly, not callback.bot.dp.storage)
        user_data = await get_user_state_data(redis_storage, user_id, bot_id=callback.bot.id)
        instagram_url = user_data.get('instagram_url')

        if not instagram_url:
            # If no link (e.g., pure top-up), prompt for one now
            await callback.bot.send_message(
                user_id,
                "👋 Пришли ссылку на Instagram-профиль для анализа.",
                reply_markup=get_strategy_keyboard()  # Or main menu; adjust as needed
            )
            await set_user_state(redis_storage, user_id, AnalysisStates.waiting_for_link, bot_id=callback.bot.id)
            return

        # NEW: Check and use analysis
        _, analyses = await get_user_data(user_id)
        if analyses < 1:
            await callback.bot.send_message(user_id, "❌ Нет доступных анализов. Пополните баланс!")
            return

        if not await use_analysis(user_id):
            await callback.bot.send_message(user_id, "❌ Ошибка при использовании анализа. Попробуйте позже.")
            return

        # Analyze profile (slow; do after ack)
        logger.info(f"🤖 Starting analysis for user {user_id}")
        analysis = await analyze_profile_with_ollama(instagram_url)

        # Send analysis
        await callback.bot.send_message(
            user_id,
            f"<b>📊 Анализ профиля:</b>\n\n{truncate_caption(analysis, 4096)}",
            parse_mode=ParseMode.HTML
        )

        # Send strategy options
        await callback.bot.send_message(
            user_id,
            "👇 Теперь выбери один из трёх вариантов стратегии:",
            reply_markup=get_strategy_keyboard()
        )

        # Update FSM state and data using helper functions (FIX: Use redis_storage)
        updated_data = {
            'instagram_url': instagram_url,
            'analysis': analysis
        }

        success_data = await update_user_state_data(redis_storage, user_id, updated_data, bot_id=callback.bot.id)
        success_state = await set_user_state(redis_storage, user_id, AnalysisStates.waiting_for_strategy_choice, bot_id=callback.bot.id)

        if success_data and success_state:
            logger.info(f"✅ Analysis data and state saved for user {user_id}")
        else:
            logger.warning(f"⚠️ Failed to save FSM data for user {user_id}")

    except Exception as e:
        logger.error(f"Error in receipt approval: {e}", exc_info=True)
        try:
            await callback.bot.send_message(

                user_id,
                f"❌ Произошла ошибка при обработке вашего запроса. Попробуйте начать заново с /start"
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {user_id}: {send_error}")

# NEW: Balance callback (shows table)
@router.callback_query(F.data == "show_balance")
async def show_balance_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance, analyses = await get_user_data(user_id)

    table = f"""
💳 <b>Ваш баланс:</b>

| Параметр              | Значение      |
|-----------------------|---------------|
| Баланс (KZT)          | {balance:.2f} ₸ |
| Доступных анализов    | {analyses}    |

💡 Каждый анализ: {settings.PAYMENT_AMOUNT} / 3 = {settings.PAYMENT_AMOUNT_FLOAT / 3:.0f} ₸
    """
    await callback.message.answer(table, parse_mode=ParseMode.HTML)
    await callback.answer()

# NEW: Top-up callback (starts payment flow)
@router.callback_query(F.data == "top_up")
async def top_up_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"Спасибо! 🔁 Теперь переведи **{settings.PAYMENT_AMOUNT}** на Kaspi: `{settings.KASPI_NUMBER}`\n\n"
        "📎 После оплаты пришли PDF или фото чека.",
        parse_mode=ParseMode.MARKDOWN
    )
    await state.set_state(AnalysisStates.waiting_for_receipt)  # Directly to receipt wait (no link needed for top-up)
    await callback.answer()
@router.callback_query(F.data.startswith("receipt_is_not_valid:"))
async def handle_receipt_reject(callback: CallbackQuery):
    """
    Admin rejects receipt - REFACTORED with proper FSM handling
    """
    try:
        _, user_id_str = callback.data.split(":", 1)
        user_id = int(user_id_str)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        await callback.answer("❌ Ошибка данных callback.")
        return

    # Edit admin message
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=f"{callback.message.caption}\n\n🔁 Запрошена повторная отправка."
            )
        else:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n🔁 Запрошена повторная отправка."
            )
    except Exception as e:
        logger.debug(f"Couldn't edit message: {e}")

    await callback.answer("🔁 Запрос отправлен пользователю.")

    # Notify user and return to receipt state using helper function
    try:
        await callback.bot.send_message(
            user_id,
            "🔁 Администратор запросил повторную отправку чека. "
            "Пожалуйста, пришлите корректный чек."
        )

        # Set state back to waiting for receipt using helper function (FIX: Use redis_storage)
        success = await set_user_state(redis_storage, user_id, AnalysisStates.waiting_for_receipt, bot_id=callback.bot.id)

        if success:
            logger.info(f"✅ User {user_id} state reset to waiting_for_receipt")
        else:
            logger.warning(f"⚠️ Failed to reset state for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}", exc_info=True)

@router.callback_query(F.data.startswith("strategy_"))
async def strategy_handler(callback: CallbackQuery, state: FSMContext):
    """Handle strategy selection"""
    strategy_type = callback.data.split("_")[1]
    data = await state.get_data()
    analysis = data.get('analysis')

    if not analysis:
        await callback.answer("❌ Анализ не найден.", show_alert=True)
        logger.warning(f"Analysis not found for user {callback.from_user.id}")
        return

        # Quick ack to prevent timeout
    await callback.message.edit_text("🤖 Генерирую персональную стратегию...")  # ← FIXED: Edit immediately
    await callback.answer("Генерирую...")  # ← Quick ack

    # Slow op after ack
    strategy = await generate_strategy(analysis, strategy_type)

    strategy_names = {
        "professional": "🧑‍💼 Профессиональная стратегия",
        "personal": "❤️ Личная стратегия",
        "trash": "🤪 Трешовая стратегия"
    }

    # Send strategy
    await callback.message.answer(
        f"<b>{strategy_names[strategy_type]}:</b>\n\n{truncate_caption(strategy, 4096)}",
        parse_mode=ParseMode.HTML
    )

    # Request feedback
    from src.keyboards.feedback import get_rating_keyboard
    await callback.message.answer(
        "📊 Оцени результат от 1 до 10:",
        reply_markup=get_rating_keyboard()
    )

    await state.set_state(AnalysisStates.waiting_for_feedback)
    await callback.answer()

@router.callback_query(F.data.startswith("rating_"))
async def rating_handler(callback: CallbackQuery, state: FSMContext):
    """Handle rating"""
    rating = callback.data.split("_")[1]

    await callback.message.edit_text(f"⭐ Спасибо за оценку: {rating}/10")

    from src.keyboards.feedback import get_restart_keyboard
    await callback.message.answer(
        "🗣 Можешь оставить комментарий или нажать кнопку ниже:",
        reply_markup=get_restart_keyboard()
    )

    # Send rating to admin
    try:
        await callback.bot.send_message(
            settings.ADMIN_ID,
            f"⭐ Новая оценка от @{callback.from_user.username or callback.from_user.id}: {rating}/10"
        )
    except Exception as e:
        logger.error(f"Failed to send rating to admin: {e}")

    await callback.answer()

@router.callback_query(F.data == "restart")
async def restart_handler(callback: CallbackQuery, state: FSMContext):
    """Restart analysis"""
    await state.clear()
    await callback.message.answer(
        "👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать."
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()