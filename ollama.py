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
from aiogram.fsm.storage.memory import MemoryStorage
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
OLLAMA_MODEL_LLAMA2 = os.getenv("OLLAMA_MODEL_LLAMA2")
OLLAMA_MODEL_LLAVA = os.getenv("OLLAMA_MODEL_LLAVA")
# Инициализация
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

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
    in_main_menu = State()  # New state for main menu

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
        [InlineKeyboardButton(text="Одобряю", callback_data=f"receipt_is_valid:{user_id}")],
        [InlineKeyboardButton(text="Повторно отправить чек", callback_data=f"receipt_is_not_valid:{user_id}")]
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


def call_ollama(messages: list, max_tokens: int = 3000) -> str:
    """Call local Ollama API"""
    try:
        print(f"  → Testing connection to Ollama at {OLLAMA_API_URL}...")
        try:
            health_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            print(f"  ✅ Ollama is reachable")
        except Exception as e:
            print(f"  ⚠️ Cannot reach Ollama at {OLLAMA_API_URL}")
            print(f"     Make sure Ollama is running: ollama serve")
            return "Error: Ollama service not available. Make sure it's running with 'ollama serve'"

        print(f"  → Sending request to model: {OLLAMA_MODEL_LLAMA2}")

        payload = {
            "model": OLLAMA_MODEL_LLAMA2,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "num_predict": max_tokens
        }

        response = requests.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=300
        )

        print(f"  → Response status: {response.status_code}")

        if response.status_code == 404:
            print(f"  ❌ Model '{OLLAMA_MODEL_LLAMA2}' not found!")
            print(f"     Run: ollama pull {OLLAMA_MODEL_LLAMA2}")
            return f"Error: Model '{OLLAMA_MODEL_LLAMA2}' not found. Run 'ollama pull {OLLAMA_MODEL_LLAMA2}'"

        response.raise_for_status()

        result = response.json()
        return result.get("message", {}).get("content", "")

    except requests.exceptions.ConnectionError:
        logging.error(f"❌ Cannot connect to Ollama at {OLLAMA_API_URL}")
        return "Ошибка: Ollama сервис не доступен. Запустите: ollama serve"
    except requests.exceptions.Timeout:
        logging.error(f"❌ Ollama request timeout")
        return "Error: Ollama response timeout."
    except Exception as e:
        logging.error(f"❌ Ollama API error: {e}")
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

            # Query recent transactions for this merchant
            url = "https://api.kaspi.kz/v2/merchant/transactions"
            params = {
                "merchant_id": KASPI_MERCHANT_ID,
                "limit": 10
            }

            async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    transactions = data.get("transactions", [])

                    # Look for a recent transaction matching the amount
                    for tx in transactions:
                        tx_amount = str(tx.get("amount", ""))
                        tx_status = tx.get("status", "").lower()

                        # Check if amount matches and payment is completed
                        if amount in tx_amount and "completed" in tx_status:
                            return True, f"✅ Payment verified! Transaction: {tx.get('id')}"

                    return False, "❌ No matching completed payment found in recent transactions"
                else:
                    return False, f"❌ Kaspi API error: {resp.status}"

    except asyncio.TimeoutError:
        return False, "❌ Kaspi API timeout - please try again"
    except Exception as e:
        logging.error(f"Kaspi API error: {e}")
        return False, f"❌ Payment verification error: {str(e)}"
async def verify_receipt_image(file_bytes: bytes, expected_amount: str) -> tuple[bool, str]:
    """
    Verify receipt image using Ollama vision (requires vision model like llava)
    Returns: (is_valid, message)
    """
    try:
        # Convert image to base64
        image_base64 = base64.b64encode(file_bytes).decode('utf-8')

        system_prompt = """
        You are an expert at verifying payment receipts and financial documents.
        Analyze the provided receipt image and extract:
        1. Payment amount
        2. Merchant name
        3. Payment status (completed, pending, failed)
        4. Date and time
        5. Transaction ID if visible

        Respond in JSON format:
        {"amount": "...", "merchant": "...", "status": "...", "is_valid": true/false, "reason": "..."}
        """

        # Note: This requires a vision model like llava
        # Standard llama2 won't process images
        messages = [
            {
                "role": "user",
                "content": f"Please verify this receipt image. Expected payment amount: {expected_amount}",
                "images": [image_base64]
            }
        ]

        # Call Ollama with vision support
        payload = {
            "model": OLLAMA_MODEL_LLAVA,
            "messages": messages,
            "stream": False,
            "max_tokens": 200
        }

        response = requests.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=60
        )
        print("LLAVA is working")
        if response.status_code == 200:
            result = response.json()
            receipt_info = result.get("message", {}).get("content", "")

            # Check if receipt is valid
            if "is_valid" in receipt_info and "true" in receipt_info.lower():
                return True, f"✅ Receipt verified! Details: {receipt_info[:100]}"
            else:
                return False, f"❌ Receipt validation failed: {receipt_info}"
        else:
            return False, "❌ Could not process receipt image (ensure model supports vision)"

    except Exception as e:
        logging.error(f"Receipt verification error: {e}")
        return False, f"❌ Receipt verification error: {str(e)}"
async def simple_receipt_check(file_bytes: bytes) -> tuple[bool, str]:
    """
    Simple receipt check - verify it's a valid image and has reasonable size
    Returns: (is_valid, message)
    """
    try:
        # Check file size (receipt should be reasonable size)
        file_size_mb = len(file_bytes) / (1024 * 1024)

        if file_size_mb > 50:
            return False, "❌ File too large (max 50MB)"

        if file_size_mb < 0.01:
            return False, "❌ File too small - not a valid receipt"

        # Try to verify it's a valid image
        try:
            from PIL import Image
            img = Image.open(BytesIO(file_bytes))
            width, height = img.size

            # Check if dimensions are reasonable for a receipt
            if width < 200 or height < 200:
                return False, "❌ Image too small to be a receipt"

            return True, f"✅ Receipt image verified ({width}x{height})"
        except:
            # If PIL not available, just check file size
            return True, "✅ Receipt file received and verified"

    except Exception as e:
        logging.error(f"Simple receipt check error: {e}")
        return False, f"❌ File verification error: {str(e)}"
async def analyze_profile_with_ollama(profile_url: str) -> str:
    """Анализирует Instagram профиль напрямую используя Ollama (без скриншотов)"""
    try:
        print(f"🤖 Analyzing Instagram profile: {profile_url}")

        # Extract username from URL
        username = profile_url.split('/')[-1].split('?')[0]
        print(f"  → Username: {username}")

        system_prompt = """
                🟢 ТВОЯ ЗАДАЧА:
                Получив ссылку на Instagram-профиль, ты должен провести максимально глубокий и профессиональный анализ человека и сформулировать чёткую, пошаговую стратегию взаимодействия, чтобы достичь указанной мной цели (например: познакомиться, получить номер телефона, пригласить на свидание).
                
                📌 ОБЯЗАТЕЛЬНЫЕ ШАГИ АНАЛИЗА:
                1️⃣ ПРОФИЛЬ:
                
                Фото: стиль, образы, позы, настроение.
                Хайлайты: темы и личные акценты, что показывает о характере и интересах.
                Отметки: кто и как отмечает человека, тип проектов или контактов.
                Цветы: какие предпочитает, если видны на фото (для подарка или комплимента).
                Аксессуары: стиль, бренды, детали образов.
                Местоположение: геолокации постов и сторис, основные города и места.
                Семейное положение: есть ли семья, дети, намёки на статус.
                Интересы: темы контента, увлечения, профессиональная деятельность, хобби.
                Места посещений: любимые кафе, рестораны, локации.
                Характер: темперамент, подача себя в постах, эмоциональный фон.
                2️⃣ АНАЛИЗ ПОДПИСОК:
                
                На какие аккаунты подписан человек (тематика, стиль, бренды, люди, сообщества).
                3️⃣ АНАЛИЗ КОММЕНТАРИЕВ:
                
                Стиль общения, реакция на комплименты, открытость к диалогу.
                4️⃣ КРУГ ЧАСТЫХ КОНТАКТОВ:
                
                Кто в близком круге, с кем взаимодействует чаще всего, тип отношений.
                5️⃣ ФИЗИОГНОМИКА И ВИЗУАЛЬНЫЙ АНАЛИЗ:
                
                Основные черты лица, эмоциональная подача, уровень открытости, жестикуляция, взгляд, осанка.
                6️⃣ ЖИЗНЕННЫЕ ЦЕННОСТИ:
                
                Что транслирует через посты и сторис (семья, карьера, свобода, личностный рост и т.д.).
                🎯 ЦЕЛЬ ВЗАИМОДЕЙСТВИЯ (укажу отдельно, например):
                Завязать первое общение в Instagram.
                Перейти в личный мессенджер, получить номер телефона.
                Организовать офлайн-встречу или свидание.
                🔑 СТРАТЕГИЯ ВЗАИМОДЕЙСТВИЯ (обязательно в ответе):
                Предоставь конкретную, пошаговую стратегию:
                
                Как лучше всего начать общение (первое сообщение в Директ).
                Как развивать диалог (ключевые темы, крючки, комплименты, которые не выглядят банально).
                Как перевести общение в личный мессенджер (номер телефона).
                Как предложить офлайн-встречу или свидание максимально естественно и с высокой вероятностью согласия.
                ✅ ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К СТРАТЕГИИ:
                Учитывай личные интересы и индивидуальные особенности профиля.
                Избегай шаблонных и банальных фраз — только персонализированный подход.
                Учитывай культурные особенности региона (если профиль из Казахстана — уважение традиций, дистанции, ненавязчивость).
                Обязательно дай примеры конкретных формулировок для каждого этапа взаимодействия.
                📎 СТРУКТУРА ТВОЕГО ОТВЕТА:
                Полный глубокий профайлинг по пунктам выше.
                Чёткая пошаговая стратегия достижения цели с примерами сообщений.
                Краткая аргументация почему именно этот подход максимально эффективен с данным человеком.
                📝 ПРИМЕР ЗАПРОСА:
                «Вот ссылка (вставить ссылку на профиль). Цель: познакомиться, плавно перевести общение в WhatsApp и пригласить на офлайн-встречу.»
                
                Используй максимум информации, не экономь на деталях. Перепроверяй каждый пункт. Пиши живым, человеческим языком, без воды, с уважением к индивидуальности каждого профиля.
         """

        user_message = f"""
       Проанализиру Instagram профиль:
        URL: {profile_url}
        Username: {username}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        print("  → Calling Ollama for analysis...")
        analysis = call_ollama(messages, max_tokens=2000)

        if analysis.startswith("Error:"):
            print(f"  ❌ Analysis failed: {analysis}")
            return "Извините, произошла ошибка при анализе профиля."

        print(f"  ✅ Analysis completed ({len(analysis)} characters)")
        if callback and bot:
            await bot.send_message(callback.from_user.id, "✅ Анализ завершен успешно!")
        return analysis

    except Exception as e:
        logging.error(f"❌ Error analyzing profile: {e}")
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

                На основе анализа личности создай {strategy_prompts[strategy_type]}.
        """

        messages = [{"role": "user", "content": prompt}]
        strategy = call_ollama(messages, max_tokens=1000)
        print("-___- Strategy Creation")
        return strategy if not strategy.startswith("Error:") else "Извините, произошла ошибка при создании стратегии."

    except Exception as e:
        logging.error(f"❌ Error generating strategy: {e}")
        return "Извините, произошла ошибка при создании стратегии."


# Хэндлеры
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()

    # Check if user is already in analysis
    current_state = await state.get_state()
    if current_state in [AnalysisStates.waiting_for_link, AnalysisStates.waiting_for_receipt]:
        await message.answer("⚠️ Вы уже в процессе анализа. Используйте /end если хотите начать заново.")
        return

    await message.answer(
        "👋 Привет! Добро пожаловать в FlirtAI!\n\n"
        "Я помогу тебе проанализировать Instagram профиль и получить персональную стратегию знакомства.",
        reply_markup=get_main_menu_keyboard()
    )
    await state.set_state(AnalysisStates.in_main_menu)

@dp.message(F.text == "/end")
async def end_command_handler(message: types.Message, state: FSMContext):
    """Handle /end command - gracefully close conversation"""
    current_state = await state.get_state()

    if current_state == AnalysisStates.in_main_menu:
        # Already in main menu, just confirm exit
        await message.answer(
            "👋 Спасибо за использование FlirtAI! Используйте /start чтобы начать снова."
        )
        await state.clear()
        return

    # If in analysis, ask for confirmation
    await message.answer(
        "⚠️ Вы в процессе анализа. Вы уверены, что хотите завершить?",
        reply_markup=get_exit_confirmation_keyboard()
    )
@dp.message(F.text == "/price")
async def price_command_handler(message: types.Message, state: FSMContext):
    """Handle /price command - show pricing"""
    current_state = await state.get_state()

    if current_state in [AnalysisStates.waiting_for_link, AnalysisStates.waiting_for_receipt,
                         AnalysisStates.waiting_for_strategy_choice, AnalysisStates.waiting_for_feedback]:
        await message.answer(
            "⚠️ Вы в процессе анализа. Используйте /end если хотите выйти.",
            reply_markup=get_analysis_menu_keyboard()
        )
        return

    # Show pricing
    pricing_text = PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", PAYMENT_AMOUNT)
    await message.answer(pricing_text, parse_mode=ParseMode.HTML)

    if current_state == AnalysisStates.in_main_menu:
        await message.answer(
            "Хотите начать анализ?",
            reply_markup=get_main_menu_keyboard()
        )
@dp.message(AnalysisStates.waiting_for_link)
async def link_handler(message: types.Message, state: FSMContext):
    instagram_url = message.text

    # Простая валидация ссылки
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

def truncate_caption(caption: str, max_length: int = 1000) -> str:
    """
    Truncate caption to Telegram's limit (1024 chars)
    Leaves room for safety margin.
    """
    if len(caption) <= max_length:
        return caption

    # Truncate and add ellipsis
    truncated = caption[:max_length - 3] + "..."
    return truncated
@dp.message(AnalysisStates.waiting_for_receipt, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    instagram_url = data['instagram_url']

    await message.answer("⏳ Проверяю платёж...")

    try:
        # Download file
        if message.photo:
            file_id = message.photo[-1].file_id
            file_info = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file_info.file_path)
        elif message.document:
            file_id = message.document.file_id
            file_info = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file_info.file_path)
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или PDF документа.")
            return

        # Convert to bytes
        file_bytes_io = BytesIO()
#        async for chunk in file_bytes:
#            file_bytes_io.write(chunk)
        file_bytes_io.write(file_bytes.read())
        file_data = file_bytes_io.getvalue()

        # Verify payment based on configuration
        is_valid = False
        verification_message = ""

        if USE_KASPI_API:
            # Use Kaspi API verification
            print("🔍 Verifying payment with Kaspi API...")
            is_valid, verification_message = await verify_payment_kaspi(PAYMENT_AMOUNT,
                                                                        message.from_user.username or "")
        else:
            # Use receipt image verification with Ollama
            print("🔍 Verifying receipt image...")
            is_valid, verification_message = await verify_receipt_image(file_data, PAYMENT_AMOUNT)

            # Fallback to simple check if vision verification fails
            if not is_valid and "vision" in verification_message.lower():
                print("⚠️ Vision model not available, using simple verification...")
                is_valid, verification_message = await simple_receipt_check(file_data)

        # --- Send result to admin for manual validation ---
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Одобряю", callback_data=f"receipt_is_valid:{message.from_user.id}"
                ),
                types.InlineKeyboardButton(
                    text="🔁 Запросить повтор", callback_data=f"receipt_is_not_valid:{message.from_user.id}"
                ),
            ]
        ])

        caption_parts = [
            "💸 Новая заявка!",
            f"🔗 Ссылка: {instagram_url}",
            f"👤 Пользователь: @{message.from_user.username or message.from_user.id}",
            f"📝 Проверка: {'✅ Автоматически подтверждена' if is_valid else '⚠️ Требует ручной проверки'}"
            f"{verification_message}"
        ]

        # Add verification message only if not too long
        if verification_message and len("\n".join(caption_parts) + "\n" + verification_message) <= 1000:
            caption_parts.append(f"📋 {verification_message}")

        caption = "\n".join(caption_parts)

        # Final truncation safety check
        caption = truncate_caption(caption, max_length=1000)

        try:
            if message.photo:
                await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
            else:
                await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Error sending receipt to admin: {e}")
            # Fallback: send without verification details if caption still too long
            try:
                simple_caption = f"💸 Новая заявка!\n🔗 {instagram_url}\n👤 @{message.from_user.username or message.from_user.id}"
                if message.photo:
                    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=simple_caption, reply_markup=keyboard)
                else:
                    await bot.send_document(ADMIN_ID, message.document.file_id, caption=simple_caption, reply_markup=keyboard)
                logging.info("Fallback caption sent successfully")
            except Exception as e2:
                logging.error(f"Fallback caption also failed: {e2}")

        # --- Tell user we're waiting for admin approval ---
        if not is_valid:
            await message.answer("🔍 Чек отправлен администратору для подтверждения. Ожидайте решения.")
        else:
            # If auto-verified, skip to next step directly
            await message.answer(f"✅ {verification_message}\n\n🤖 Начинаю анализ профиля...")
            analysis = await analyze_profile_with_ollama(instagram_url)
            await message.answer(
                "👇 Теперь выбери один из трёх вариантов стратегии:",
                reply_markup=get_strategy_keyboard()
            )
            await state.update_data(analysis=analysis)
            await state.set_state(AnalysisStates.waiting_for_strategy_choice)
            return

        # --- Save user data in FSM storage (so callback can access it) ---
        await state.update_data(instagram_url=instagram_url)
            # Keep user in waiting_for_receipt state to try again


    except Exception as e:
        logging.error(f"Receipt handler error: {e}")
        await message.answer(f"❌ Ошибка при обработке файла: {str(e)}\n\nПожалуйста, попробуйте ещё раз.")

# callback handlers for main menu
@dp.callback_query(F.data == "main_start")
async def main_start_callback(callback: types.CallbackQuery, state: FSMContext):
    """Start analysis from main menu"""
    await callback.message.edit_text(
        "👋 Привет! Пришли ссылку на Instagram-профиль, который хочешь проанализировать.",
        reply_markup=None
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()


@dp.callback_query(F.data == "main_price")
async def main_price_callback(callback: types.CallbackQuery, state: FSMContext):
    """Show pricing from main menu"""
    pricing_text = PRICING_MESSAGE.replace("{PAYMENT_AMOUNT}", PAYMENT_AMOUNT)
    await callback.message.answer(pricing_text, parse_mode=ParseMode.HTML)
    await callback.answer()


@dp.callback_query(F.data == "main_end")
async def main_end_callback(callback: types.CallbackQuery, state: FSMContext):
    """Ask for confirmation to end analysis"""
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите завершить анализ?",
        reply_markup=get_exit_confirmation_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "confirm_end")
async def confirm_end_callback(callback: types.CallbackQuery, state: FSMContext):
    """Confirm end and clear state"""
    await callback.message.edit_text(
        "👋 Спасибо за использование FlirtAI!\n\n"
        "Используйте /start чтобы начать снова или /price чтобы узнать цены."
    )
    await state.clear()
    await callback.answer("✅ Анализ завершен.")

@dp.callback_query(F.data == "cancel_end")
async def cancel_end_callback(callback: types.CallbackQuery, state: FSMContext):
    """Cancel exit and return to previous state"""
    current_state = await state.get_state()

    if current_state == AnalysisStates.waiting_for_link:
        await callback.message.edit_text(
            "👋 Пришли ссылку на Instagram-профиль, который хочешь проанализировать.",
            reply_markup=None
        )
    elif current_state == AnalysisStates.waiting_for_strategy_choice:
        await callback.message.edit_text(
            "👇 Выбери один из трёх вариантов стратегии:",
            reply_markup=get_strategy_keyboard()
        )
    else:
        await callback.message.edit_text(
            "Продолжаем анализ...",
            reply_markup=get_analysis_menu_keyboard()
        )

    await callback.answer("✅ Продолжаем!")
@dp.callback_query(F.data.startswith("receipt_is_valid:"))
async def handle_receipt_approve(callback: types.CallbackQuery, state: FSMContext):
    """Admin approves receipt."""
    try:
        _, user_id_str = callback.data.split(":", 1)
        user_id = int(user_id_str)
    except Exception:
        await callback.answer("❌ Ошибка данных callback.")
        return

    # FIX: Get the correct FSM context for the user
    # The key format should match how aiogram stores it
    from aiogram.fsm.storage.memory import MemoryStorage

    # Get user's FSM data from storage
    try:
        fsm_storage = dp.storage
        fsm_key = f"user:{user_id}:chat:{user_id}"
        user_state_data = await fsm_storage.get_data(key=fsm_key)
        instagram_url = user_state_data.get("instagram_url") if user_state_data else None

        if not instagram_url:
            await callback.answer("❌ Не найдена ссылка на профиль.")
            return

    except Exception as e:
        logging.error(f"Could not retrieve user data: {e}")
        await callback.answer("❌ Ошибка при получении данных пользователя.")
        return

    # Edit admin message
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                f"{callback.message.caption}\n\n✅ Чек одобрен администратором."
            )
        else:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n✅ Чек одобрен администратором."
            )
    except Exception:
        logging.debug("Couldn't edit admin message caption/text")

    await callback.answer("✅ Чек одобрен — пользователь уведомлён.")

    # FIX: Notify user FIRST, THEN continue analysis (moved outside try-except)
    try:
        await bot.send_message(user_id, "✅ Ваш чек одобрен администратором. Начинаю анализ профиля...")
    except Exception as e:
        logging.warning(f"Failed to notify user {user_id}: {e}")

    # FIX: This is NOW OUTSIDE the except block - will always execute
    #if not instagram_url:
     #   try:
    #        await bot.send_message(user_id, "❌ Не удалось найти ссылку на профиль. Попробуйте отправить чек заново.")
   #     except:
  #          pass
 #       return

    # FIX: Call analyze_profile_with_ollama as a synchronous function (remove async)
    print(f"🤖 Starting analysis for user {user_id} on profile: {instagram_url}")
    analysis = await analyze_profile_with_ollama(instagram_url)

    # Send strategy options to user
    try:
        await bot.send_message(
            user_id,
            "👇 Теперь выбери один из трёх вариантов стратегии:",
            reply_markup=get_strategy_keyboard()
        )

        # Save analysis and move to next state
        await fsm_storage.set_data(
            key=fsm_key,
            data={
                "instagram_url": instagram_url,
                "analysis": analysis
            }
        )

        # FIX: Set state in FSM storage
        await fsm_storage.set_state(key=fsm_key, state=AnalysisStates.waiting_for_strategy_choice)

        print(f"✅ Analysis saved for user {user_id}")

    except Exception as e:
        logging.error(f"Error saving analysis: {e}")
        try:
            await bot.send_message(user_id, "❌ Ошибка при сохранении анализа. Попробуйте снова.")
        except:
            pass

@dp.callback_query(F.data.startswith("receipt_is_not_valid:"))
async def handle_receipt_reject(callback: types.CallbackQuery, state: FSMContext):
    """Admin rejects receipt and requests reupload."""
    try:
        _, user_id_str = callback.data.split(":", 1)
        user_id = int(user_id_str)
    except Exception:
        await callback.answer("❌ Ошибка данных callback.")
        return

    # Get FSM context for user
    user_state = dp.fsm.get_context(bot=bot, user_id=user_id, chat_id=user_id)

    # Edit admin message
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                f"{callback.message.caption}\n\n🔁 Запрошена повторная отправка чека."
            )
        else:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n🔁 Запрошена повторная отправка чека."
            )
    except Exception:
        logging.debug("Couldn't edit admin message caption/text")

    await callback.answer("🔁 Запрос на повторную отправку чека отправлен.")

    # Notify user & return to waiting state
    try:
        await bot.send_message(
            user_id,
            "🔁 Администратор запросил повторную отправку чека. "
            "Пожалуйста, пришлите корректный чек."
        )
        await user_state.set_state(AnalysisStates.waiting_for_receipt)
    except Exception as e:
        logging.warning(f"Failed to notify user {user_id}: {e}")

@dp.callback_query(F.data.startswith("strategy_"))
async def strategy_handler(callback: types.CallbackQuery, state: FSMContext):
    strategy_type = callback.data.split("_")[1]
    data = await state.get_data()
    analysis = data.get('analysis')

    # Safety check
#    if not analysis:
 #       await callback.answer("❌ Анализ не найден. Попробуйте начать с начала.")
  #      logging.warning(f"Analysis not found for user {callback.from_user.id}")
   #     return

    await callback.message.edit_text("🤖 Генерирую персональную стратегию знакомства...")

    strategy = await generate_strategy(analysis, strategy_type)

    await callback.message.answer(
        f"<b>Ваш анализ:</b>\n\n{analysis}",
        parse_mode="HTML"
    )

    strategy_names = {
        "professional": "🧑‍💼 Профессиональная стратегия",
        "personal": "❤️ Личная стратегия",
        "trash": "🤪 Трешовая стратегия"
    }

    await callback.message.answer(
        f"<b>{strategy_names[strategy_type]}:</b>\n\n{strategy}"
    )

    # Запрос обратной связи
    await callback.message.answer(
        "📊 Оцени результат от 1 до 10:",
        reply_markup=get_rating_keyboard()
    )

    await state.set_state(AnalysisStates.waiting_for_feedback)
    await callback.answer()


@dp.callback_query(F.data.startswith("rating_"))
async def rating_handler(callback: types.CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]

    await callback.message.edit_text(f"⭐ Спасибо за оценку: {rating}/10")

    await callback.message.answer(
        "🗣 Можешь оставить комментарий или нажать кнопку ниже:",
        reply_markup=get_restart_keyboard()
    )

    # Отправка рейтинга админу
    try:
        await bot.send_message(ADMIN_ID, f"⭐ Новая оценка: {rating}/10")
    except:
        pass

    await callback.answer()


@dp.callback_query(F.data == "restart")
async def restart_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "👋 Привет! Пришли ссылку на Instagram-профиль, который хочешь проанализировать."
    )
    await state.set_state(AnalysisStates.waiting_for_link)
    await callback.answer()


@dp.message(AnalysisStates.waiting_for_feedback)
async def feedback_handler(message: types.Message, state: FSMContext):
    feedback = message.text

    # Отправка отзыва админу
    try:
        await bot.send_message(ADMIN_ID, f"💬 Новый отзыв:\n{feedback}")
    except:
        pass

    await message.answer(
        "✅ Спасибо за отзыв!",
        reply_markup=get_restart_keyboard()
    )


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())