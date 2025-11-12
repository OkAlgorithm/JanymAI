from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.enums import ParseMode
from src.states.analysis_states import AnalysisStates
from src.keyboards.strategy import get_strategy_keyboard
from src.services.file_service import download_file
from src.services.kaspi_services import verify_payment_kaspi, verify_receipt_image, simple_receipt_check
from src.services.ollama_services import analyze_profile_with_ollama
from src.services.redis_service import get_user_state_data
from src.keyboards.admin import get_admin_receipt_keyboard
from src.keyboards.reply_keyboard import get_reply_keyboard
from src.keyboards.main_menu import get_main_menu_keyboard
from src.utils.validators import truncate_caption
import src.config.settings as settings
from src.utils.logger import logger
import requests  # For admin send
from src.database import get_user_data, credit_payment, use_analysis

router = Router()

@router.message(AnalysisStates.waiting_for_link)
async def link_handler(message: Message, state: FSMContext):
    """Handle Instagram link submission"""
    instagram_url = message.text

    if "instagram.com" not in instagram_url:
        await message.answer("❌ Пожалуйста, отправь корректную ссылку на Instagram профиль.")
        return

    await state.update_data(instagram_url=instagram_url)
    await message.answer(
        f"Спасибо! 🔁 Теперь переведи **{settings.PAYMENT_AMOUNT}** на Kaspi: `{settings.KASPI_NUMBER}`\n\n"
        "📎 После оплаты пришли PDF или фото чека.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_reply_keyboard()
    )
    await state.set_state(AnalysisStates.waiting_for_receipt)

@router.message(AnalysisStates.waiting_for_receipt, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: Message, state: FSMContext):
    """Handle receipt submission"""
    data = await state.get_data()
    instagram_url = data.get('instagram_url')

    if not instagram_url:
        await message.answer("❌ Ошибка: ссылка на профиль не найдена. Начните с /start")
        return

    await message.answer("⏳ Проверяю платёж...")

    try:
        # Download file
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или PDF документа.")
            return

        file_data = await download_file(message.bot, file_id)

        # Verify payment
        is_valid = False
        verification_message = ""

        if settings.USE_KASPI_API:
            logger.info("🔍 Verifying payment with Kaspi API...")
            is_valid, verification_message = await verify_payment_kaspi(
                settings.PAYMENT_AMOUNT,
                message.from_user.username or ""
            )
        else:
            logger.info("🔍 Verifying receipt image...")
            is_valid, verification_message = await verify_receipt_image(file_data, settings.PAYMENT_AMOUNT)  # Already awaited

            if not is_valid and "vision" in verification_message.lower():
                logger.info("⚠️ Using simple verification...")
                is_valid, verification_message = await simple_receipt_check(file_data)  # Await if made async later

        # Send to admin (unchanged)
        keyboard = get_admin_receipt_keyboard(message.from_user.id)

        caption_parts = [
            "💸 Новая заявка!",
            f"🔗 Ссылка: {instagram_url}",
            f"👤 Пользователь: @{message.from_user.username or message.from_user.id}",
            f"📝 Проверка: {'✅ Автоматически подтверждена' if is_valid else '⚠️ Требует ручной проверки'}",
            f"📋 {verification_message}"
        ]

        caption = truncate_caption("\n".join(caption_parts))

        try:
            if message.photo:
                await message.bot.send_photo(settings.ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
            else:
                await message.bot.send_document(settings.ADMIN_ID, message.document.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error sending to admin: {e}")
            simple_caption = f"💸 Новая заявка!\n🔗 {instagram_url}\n👤 @{message.from_user.username or message.from_user.id}"
            if message.photo:
                await message.bot.send_photo(settings.ADMIN_ID, message.photo[-1].file_id, caption=simple_caption, reply_markup=keyboard)
            else:
                await message.bot.send_document(settings.ADMIN_ID, message.document.file_id, caption=simple_caption,
                                                reply_markup=keyboard)

        if not is_valid:
            await message.answer("🔍 Чек отправлен администратору для подтверждения. Ожидайте решения.")
        else:
            # NEW: Credit on auto-verification
            await credit_payment(message.from_user.id, float(settings.PAYMENT_AMOUNT_FLOAT))

            await message.answer(f"✅ {verification_message}\n\n🤖 Начинаю анализ профиля...")

            # NEW: Check and use analysis
            _, analyses = await get_user_data(message.from_user.id)
            if analyses < 1:
                await message.answer("❌ Нет доступных анализов. Пополните баланс!")
                return

            if not await use_analysis(message.from_user.id):
                await message.answer("❌ Ошибка при использовании анализа. Попробуйте позже.")
                return

            # Proceed with analysis
            analysis = await analyze_profile_with_ollama(instagram_url)

            # Send analysis to user
            await message.answer(
                f"<b>📊 Анализ профиля:</b>\n\n{truncate_caption(analysis, 4096)}",
                parse_mode=ParseMode.HTML
            )

            await message.answer(
                "👇 Теперь выбери один из трёх вариантов стратегии:",
                reply_markup=get_strategy_keyboard()
            )
            # And in pure top-up case (if no url):
            await message.answer(
                "✅ Пополнение завершено! Теперь начни анализ:",
                reply_markup=get_main_menu_keyboard()  # ← Ensure menu shows
            )
            await state.update_data(analysis=analysis)
            await state.set_state(AnalysisStates.waiting_for_strategy_choice)

    except Exception as e:
        logger.error(f"Receipt handler error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}\n\nПопробуйте ещё раз.")

@router.message(AnalysisStates.waiting_for_feedback)
async def feedback_handler(message: Message, state: FSMContext):
    """Handle feedback"""
    feedback = message.text

    # Send feedback to admin
    try:
        await message.bot.send_message(
            settings.ADMIN_ID,
            f"💬 Новый отзыв от @{message.from_user.username or message.from_user.id}:\n{feedback}"
        )
    except Exception as e:
        logger.error(f"Failed to send feedback to admin: {e}")

    from src.keyboards.feedback import get_restart_keyboard
    await message.answer(
        "✅ Спасибо за отзыв!",
        reply_markup=get_reply_keyboard()
    )
