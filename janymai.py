import asyncio
import logging
import os
import requests
import base64
from io import BytesIO
from typing import Dict, Any
import aiohttp

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import Dialog, Window, setup_dialogs, DialogManager
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.kbd import (
    Checkbox, Button, Row, Cancel, Start, Group, Select
)
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
KASPI_NUMBER = os.getenv("KASPI_NUMBER")
PAYMENT_AMOUNT = os.getenv("PAYMENT_AMOUNT")
KASPI_API_KEY = os.getenv("KASPI_API_KEY", "")
KASPI_MERCHANT_ID = os.getenv("KASPI_MERCHANT_ID", "")
USE_KASPI_API = os.getenv("USE_KASPI_API", "false").lower() == "true"

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL_LLAMA2 = os.getenv("OLLAMA_MODEL_LLAMA2")
OLLAMA_MODEL_LLAVA = os.getenv("OLLAMA_MODEL_LLAVA")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


# ==================== STATES ====================
class MainMenuSG(StatesGroup):
    MAIN = State()
    PRICING = State()


class AnalysisSG(StatesGroup):
    WAITING_FOR_LINK = State()
    WAITING_FOR_RECEIPT = State()
    STRATEGY_SELECTION = State()
    FEEDBACK = State()


# ==================== OLLAMA FUNCTIONS ====================
def call_ollama(messages: list, max_tokens: int = 3000) -> str:
    """Call local Ollama API"""
    try:
        print(f"  → Testing connection to Ollama at {OLLAMA_API_URL}...")
        try:
            health_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            print(f"  ✅ Ollama is reachable")
        except Exception as e:
            print(f"  ⚠️ Cannot reach Ollama at {OLLAMA_API_URL}")
            return "Error: Ollama service not available"

        print(f"  → Sending request to model: {OLLAMA_MODEL_LLAMA2}")

        payload = {
            "model": OLLAMA_MODEL_LLAMA2,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "num_predict": max_tokens
        }

        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=120)

        if response.status_code == 404:
            return f"Error: Model '{OLLAMA_MODEL_LLAMA2}' not found"

        response.raise_for_status()
        result = response.json()
        return result.get("message", {}).get("content", "")

    except Exception as e:
        logging.error(f"❌ Ollama API error: {e}")
        return f"Error: {str(e)}"


async def analyze_profile_with_ollama(profile_url: str) -> str:
    """Analyze Instagram profile using Ollama"""
    try:
        print(f"🤖 Analyzing Instagram profile: {profile_url}")
        username = profile_url.split('/')[-1].split('?')[0]

        system_prompt = """
        Вы — эксперт в области социального профилирования и анализа профилей Instagram.
        Проведите глубокий анализ профиля Instagram на основе URL профиля и имени пользователя.

        Анализируйте:
        1. Типичные характеристики профиля
        2. Интересы на основе имени пользователя
        3. Социальный статус
        4. Общую оценку личности

        Проведи анализ на Русском Языке.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Проанализируй Instagram профиль: {username}"}
        ]

        analysis = call_ollama(messages, max_tokens=2000)
        return analysis if not analysis.startswith("Error:") else "Ошибка при анализе профиля."

    except Exception as e:
        logging.error(f"❌ Error analyzing profile: {e}")
        return "Ошибка при анализе профиля."


async def generate_strategy(analysis: str, strategy_type: str) -> str:
    """Generate approach strategy"""
    try:
        strategy_prompts = {
            "professional": "Создай профессиональную стратегию знакомства",
            "personal": "Создай личную романтическую стратегию знакомства",
            "trash": "Создай креативную и необычную стратегию знакомства"
        }

        prompt = f"""
        На основе анализа создай {strategy_prompts[strategy_type]}.

        Анализ: {analysis}

        Дай конкретные рекомендации:
        - Как начать диалог
        - О чем говорить
        - Каких тем избегать
        - Какой подход использовать
        """

        messages = [{"role": "user", "content": prompt}]
        strategy = call_ollama(messages, max_tokens=1000)
        return strategy if not strategy.startswith("Error:") else "Ошибка при создании стратегии."

    except Exception as e:
        logging.error(f"❌ Error generating strategy: {e}")
        return "Ошибка при создании стратегии."


# ==================== PAYMENT VERIFICATION ====================
async def verify_receipt_image(file_bytes: bytes, expected_amount: str) -> tuple[bool, str]:
    """Verify receipt image"""
    try:
        image_base64 = base64.b64encode(file_bytes).decode('utf-8')

        payload = {
            "model": OLLAMA_MODEL_LLAVA,
            "messages": [
                {"role": "user", "content": f"Verify receipt. Expected: {expected_amount}", "images": [image_base64]}],
            "stream": False,
            "max_tokens": 150
        }

        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()
            receipt_info = result.get("message", {}).get("content", "")
            if "is_valid" in receipt_info and "true" in receipt_info.lower():
                return True, "✅ Чек подтвержден"
            else:
                return False, "❌ Ошибка валидации"
        else:
            return False, "❌ Ошибка обработки"

    except Exception as e:
        logging.error(f"Receipt verification error: {e}")
        return False, "❌ Ошибка валидации"


# ==================== DIALOGS ====================

# ===== MAIN MENU DIALOG =====
async def main_menu_getter(dialog_manager: DialogManager, **kwargs) -> Dict[str, Any]:
    return {"payment_amount": PAYMENT_AMOUNT}


main_menu_dialog = Dialog(
    Window(
        Format(
            "👋 Привет! Добро пожаловать в FlirtAI!\n\n"
            "Я помогу тебе проанализировать Instagram профиль и получить персональную стратегию знакомства."
        ),
        Start(Const("🚀 Начать анализ"), id="start_analysis", state=AnalysisSG.WAITING_FOR_LINK),
        Start(Const("💰 Узнать цену"), id="show_price", state=MainMenuSG.PRICING),
        state=MainMenuSG.MAIN,
    ),
    Window(
        Format(
            "💰 <b>Наша Цена:</b>\n\n"
            "🔍 <b>Анализ Instagram профиля</b>\n"
            "• Полный психологический анализ\n"
            "• Определение типа личности\n"
            "• Анализ интересов и ценностей\n\n"
            "💵 <b>Стоимость:</b> {payment_amount} ₸\n\n"
            "📊 <b>В пакет включено:</b>\n"
            "✅ Анализ профиля\n"
            "✅ 3 варианта стратегии\n"
            "✅ Персональные рекомендации\n\n"
            "⏱️ <b>Время обработки:</b> 2-3 минуты"
        ),
        Cancel(Const("🔙 Назад")),
        state=MainMenuSG.PRICING,
        getter=main_menu_getter,
    ),
)


# ===== ANALYSIS DIALOG =====
async def analysis_getter(dialog_manager: DialogManager, **kwargs) -> Dict[str, Any]:
    data = dialog_manager.dialog_data
    return {
        "instagram_url": data.get("instagram_url", ""),
        "strategy_type": data.get("strategy_type", ""),
    }


strategy_choices = [
    ("professional", "🧑‍💼 Профессиональное"),
    ("personal", "❤️ Личное"),
    ("trash", "🤪 Креативное"),
]

rating_choices = [str(i) for i in range(1, 11)]

analysis_dialog = Dialog(
    # Step 1: Enter Instagram Link
    Window(
        Const("👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать.\n\n"
              "Доступные команды: /price, /end"),
        state=AnalysisSG.WAITING_FOR_LINK,
        getter=analysis_getter,
    ),

    # Step 2: Payment Receipt
    Window(
        Format(
            "Спасибо! 🔁 Теперь переведи <b>{payment_amount}</b> на Kaspi: <code>{kaspi_number}</code>\n\n"
            "📎 После оплаты пришли фото чека.\n\n"
            "Доступные команды: /price, /end"
        ),
        Cancel(Const("🔙 Отмена")),
        state=AnalysisSG.WAITING_FOR_RECEIPT,
    ),

    # Step 3: Strategy Selection
    Window(
        Const("👇 Теперь выбери один из трёх вариантов стратегии:\n\n"
              "Доступные команды: /end"),
        Select(
            Format("{item[1]}"),
            id="strategy_select",
            item_id_getter=lambda x: x[0],
            items=strategy_choices,
            on_click=lambda c, widget, manager, item_id: None,
        ),
        Cancel(Const("🔙 Назад")),
        state=AnalysisSG.STRATEGY_SELECTION,
        getter=analysis_getter,
    ),

    # Step 4: Feedback
    Window(
        Const("📊 Оцени результат от 1 до 10:\n\n"
              "Доступные команды: /end"),
        Select(
            Format("{item}"),
            id="rating_select",
            item_id_getter=lambda x: x,
            items=rating_choices,
            on_click=lambda c, widget, manager, item_id: None,
        ),
        Cancel(Const("🔙 Начать заново")),
        state=AnalysisSG.FEEDBACK,
    ),
)

# ==================== MESSAGE HANDLERS ====================
router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message, dialog_manager: DialogManager):
    """Start command - open main menu"""
    await dialog_manager.start(MainMenuSG.MAIN)


@router.message(Command("end"))
async def end_handler(message: types.Message, dialog_manager: DialogManager):
    """End command - close dialog"""
    try:
        await dialog_manager.done()
    except:
        pass
    await message.answer("👋 Спасибо за использование FlirtAI! Используйте /start чтобы начать снова.")


@router.message(Command("price"))
async def price_handler(message: types.Message, dialog_manager: DialogManager):
    """Price command - show pricing (only outside analysis)"""
    try:
        current_state = dialog_manager.current_stack()
        if current_state and len(current_state) > 0:
            # Already in analysis dialog
            await message.answer("⚠️ Вы в процессе анализа. Используйте /end если хотите выйти.")
            return
    except:
        pass

    pricing_text = (
        "💰 <b>Наша Цена:</b>\n\n"
        "🔍 <b>Анализ Instagram профиля</b>\n"
        "• Полный психологический анализ\n"
        "• Определение типа личности\n"
        "• Анализ интересов и ценностей\n\n"
        f"💵 <b>Стоимость:</b> {PAYMENT_AMOUNT} ₸\n\n"
        "📊 <b>В пакет включено:</b>\n"
        "✅ Анализ профиля\n"
        "✅ 3 варианта стратегии\n"
        "✅ Персональные рекомендации\n\n"
        "⏱️ <b>Время обработки:</b> 2-3 минуты"
    )
    await message.answer(pricing_text, parse_mode=ParseMode.HTML)

    await message.answer("Хотите начать анализ? Используйте /start")


# CRITICAL: Must have higher priority than dialog message handlers
@router.message(AnalysisSG.WAITING_FOR_LINK, ~F.text.startswith("/"))
async def link_input_handler(message: types.Message, dialog_manager: DialogManager):
    """Handle Instagram link input"""
    print(f"📍 Link input received: {message.text}")

    if "instagram.com" not in message.text:
        await message.answer("❌ Пожалуйста, отправь корректную ссылку на Instagram профиль.")
        return

    print(f"✅ Valid link detected, switching state...")
    dialog_manager.dialog_data["instagram_url"] = message.text
    dialog_manager.dialog_data["kaspi_number"] = KASPI_NUMBER
    dialog_manager.dialog_data["payment_amount"] = PAYMENT_AMOUNT

    await dialog_manager.switch_to(AnalysisSG.WAITING_FOR_RECEIPT)

    await message.answer(
        f"Спасибо! 🔁 Теперь переведи <b>{PAYMENT_AMOUNT}</b> на Kaspi: <code>{KASPI_NUMBER}</code>\n\n"
        "📎 После оплаты пришли фото чека.",
        parse_mode=ParseMode.HTML
    )


@router.message(AnalysisSG.WAITING_FOR_RECEIPT, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: types.Message, dialog_manager: DialogManager):
    """Handle payment receipt"""
    print("📍 Receipt received")
    await message.answer("⏳ Проверяю платёж...")

    try:
        # Download file
        if message.photo:
            file_id = message.photo[-1].file_id
            file_info = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file_info.file_path)
        else:
            file_id = message.document.file_id
            file_info = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file_info.file_path)

        file_bytes_io = BytesIO()
        file_bytes_io.write(file_bytes.read())
        file_data = file_bytes_io.getvalue()

        # Verify receipt
        is_valid, verification_message = await verify_receipt_image(file_data, PAYMENT_AMOUNT)

        instagram_url = dialog_manager.dialog_data.get("instagram_url")

        # Send to admin
        caption = f"💸 Новая заявка!\n🔗 {instagram_url}\n👤 @{message.from_user.username or message.from_user.id}"
        if len(caption) <= 1000:
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)
            else:
                await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption)

        if is_valid:
            await message.answer(f"✅ {verification_message}\n\n🤖 Начинаю анализ профиля...")
            analysis = await analyze_profile_with_ollama(instagram_url)
            dialog_manager.dialog_data["analysis"] = analysis
            await dialog_manager.switch_to(AnalysisSG.STRATEGY_SELECTION)
            await message.answer("👇 Теперь выбери один из трёх вариантов стратегии:")
        else:
            await message.answer("🔍 Чек отправлен администратору для подтверждения. Ожидайте решения.")

    except Exception as e:
        logging.error(f"Receipt handler error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(AnalysisSG.STRATEGY_SELECTION)
async def strategy_selected(callback: types.CallbackQuery, widget, manager: DialogManager, item_id: str):
    """Handle strategy selection"""
    manager.dialog_data["strategy_type"] = item_id
    analysis = manager.dialog_data.get("analysis", "")
    strategy = await generate_strategy(analysis, item_id)

    strategy_names = {
        "professional": "🧑‍💼 Профессиональная стратегия",
        "personal": "❤️ Личная стратегия",
        "trash": "🤪 Креативная стратегия"
    }

    await callback.message.answer(f"<b>{strategy_names[item_id]}:</b>\n\n{strategy}")
    await manager.next()
    await callback.message.answer("📊 Оцени результат от 1 до 10:", reply_markup=None)


@router.callback_query(AnalysisSG.FEEDBACK)
async def rating_selected(callback: types.CallbackQuery, widget, manager: DialogManager, item_id: str):
    """Handle rating submission"""
    try:
        await bot.send_message(ADMIN_ID, f"⭐ Новая оценка: {item_id}/10")
    except:
        pass

    await callback.message.answer(
        "✅ Спасибо за отзыв!\n\nИспользуйте /start чтобы начать заново или /price чтобы узнать цены."
    )
    await manager.done()


from aiogram.types import BotCommand


# ==================== MAIN ====================
async def main():
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(main_menu_dialog)
    dp.include_router(analysis_dialog)
    dp.include_router(router)

    setup_dialogs(dp)

    # Set command scope - show available commands when typing /
    commands = [
        BotCommand(command="start", description="🚀 Начать анализ профиля"),
        BotCommand(command="price", description="💰 Узнать цену"),
        BotCommand(command="end", description="🛑 Завершить анализ"),
    ]
    await bot.set_my_commands(commands)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())