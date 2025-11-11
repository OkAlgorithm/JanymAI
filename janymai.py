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
        print(f"🤖 [OLLAMA] Testing connection to {OLLAMA_API_URL}...")
        try:
            health_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            print(f"✅ [OLLAMA] Connection successful")
        except Exception as e:
            print(f"⚠️ [OLLAMA] Cannot reach Ollama at {OLLAMA_API_URL}: {e}")
            return "Error: Ollama service not available"

        print(f"🤖 [OLLAMA] Sending request to model: {OLLAMA_MODEL_LLAMA2}")
        print(f"📊 [OLLAMA] Messages count: {len(messages)}, Max tokens: {max_tokens}")

        payload = {
            "model": OLLAMA_MODEL_LLAMA2,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "num_predict": max_tokens
        }

        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=120)
        print(f"📡 [OLLAMA] Response status code: {response.status_code}")

        if response.status_code == 404:
            error_msg = f"Error: Model '{OLLAMA_MODEL_LLAMA2}' not found"
            print(f"❌ [OLLAMA] {error_msg}")
            return error_msg

        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "")
        print(f"✅ [OLLAMA] Response received, content length: {len(content)} chars")
        return content

    except Exception as e:
        print(f"❌ [OLLAMA] Error: {type(e).__name__}: {e}")
        logging.error(f"❌ Ollama API error: {e}", exc_info=True)
        return f"Error: {str(e)}"


async def analyze_profile_with_ollama(profile_url: str) -> str:
    """Analyze Instagram profile using Ollama"""
    try:
        print(f"\n🎯 [ANALYSIS] Starting profile analysis")
        print(f"   📎 URL: {profile_url}")
        username = profile_url.split('/')[-1].split('?')[0]
        print(f"   👤 Extracted username: {username}")

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

        print(f"   🔄 Calling Ollama API...")
        analysis = call_ollama(messages, max_tokens=2000)

        if analysis.startswith("Error:"):
            print(f"   ❌ [ANALYSIS] Error returned: {analysis}")
            return "Ошибка при анализе профиля."

        print(f"   ✅ [ANALYSIS] Complete, result length: {len(analysis)} chars")
        return analysis

    except Exception as e:
        print(f"   ❌ [ANALYSIS] Exception: {type(e).__name__}: {e}")
        logging.error(f"❌ Error analyzing profile: {e}", exc_info=True)
        return "Ошибка при анализе профиля."


async def generate_strategy(analysis: str, strategy_type: str) -> str:
    """Generate approach strategy"""
    try:
        print(f"\n🎯 [STRATEGY] Generating strategy")
        print(f"   📌 Type: {strategy_type}")
        print(f"   📄 Analysis length: {len(analysis)} chars")

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
        print(f"   🔄 Calling Ollama API...")
        strategy = call_ollama(messages, max_tokens=1000)

        if strategy.startswith("Error:"):
            print(f"   ❌ [STRATEGY] Error returned: {strategy}")
            return "Ошибка при создании стратегии."

        print(f"   ✅ [STRATEGY] Complete, result length: {len(strategy)} chars")
        return strategy

    except Exception as e:
        print(f"   ❌ [STRATEGY] Exception: {type(e).__name__}: {e}")
        logging.error(f"❌ Error generating strategy: {e}", exc_info=True)
        return "Ошибка при создании стратегии."


# ==================== PAYMENT VERIFICATION ====================
async def verify_receipt_image(file_bytes: bytes, expected_amount: str) -> tuple[bool, str]:
    """Verify receipt image"""
    try:
        print(f"\n🔍 [RECEIPT] Starting verification")
        print(f"   📦 File size: {len(file_bytes)} bytes")
        print(f"   💰 Expected amount: {expected_amount}")

        image_base64 = base64.b64encode(file_bytes).decode('utf-8')
        print(f"   ✅ Base64 encoding complete: {len(image_base64)} chars")

        payload = {
            "model": OLLAMA_MODEL_LLAVA,
            "messages": [
                {"role": "user", "content": f"Verify receipt. Expected: {expected_amount}", "images": [image_base64]}],
            "stream": False,
            "max_tokens": 150
        }

        print(f"   🔄 Sending to LLaVA model: {OLLAMA_MODEL_LLAVA}")
        response = requests.post(f"{OLLAMA_API_URL}/api/chat", json=payload, timeout=60)
        print(f"   📡 Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            receipt_info = result.get("message", {}).get("content", "")
            print(f"   📄 Receipt info: {receipt_info[:100]}...")

            if "is_valid" in receipt_info and "true" in receipt_info.lower():
                print(f"   ✅ [RECEIPT] Validation PASSED")
                return True, "✅ Чек подтвержден"
            else:
                print(f"   ❌ [RECEIPT] Validation FAILED")
                return False, "❌ Ошибка валидации"
        else:
            print(f"   ❌ [RECEIPT] Bad status code: {response.status_code}")
            return False, "❌ Ошибка обработки"

    except Exception as e:
        print(f"   ❌ [RECEIPT] Exception: {type(e).__name__}: {e}")
        logging.error(f"Receipt verification error: {e}", exc_info=True)
        return False, "❌ Ошибка валидации"


# ==================== DIALOGS ====================

# ===== MAIN MENU DIALOG =====
async def main_menu_getter(dialog_manager: DialogManager, **kwargs) -> Dict[str, Any]:
    """Main menu data getter with debugging"""
    print(f"📊 [MAIN_MENU_GETTER] Rendering main menu")
    print(f"   Current state: {dialog_manager.current_stack()}")
    print(f"   Dialog data: {dialog_manager.dialog_data}")
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
        getter=main_menu_getter,
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
    """Analysis dialog data getter with debugging"""
    data = dialog_manager.dialog_data
    print(f"📊 [ANALYSIS_GETTER] Rendering analysis state")
    print(f"   Current state: {dialog_manager.current_stack()}")
    print(f"   Instagram URL: {data.get('instagram_url', 'NOT SET')}")
    print(f"   Strategy type: {data.get('strategy_type', 'NOT SET')}")
    print(f"   Has analysis: {'analysis' in data}")
    print(f"   Full dialog data keys: {list(data.keys())}")

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
        getter=analysis_getter,
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
        getter=analysis_getter,
    ),
)

# ==================== MESSAGE HANDLERS ====================
router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message, dialog_manager: DialogManager):
    """Start command - open main menu"""
    print(f"\n🔵 [START_HANDLER] /start command received")
    print(f"   User ID: {message.from_user.id}")
    print(f"   Username: {message.from_user.username}")
    await dialog_manager.start(MainMenuSG.MAIN)
    print(f"   ✅ Dialog started")


@router.message(Command("end"))
async def end_handler(message: types.Message, dialog_manager: DialogManager):
    """End command - close dialog"""
    print(f"\n🔵 [END_HANDLER] /end command received")
    print(f"   User ID: {message.from_user.id}")
    try:
        await dialog_manager.done()
        print(f"   ✅ Dialog closed")
    except Exception as e:
        print(f"   ⚠️ Error closing dialog: {e}")
        pass
    await message.answer("👋 Спасибо за использование FlirtAI! Используйте /start чтобы начать снова.")


@router.message(Command("price"))
async def price_handler(message: types.Message, dialog_manager: DialogManager):
    """Price command - show pricing (only outside analysis)"""
    print(f"\n🔵 [PRICE_HANDLER] /price command received")
    print(f"   User ID: {message.from_user.id}")
    try:
        current_state = dialog_manager.current_stack()
        print(f"   Current dialog stack: {current_state}")
        if current_state and len(current_state) > 0:
            # Already in analysis dialog
            print(f"   ⚠️ User in analysis dialog, denying price command")
            await message.answer("⚠️ Вы в процессе анализа. Используйте /end если хотите выйти.")
            return
    except Exception as e:
        print(f"   ⚠️ Error checking state: {e}")

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
    print(f"   ✅ Sending pricing info")
    await message.answer(pricing_text, parse_mode=ParseMode.HTML)
    await message.answer("Хотите начать анализ? Используйте /start")


# ==================== NEW: MAIN MENU TEXT HANDLER ====================
# INSERTED: Handle unexpected text while in main menu (following article pattern)
@router.message(MainMenuSG.MAIN, ~F.text.startswith("/"))
async def main_menu_unexpected_text(message: types.Message, dialog_manager: DialogManager):
    """
    Handle text input while in main menu state.
    Instead of editing old menu, send NEW message as per article recommendations.
    """
    print(f"\n⚠️ [MAIN_MENU_TEXT] Unexpected text received")
    print(f"   User ID: {message.from_user.id}")
    print(f"   Text: {message.text[:100]}")
    print(f"   Current state: {dialog_manager.current_stack()}")

    await message.answer(
        "ℹ️ Пожалуйста, используйте кнопки меню или доступные команды:\n\n"
        "/start - 🚀 Начать анализ\n"
        "/price - 💰 Узнать цену\n"
        "/end - 🛑 Завершить"
    )
    print(f"   ✅ Sent instructions")


# CRITICAL: Must have higher priority than dialog message handlers
@router.message(AnalysisSG.WAITING_FOR_LINK, ~F.text.startswith("/"))
async def link_input_handler(message: types.Message, dialog_manager: DialogManager):
    """Handle Instagram link input"""
    print(f"\n🔵 [LINK_HANDLER] Text input received")
    print(f"   User ID: {message.from_user.id}")
    print(f"   Text: {message.text[:100]}")

    if "instagram.com" not in message.text:
        print(f"   ❌ Invalid Instagram URL format")
        await message.answer("❌ Пожалуйста, отправь корректную ссылку на Instagram профиль.")
        return

    print(f"   ✅ Valid Instagram URL detected")

    # FIX: Update dialog_data and wait before switching state
    await dialog_manager.update_data(
        instagram_url=message.text,
        kaspi_number=KASPI_NUMBER,
        payment_amount=PAYMENT_AMOUNT
    )
    print(f"   💾 Stored in dialog_data: instagram_url={message.text[:50]}...")
    print(f"   📋 Updated data keys: {list(dialog_manager.dialog_data.keys())}")

    # FIX: Send confirmation message BEFORE switching state
    await message.answer(
        f"Спасибо! 🔁 Теперь переведи <b>{PAYMENT_AMOUNT}</b> на Kaspi: <code>{KASPI_NUMBER}</code>\n\n"
        "📎 После оплаты пришли фото чека.",
        parse_mode=ParseMode.HTML
    )
    print(f"   📤 Payment prompt sent")

    # FIX: Switch state AFTER sending message
    print(f"   📍 Switching state to WAITING_FOR_RECEIPT")
    await dialog_manager.switch_to(AnalysisSG.WAITING_FOR_RECEIPT)
    print(f"   ✅ State switched successfully")


# ==================== NEW: INVALID RECEIPT HANDLER ====================
# INSERTED: Handle non-photo/non-document content in receipt state
@router.message(AnalysisSG.WAITING_FOR_RECEIPT, ~F.content_type.in_(['photo', 'document']))
async def invalid_receipt_handler(message: types.Message, dialog_manager: DialogManager):
    """
    Handle invalid content type while waiting for receipt.
    Send NEW message instead of clearing old one (article pattern).
    """
    print(f"\n⚠️ [RECEIPT_INVALID] Invalid content type received")
    print(f"   User ID: {message.from_user.id}")
    print(f"   Content type: {message.content_type}")
    print(f"   Current state: {dialog_manager.current_stack()}")

    await message.answer(
        "❌ Пожалуйста, отправьте фото или документ чека.\n\n"
        "Принимаются форматы: фото (JPEG, PNG) или PDF"
    )
    print(f"   ✅ Sent error message with instructions")


@router.message(AnalysisSG.WAITING_FOR_RECEIPT, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: types.Message, dialog_manager: DialogManager):
    """Handle payment receipt"""
    print(f"\n🔵 [RECEIPT_HANDLER] Receipt received")
    print(f"   User ID: {message.from_user.id}")
    print(f"   Content type: {message.content_type}")

    await message.answer("⏳ Проверяю платёж...")

    try:
        # Download file
        print(f"   📥 Starting file download...")
        if message.photo:
            file_id = message.photo[-1].file_id
            print(f"      Photo file_id: {file_id[:20]}...")
        else:
            file_id = message.document.file_id
            print(f"      Document file_id: {file_id[:20]}...")

        file_info = await bot.get_file(file_id)
        print(f"      File path: {file_info.file_path}")

        file_bytes = await bot.download_file(file_info.file_path)

        file_bytes_io = BytesIO()
        file_bytes_io.write(file_bytes.read())
        file_data = file_bytes_io.getvalue()
        print(f"      ✅ Downloaded, size: {len(file_data)} bytes")

        # Verify receipt
        print(f"   🔍 Verifying receipt...")
        is_valid, verification_message = await verify_receipt_image(file_data, PAYMENT_AMOUNT)

        instagram_url = dialog_manager.dialog_data.get("instagram_url")
        print(f"      Retrieved from dialog_data: {instagram_url}")

        # Send to admin
        caption = f"💸 Новая заявка!\n🔗 {instagram_url}\n👤 @{message.from_user.username or message.from_user.id}"
        print(f"   📤 Forwarding to admin (ID: {ADMIN_ID})")

        if len(caption) <= 1000:
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)
            else:
                await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption)
            print(f"      ✅ Sent to admin")

        if is_valid:
            print(f"   ✅ Receipt validated - starting analysis")
            await message.answer(f"✅ {verification_message}\n\n🤖 Начинаю анализ профиля...")

            print(f"   🤖 Calling analyze_profile_with_ollama...")
            analysis = await analyze_profile_with_ollama(instagram_url)
            print(f"      Analysis result length: {len(analysis)} chars")

            # FIX: Use update_data instead of direct assignment
            await manager.update_data(analysis=analysis)
            print(f"      💾 Stored analysis in dialog_data using update_data()")
            print(f"      Updated data keys: {list(manager.dialog_data.keys())}")

            print(f"   📍 Switching to STRATEGY_SELECTION state")
            await manager.switch_to(AnalysisSG.STRATEGY_SELECTION)
            print(f"   ✅ State switched")

            # FIX: Send strategy selection message AFTER state switch
            await message.answer("👇 Теперь выбери один из трёх вариантов стратегии:")
            print(f"   ✅ Strategy selection prompt sent")
        else:
            print(f"   ⚠️ Receipt validation failed - sending to admin")
            await message.answer("🔍 Чек отправлен администратору для подтверждения. Ожидайте решения.")

    except Exception as e:
        print(f"   ❌ Exception: {type(e).__name__}: {e}")
        logging.error(f"Receipt handler error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(AnalysisSG.STRATEGY_SELECTION)
async def strategy_selected(callback: types.CallbackQuery, widget, manager: DialogManager, item_id: str):
    """Handle strategy selection"""
    print(f"\n🔵 [STRATEGY_SELECTED] Callback received")
    print(f"   User ID: {callback.from_user.id}")
    print(f"   Selected strategy: {item_id}")
    print(f"   Dialog data before update: {list(manager.dialog_data.keys())}")

    # FIX: Use update_data for proper persistence
    await manager.update_data(strategy_type=item_id)
    print(f"   Updated data with strategy_type")

    analysis = manager.dialog_data.get("analysis", "")

    print(f"   Analysis length: {len(analysis)} chars")
    print(f"   🔄 Generating strategy...")

    strategy = await generate_strategy(analysis, item_id)
    print(f"      Generated strategy length: {len(strategy)} chars")

    strategy_names = {
        "professional": "🧑‍💼 Профессиональная стратегия",
        "personal": "❤️ Личная стратегия",
        "trash": "🤪 Креативная стратегия"
    }

    print(f"   📤 Sending strategy to user")
    await callback.message.answer(f"<b>{strategy_names[item_id]}:</b>\n\n{strategy}")

    print(f"   📍 Moving to FEEDBACK state")
    await manager.next()
    await callback.message.answer("📊 Оцени результат от 1 до 10:", reply_markup=None)
    print(f"   ✅ Feedback prompt sent")


@router.callback_query(AnalysisSG.FEEDBACK)
async def rating_selected(callback: types.CallbackQuery, widget, manager: DialogManager, item_id: str):
    """Handle rating submission"""
    print(f"\n🔵 [FEEDBACK] Rating received")
    print(f"   User ID: {callback.from_user.id}")
    print(f"   Rating: {item_id}/10")

    try:
        print(f"   📤 Sending rating to admin...")
        await bot.send_message(ADMIN_ID, f"⭐ Новая оценка: {item_id}/10")
        print(f"      ✅ Sent to admin")
    except Exception as e:
        print(f"      ⚠️ Error sending to admin: {e}")

    print(f"   ✅ Closing dialog")
    await callback.message.answer(
        "✅ Спасибо за отзыв!\n\nИспользуйте /start чтобы начать заново или /price чтобы узнать цены."
    )
    await manager.done()
    print(f"   Dialog closed successfully")


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