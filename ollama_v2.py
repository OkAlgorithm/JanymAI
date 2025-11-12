import asyncio
import logging
import os
import requests
import base64
from io import BytesIO
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
KASPI_NUMBER = os.getenv("KASPI_NUMBER")
PAYMENT_AMOUNT = os.getenv("PAYMENT_AMOUNT")
KASPI_API_KEY = os.getenv("KASPI_API_KEY", "")
KASPI_MERCHANT_ID = os.getenv("KASPI_MERCHANT_ID", "")
USE_KASPI_API = os.getenv("USE_KASPI_API", "false").lower() == "true"

# Ollama settings
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL_LLAMA2 = os.getenv("OLLAMA_MODEL_LLAMA2", "llama2")
OLLAMA_MODEL_LLAVA = os.getenv("OLLAMA_MODEL_LLAVA", "llava")

# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Инициализация
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis FSM Storage - FIXED: Proper URL construction
redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
redis_storage = RedisStorage.from_url(redis_url)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=redis_storage)

PRICING_MESSAGE = """
💰 <b>Наша Цена:</b>

🔍 <b>Анализ Instagram профиля</b>
• Полный психологический анализ
• Определение типа личности
• Анализ интересов и ценностей
• Рекомендации по подходу

💵 <b>Стоимость:</b> {PAYMENT_AMOUNT} ₸

📊 <b>В пакет включено:</b>
✅ Анализ профиля
✅ 3 варианта стратегии (Профессиональная, Личная, Креативная)
✅ Персональные рекомендации

⏱️ <b>Время обработки:</b> 2-3 минуты

Начните с команды /start!
"""


# Состояния FSM
class AnalysisStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_receipt = State()
    waiting_for_strategy_choice = State()
    waiting_for_feedback = State()
    in_main_menu = State()


# ============ FSM HELPER FUNCTIONS ============

async def get_user_state_data(user_id: int, chat_id: int = None) -> dict:
    """
    Safely get user's FSM data from Redis

    Args:
        user_id: Telegram user ID
        chat_id: Optional chat ID (defaults to user_id for private chats)

    Returns:
        Dictionary with user data, empty dict if not found
    """
    try:
        chat_id = chat_id or user_id
        # Correct key format for aiogram 3.x
        from aiogram.fsm.storage.base import StorageKey
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id)

        data = await redis_storage.get_data(key=key)
        return data if data else {}
    except Exception as e:
        logger.error(f"Error getting FSM data for user {user_id}: {e}")
        return {}


async def update_user_state_data(user_id: int, data: dict, chat_id: int = None) -> bool:
    """
    Safely update user's FSM data in Redis

    Args:
        user_id: Telegram user ID
        data: Dictionary with data to save
        chat_id: Optional chat ID (defaults to user_id for private chats)

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        from aiogram.fsm.storage.base import StorageKey
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id)

        await redis_storage.set_data(key=key, data=data)
        return True
    except Exception as e:
        logger.error(f"Error updating FSM data for user {user_id}: {e}")
        return False


async def set_user_state(user_id: int, state: State, chat_id: int = None) -> bool:
    """
    Safely set user's FSM state in Redis

    Args:
        user_id: Telegram user ID
        state: FSM State to set
        chat_id: Optional chat ID (defaults to user_id for private chats)

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        from aiogram.fsm.storage.base import StorageKey
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id)

        await redis_storage.set_state(key=key, state=state)
        return True
    except Exception as e:
        logger.error(f"Error setting FSM state for user {user_id}: {e}")
        return False


async def clear_user_state(user_id: int, chat_id: int = None) -> bool:
    """
    Safely clear user's FSM state and data in Redis

    Args:
        user_id: Telegram user ID
        chat_id: Optional chat ID (defaults to user_id for private chats)

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        from aiogram.fsm.storage.base import StorageKey
        key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id)

        await redis_storage.set_state(key=key, state=None)
        await redis_storage.set_data(key=key, data={})
        return True
    except Exception as e:
        logger.error(f"Error clearing FSM state for user {user_id}: {e}")
        return False


# Клавиатуры
def get_main_menu_keyboard():
    """Main menu keyboard shown before /start is used"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать анализ", callback_data="main_start")],
        [InlineKeyboardButton(text="💰 Узнать цену", callback_data="main_price")],
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


def get_strategy_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💼 Профессиональное", callback_data="strategy_professional")],
        [InlineKeyboardButton(text="❤️ Личное", callback_data="strategy_personal")],
        [InlineKeyboardButton(text="🤪 Трешовое", callback_data="strategy_trash")]
    ])
    return keyboard


def get_admin_receipt_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard sent to admin to approve / request resend for a specific user's receipt."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобряю", callback_data=f"receipt_is_valid:{user_id}")],
        [InlineKeyboardButton(text="🔁 Повторно отправить чек", callback_data=f"receipt_is_not_valid:{user_id}")]
    ])


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


def call_ollama(
        messages: list,
        model: str = None,
        max_tokens: int = 3000,
        temperature: float = 0.7,
        **extra_payload
) -> str:
    """
    Call local Ollama API with flexible payload support

    Args:
        messages: List of message dicts with role & content
        model: Model name (defaults to OLLAMA_MODEL_LLAMA2)
        max_tokens: Maximum tokens in response
        temperature: Temperature for generation (0.0-1.0)
        **extra_payload: Additional fields for the API request

    Returns:
        Model response text or error message
    """
    model = model or OLLAMA_MODEL_LLAMA2

    try:
        logger.info(f"🤖 Testing connection to Ollama at {OLLAMA_API_URL}...")
        try:
            health_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            logger.info("✅ Ollama is reachable")
        except Exception as e:
            logger.error(f"⚠️ Cannot reach Ollama at {OLLAMA_API_URL}: {e}")
            return "Error: Ollama service not available. Make sure it's running with 'ollama serve'"

        logger.info(f"→ Sending request to model: {model}")

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "num_predict": max_tokens,
            **extra_payload
        }

        response = requests.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=300
        )

        logger.info(f"→ Response status: {response.status_code}")

        if response.status_code == 404:
            error_msg = f"Model '{model}' not found! Run: ollama pull {model}"
            logger.error(f"❌ {error_msg}")
            return f"Error: {error_msg}"

        response.raise_for_status()

        result = response.json()
        content = result.get("message", {}).get("content", "")
        logger.info(f"✅ Response received ({len(content)} chars)")
        return content

    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Cannot connect to Ollama: {e}")
        return "Error: Ollama service not available."
    except requests.exceptions.Timeout:
        logger.error("❌ Ollama request timeout")
        return "Error: Ollama response timeout."
    except Exception as e:
        logger.error(f"❌ Ollama API error: {e}")
        return f"Error: {str(e)}"


async def verify_payment_kaspi(amount: str, user_phone: str) -> tuple[bool, str]:
    """
    Verify payment using Kaspi API
    Returns: (is_verified, message)
    """
    if not KASPI_API_KEY or not KASPI_MERCHANT_ID:
        return False, "Kaspi API credentials not configured"

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {KASPI_API_KEY}",
                "Content-Type": "application/json"
            }

            url = "https://api.kaspi.kz/v2/merchant/transactions"
            params = {
                "merchant_id": KASPI_MERCHANT_ID,
                "limit": 10
            }

            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    transactions = data.get("transactions", [])

                    for tx in transactions:
                        tx_amount = str(tx.get("amount", ""))
                        tx_status = tx.get("status", "").lower()

                        if amount in tx_amount and "completed" in tx_status:
                            return True, f"✅ Payment verified! Transaction: {tx.get('id')}"

                    return False, "❌ No matching completed payment found"
                else:
                    return False, f"❌ Kaspi API error: {resp.status}"

    except asyncio.TimeoutError:
        return False, "❌ Kaspi API timeout"
    except Exception as e:
        logger.error(f"Kaspi API error: {e}")
        return False, f"❌ Payment verification error: {str(e)}"


async def verify_receipt_image(file_bytes: bytes, expected_amount: str) -> tuple[bool, str]:
    """
    Verify receipt image using Ollama vision (requires vision model like llava)
    Returns: (is_valid, message)
    """
    try:
        image_base64 = base64.b64encode(file_bytes).decode('utf-8')

        system_prompt = """
        You are an expert at verifying payment receipts.
        Analyze the receipt and extract: amount, merchant, status, date.
        Respond in JSON: {"amount": "...", "status": "...", "is_valid": true/false}
        """

        messages = [
            {
                "role": "user",
                "content": f"Verify this receipt. Expected amount: {expected_amount}",
                "images": [image_base64]
            }
        ]

        response = requests.post(
            f"{OLLAMA_API_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL_LLAVA,
                "messages": messages,
                "stream": False,
                "max_tokens": 200
            },
            timeout=60
        )

        logger.info(f"LLAVA response: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            receipt_info = result.get("message", {}).get("content", "")

            if "is_valid" in receipt_info and "true" in receipt_info.lower():
                return True, f"✅ Receipt verified!"
            else:
                return False, f"❌ Receipt validation failed"
        else:
            return False, "❌ Could not process receipt image"

    except Exception as e:
        logger.error(f"Receipt verification error: {e}")
        return False, f"❌ Receipt verification error"


async def simple_receipt_check(file_bytes: bytes) -> tuple[bool, str]:
    """
    Simple receipt check - verify it's a valid image
    Returns: (is_valid, message)
    """
    try:
        file_size_mb = len(file_bytes) / (1024 * 1024)

        if file_size_mb > 50:
            return False, "❌ File too large (max 50MB)"

        if file_size_mb < 0.01:
            return False, "❌ File too small"

        try:
            from PIL import Image
            img = Image.open(BytesIO(file_bytes))
            width, height = img.size

            if width < 200 or height < 200:
                return False, "❌ Image too small"

            return True, f"✅ Receipt verified ({width}x{height})"
        except:
            return True, "✅ Receipt file verified"

    except Exception as e:
        logger.error(f"Receipt check error: {e}")
        return False, f"❌ File verification error"


async def analyze_profile_with_ollama(profile_url: str) -> str:
    """Анализирует Instagram профиль используя Ollama"""
    try:
        logger.info(f"🤖 Analyzing Instagram profile: {profile_url}")
        username = profile_url.split('/')[-1].split('?')[0]
        logger.info(f"→ Username: {username}")

        system_prompt = """
            🟢 ТВОЯ ЗАДАЧА:
            Получив ссылку на Instagram-профиль, ты должен провести максимально глубокий и профессиональный анализ человека и сформулировать чёткую стратегию взаимодействия.
            
            📌 ОБЯЗАТЕЛЬНЫЕ ШАГИ АНАЛИЗА:
            1️⃣ ПРОФИЛЬ: Фото (стиль, образы, позы), хайлайты, интересы, места, характер
            2️⃣ ПОДПИСКИ: На какие аккаунты подписан (тематика, бренды)
            3️⃣ КОММЕНТАРИИ: Стиль общения, открытость к диалогу
            4️⃣ КРУГ КОНТАКТОВ: Кто в близком круге
            5️⃣ ФИЗИОГНОМИКА: Эмоциональная подача, открытость
            6️⃣ ЦЕННОСТИ: Что транслирует (семья, карьера, свобода)
            
            🎯 СТРАТЕГИЯ ВЗАИМОДЕЙСТВИЯ:
            - Как начать общение (первое сообщение)
            - Как развивать диалог (ключевые темы, крючки)
            - Как перейти в личный мессенджер
            - Как предложить встречу
            
            ✅ ТРЕБОВАНИЯ:
            - Учитывай личные интересы
            - Избегай шаблонных фраз
            - Дай конкретные примеры формулировок
            - Живой, человеческий язык
            """

        user_message = f"Проанализируй Instagram профиль: {profile_url}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        logger.info("→ Calling Ollama for analysis...")
        analysis = call_ollama(messages, max_tokens=2000)

        if analysis.startswith("Error:"):
            logger.error(f"Analysis failed: {analysis}")
            return "Извините, произошла ошибка при анализе профиля."

        logger.info(f"✅ Analysis completed ({len(analysis)} characters)")
        return analysis

    except Exception as e:
        logger.error(f"❌ Error analyzing profile: {e}")
        return "Извините, произошла ошибка при анализе профиля."


async def generate_strategy(analysis: str, strategy_type: str) -> str:
    """Генерирует стратегию знакомства на основе анализа"""
    try:
        strategy_prompts = {
            "professional": "Создай профессиональную стратегию знакомства для деловых целей",
            "personal": "Создай личную романтическую стратегию знакомства",
            "trash": "Создай креативную и необычную стратегию знакомства"
        }

        prompt = f"""
Анализ: {analysis}

На основе анализа личности создай {strategy_prompts.get(strategy_type, 'персональную')} стратегию.
Включи конкретные примеры сообщений и тактики взаимодействия.
"""

        messages = [{"role": "user", "content": prompt}]
        strategy = call_ollama(messages, max_tokens=1000)

        logger.info("Strategy generation complete")
        return strategy if not strategy.startswith("Error:") else "Ошибка при создании стратегии."

    except Exception as e:
        logger.error(f"Error generating strategy: {e}")
        return "Ошибка при создании стратегии."


def truncate_caption(caption: str, max_length: int = 1000) -> str:
    """Truncate caption to Telegram's limit"""
    if len(caption) <= max_length:
        return caption
    return caption[:max_length - 3] + "..."


# ============ HANDLERS ============

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()

    await message.answer(
        "👋 Привет! Добро пожаловать в FlirtAI!\n\n"
        "Я помогу тебе проанализировать Instagram профиль и получить персональную стратегию знакомства.",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(AnalysisStates.in_main_menu)


@dp.message(F.text == "/end")
async def end_command_handler(message: types.Message, state: FSMContext):
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


@dp.message(F.text == "/price")
async def price_command_handler(message: types.Message, state: FSMContext):
    """Handle /price command"""
    pricing_text = PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", PAYMENT_AMOUNT)
    await message.answer(pricing_text, parse_mode=ParseMode.HTML)


@dp.message(AnalysisStates.waiting_for_link)
async def link_handler(message: types.Message, state: FSMContext):
    """Handle Instagram link submission"""
    instagram_url = message.text

    if "instagram.com" not in instagram_url:
        await message.answer("❌ Пожалуйста, отправь корректную ссылку на Instagram профиль.")
        return

    await state.update_data(instagram_url=instagram_url)
    await message.answer(
        f"Спасибо! 🔁 Теперь переведи **{PAYMENT_AMOUNT}** на Kaspi: `{KASPI_NUMBER}`\n\n"
        "📎 После оплаты пришли PDF или фото чека.",
        parse_mode=ParseMode.MARKDOWN
    )
    await state.set_state(AnalysisStates.waiting_for_receipt)


@dp.message(AnalysisStates.waiting_for_receipt, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: types.Message, state: FSMContext):
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
            file_info = await bot.get_file(file_id)
            file = await bot.download_file(file_info.file_path)
            file_data = file.read()
        elif message.document:
            file_id = message.document.file_id
            file_info = await bot.get_file(file_id)
            file = await bot.download_file(file_info.file_path)
            file_data = file.read()
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или PDF документа.")
            return

        # Verify payment
        is_valid = False
        verification_message = ""

        if USE_KASPI_API:
            logger.info("🔍 Verifying payment with Kaspi API...")
            is_valid, verification_message = await verify_payment_kaspi(
                PAYMENT_AMOUNT,
                message.from_user.username or ""
            )
        else:
            logger.info("🔍 Verifying receipt image...")
            is_valid, verification_message = await verify_receipt_image(file_data, PAYMENT_AMOUNT)

            if not is_valid and "vision" in verification_message.lower():
                logger.info("⚠️ Using simple verification...")
                is_valid, verification_message = await simple_receipt_check(file_data)

        # Send to admin
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
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
            else:
                await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error sending to admin: {e}")
            simple_caption = f"💸 Новая заявка!\n🔗 {instagram_url}\n👤 @{message.from_user.username or message.from_user.id}"
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=simple_caption, reply_markup=keyboard)
            else:
                await bot.send_document(ADMIN_ID, message.document.file_id, caption=simple_caption,
                                        reply_markup=keyboard)

        if not is_valid:
            await message.answer("🔍 Чек отправлен администратору для подтверждения. Ожидайте решения.")
        else:
            await message.answer(f"✅ {verification_message}\n\n🤖 Начинаю анализ профиля...")
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

            await state.update_data(analysis=analysis)
            await state.set_state(AnalysisStates.waiting_for_strategy_choice)

    except Exception as e:
        logger.error(f"Receipt handler error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}\n\nПопробуйте ещё раз.")


# ============ CALLBACK HANDLERS ============

@dp.callback_query(F.data == "main_start")
async def main_start_callback(callback: types.CallbackQuery, state: FSMContext):
    """Start analysis from main menu"""
    await callback.message.edit_text(
        "👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать.",
        reply_markup=None
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()


@dp.callback_query(F.data == "main_price")
async def main_price_callback(callback: types.CallbackQuery, state: FSMContext):
    """Show pricing"""
    pricing_text = PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", PAYMENT_AMOUNT)
    await callback.message.answer(pricing_text, parse_mode=ParseMode.HTML)
    await callback.answer()


@dp.callback_query(F.data == "main_end")
async def main_end_callback(callback: types.CallbackQuery, state: FSMContext):
    """Ask for exit confirmation"""
    await callback.message.edit_text(
        "⚠️ Вы уверены?",
        reply_markup=get_exit_confirmation_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "confirm_end")
async def confirm_end_callback(callback: types.CallbackQuery, state: FSMContext):
    """Confirm end"""
    await callback.message.edit_text(
        "👋 Спасибо за использование FlirtAI!\n\nИспользуйте /start чтобы начать снова."
    )
    await state.clear()
    await callback.answer("✅ Анализ завершен.")


@dp.callback_query(F.data == "cancel_end")
async def cancel_end_callback(callback: types.CallbackQuery, state: FSMContext):
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


@dp.callback_query(F.data.startswith("receipt_is_valid:"))
async def handle_receipt_approve(callback: types.CallbackQuery):
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
        await bot.send_message(user_id, "✅ Ваш чек одобрен! Начинаю анализ профиля...")

        # Get user data using helper function
        user_data = await get_user_state_data(user_id)
        instagram_url = user_data.get('instagram_url')

        if not instagram_url:
            await bot.send_message(user_id, "❌ Ссылка на профиль не найдена. Начните с /start")
            logger.warning(f"No instagram_url found for user {user_id}")
            return

        # Analyze profile
        logger.info(f"🤖 Starting analysis for user {user_id}")
        analysis = await analyze_profile_with_ollama(instagram_url)

        # Send analysis
        await bot.send_message(
            user_id,
            f"<b>📊 Анализ профиля:</b>\n\n{truncate_caption(analysis, 4096)}",
            parse_mode=ParseMode.HTML
        )

        # Send strategy options
        await bot.send_message(
            user_id,
            "👇 Теперь выбери один из трёх вариантов стратегии:",
            reply_markup=get_strategy_keyboard()
        )

        # Update FSM state and data using helper functions
        updated_data = {
            'instagram_url': instagram_url,
            'analysis': analysis
        }

        success_data = await update_user_state_data(user_id, updated_data)
        success_state = await set_user_state(user_id, AnalysisStates.waiting_for_strategy_choice)

        if success_data and success_state:
            logger.info(f"✅ Analysis data and state saved for user {user_id}")
        else:
            logger.warning(f"⚠️ Failed to save FSM data for user {user_id}")

    except Exception as e:
        logger.error(f"Error in receipt approval: {e}", exc_info=True)
        try:
            await bot.send_message(
                user_id,
                f"❌ Произошла ошибка при обработке вашего запроса. Попробуйте начать заново с /start"
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {user_id}: {send_error}")


@dp.callback_query(F.data.startswith("receipt_is_not_valid:"))
async def handle_receipt_reject(callback: types.CallbackQuery):
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
        await bot.send_message(
            user_id,
            "🔁 Администратор запросил повторную отправку чека. "
            "Пожалуйста, пришлите корректный чек."
        )

        # Set state back to waiting for receipt using helper function
        success = await set_user_state(user_id, AnalysisStates.waiting_for_receipt)

        if success:
            logger.info(f"✅ User {user_id} state reset to waiting_for_receipt")
        else:
            logger.warning(f"⚠️ Failed to reset state for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}", exc_info=True)


@dp.callback_query(F.data.startswith("strategy_"))
async def strategy_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handle strategy selection"""
    strategy_type = callback.data.split("_")[1]
    data = await state.get_data()
    analysis = data.get('analysis')

    if not analysis:
        await callback.answer("❌ Анализ не найден.", show_alert=True)
        logger.warning(f"Analysis not found for user {callback.from_user.id}")
        return

    await callback.message.edit_text("🤖 Генерирую персональную стратегию...")

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
    await callback.message.answer(
        "📊 Оцени результат от 1 до 10:",
        reply_markup=get_rating_keyboard()
    )

    await state.set_state(AnalysisStates.waiting_for_feedback)
    await callback.answer()


@dp.callback_query(F.data.startswith("rating_"))
async def rating_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handle rating"""
    rating = callback.data.split("_")[1]

    await callback.message.edit_text(f"⭐ Спасибо за оценку: {rating}/10")

    await callback.message.answer(
        "🗣 Можешь оставить комментарий или нажать кнопку ниже:",
        reply_markup=get_restart_keyboard()
    )

    # Send rating to admin
    try:
        await bot.send_message(
            ADMIN_ID,
            f"⭐ Новая оценка от @{callback.from_user.username or callback.from_user.id}: {rating}/10"
        )
    except Exception as e:
        logger.error(f"Failed to send rating to admin: {e}")

    await callback.answer()


@dp.callback_query(F.data == "restart")
async def restart_handler(callback: types.CallbackQuery, state: FSMContext):
    """Restart analysis"""
    await state.clear()
    await callback.message.answer(
        "👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать."
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()


@dp.message(AnalysisStates.waiting_for_feedback)
async def feedback_handler(message: types.Message, state: FSMContext):
    """Handle feedback"""
    feedback = message.text

    # Send feedback to admin
    try:
        await bot.send_message(
            ADMIN_ID,
            f"💬 Новый отзыв от @{message.from_user.username or message.from_user.id}:\n{feedback}"
        )
    except Exception as e:
        logger.error(f"Failed to send feedback to admin: {e}")

    await message.answer(
        "✅ Спасибо за отзыв!",
        reply_markup=get_restart_keyboard()
    )


# ============ ERROR HANDLER ============

@dp.error()
async def error_handler(event, exception):
    """
    Global error handler for the bot
    """
    logger.error(f"❌ Error occurred: {exception}", exc_info=True)

    # Try to notify user if possible
    if hasattr(event, 'update') and event.update:
        try:
            if event.update.message:
                await event.update.message.answer(
                    "❌ Произошла ошибка. Попробуйте начать заново с /start"
                )
            elif event.update.callback_query:
                await event.update.callback_query.message.answer(
                    "❌ Произошла ошибка. Попробуйте начать заново с /start"
                )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

    return True  # Mark as handled


# ============ BOT STARTUP ============

async def on_startup():
    """Actions on bot startup"""
    logger.info("🚀 Starting FlirtAI bot...")

    # Test Redis connection
    try:
        from aiogram.fsm.storage.base import StorageKey
        test_key = StorageKey(bot_id=bot.id, chat_id=0, user_id=0)
        await redis_storage.set_data(key=test_key, data={"test": "connection"})
        await redis_storage.get_data(key=test_key)
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise

    # Test Ollama connection
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Ollama connection successful")
        else:
            logger.warning(f"⚠️ Ollama returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Ollama connection failed: {e}")

    logger.info(f"✅ Bot started successfully")
    logger.info(f"📊 Admin ID: {ADMIN_ID}")
    logger.info(f"💰 Payment amount: {PAYMENT_AMOUNT} ₸")
    logger.info(f"🔑 Kaspi API enabled: {USE_KASPI_API}")


async def on_shutdown():
    """Actions on bot shutdown"""
    logger.info("🛑 Shutting down bot...")

    # Close Redis connection
    try:
        await redis_storage.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")

    # Close bot session
    try:
        await bot.session.close()
        logger.info("✅ Bot session closed")
    except Exception as e:
        logger.error(f"❌ Error closing bot session: {e}")


async def main():
    """Start the bot"""
    try:
        await on_startup()
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True  # Skip pending updates on restart
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}", exc_info=True)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())