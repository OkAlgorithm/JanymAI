import asyncio
import logging
import re
import os
import tempfile
from datetime import datetime
from io import BytesIO

import aiohttp
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from playwright.async_api import async_playwright
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID")) # ID администратора
KASPI_NUMBER = os.getenv("KASPI_NUMBER")
PAYMENT_AMOUNT = os.getenv("PAYMENT_AMOUNT")

# Инициализация
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# Состояния FSM
class AnalysisStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_receipt = State()
    waiting_for_strategy_choice = State()
    waiting_for_feedback = State()


# Клавиатуры
def get_strategy_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💼 Профессиональное", callback_data="strategy_professional")],
        [InlineKeyboardButton(text="❤️ Личное", callback_data="strategy_personal")],
        [InlineKeyboardButton(text="🤪 Трешовое", callback_data="strategy_trash")]
    ])
    return keyboard


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

#инстаграм креды
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Функция для создания скриншотов Instagram профиля
async def take_instagram_screenshots(profile_url: str) -> list:
    """Создает скриншоты Instagram профиля используя Playwright"""
    screenshots = []
    auth_file = "auth_state.json"

    print("\n" + "=" * 60)
    print("🚀 STARTING INSTAGRAM SCREENSHOT PROCESS")
    print("=" * 60)

    p = None
    browser = None

    try:
        print("[STEP 1] Initializing Playwright...")
        try:
            p = await async_playwright().start()
            print("✅ Playwright initialized")
        except Exception as e:
            print(f"❌ CRITICAL: Failed to initialize Playwright: {e}")
            import traceback
            traceback.print_exc()
            return []

        print("\n[STEP 2] Launching browser with retry logic...")
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  Attempt {attempt}/{max_retries}...")
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                print(f"  ✅ Browser launched on attempt {attempt}")
                break
            except Exception as e:
                print(f"  ❌ Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    print("❌ CRITICAL: All browser launch attempts failed")
                    import traceback
                    traceback.print_exc()
                    return []
                await asyncio.sleep(2)

        print("\n[STEP 3] Creating browser context...")
        try:
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            if os.path.exists(auth_file):
                print(f"  📂 Found existing session file: {auth_file}")
                context_options['storage_state'] = auth_file
            else:
                print(f"  ⚠️ No session file found at: {auth_file}")

            context = await browser.new_context(**context_options)
            print("  ✅ Context created successfully")
        except Exception as e:
            print(f"  ❌ CRITICAL: Failed to create context: {e}")
            import traceback
            traceback.print_exc()
            if browser:
                await browser.close()
            return []

        print("\n[STEP 4] Creating new page...")
        try:
            page = await context.new_page()
            print("  ✅ Page created successfully")

            # Add stealth measures
            print("  → Adding stealth JavaScript...")
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            print("  ✅ Stealth measures applied")
        except Exception as e:
            print(f"  ❌ CRITICAL: Failed to create page: {e}")
            import traceback
            traceback.print_exc()
            await context.close()
            if browser:
                await browser.close()
            return []

        # Login if no saved session exists
        # Replace the login section (STEP 5) with this improved version:

        print("\n[STEP 5] Checking authentication status...")
        session_exists = os.path.exists(auth_file)
        needs_login = True

        if session_exists:
            print(f"  📂 Session file found: {auth_file}")
            print("  → Attempting to use existing session...")
            try:
                # Try to navigate to profile to verify session is valid
                await page.goto("https://www.instagram.com/", wait_until='load', timeout=15000)
                await asyncio.sleep(2)

                # Check if we're logged in by looking for specific elements
                try:
                    # If we can find the home feed/profile icon, we're logged in
                    await page.wait_for_selector('[aria-label="Home"]', timeout=5000)
                    print("  ✅ Session is valid and active!")
                    needs_login = False
                except:
                    print("  ⚠️ Session appears invalid or expired")
                    needs_login = True
            except Exception as e:
                print(f"  ⚠️ Failed to verify session: {e}")
                needs_login = True
        else:
            print(f"  ⚠️ No session file found: {auth_file}")
            needs_login = True

        if needs_login:
            print("\n[STEP 5.1] Performing new login...")
            try:
                print("  → Navigating to login page...")
                await page.goto("https://www.instagram.com/accounts/login/", wait_until='load', timeout=30000)
                print("  ✅ Login page loaded")

                await asyncio.sleep(3)

                print("  → Waiting for form elements...")
                await page.wait_for_selector('input[name="username"]', timeout=10000)
                await page.wait_for_selector('input[name="password"]', timeout=10000)
                await page.wait_for_selector('button[type="submit"]', timeout=10000)
                print("  ✅ All form elements found")

                print("  → Filling credentials...")
                print(f"    Username: {USERNAME[:3]}***")
                print(f"    Password: {'*' * len(PASSWORD)}")
                await page.fill('input[name="username"]', USERNAME)
                await page.fill('input[name="password"]', PASSWORD)
                print("  ✅ Credentials filled")

                print("  → Clicking submit button...")
                await page.click('button[type="submit"]')
                print("  ✅ Submit clicked")

                print("  → Waiting for login to complete...")
                try:
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    await asyncio.sleep(5)
                    print("  ✅ Login completed successfully")
                except TimeoutError:
                    print("  ⚠️ Login timeout, but continuing...")
                    await asyncio.sleep(5)

                # Handle optional dialogs
                print("  → Dismissing optional dialogs...")
                for label in ["Not Now", "Later"]:
                    try:
                        await page.click(f'text="{label}"', timeout=3000)
                        print(f"    ✅ Dismissed '{label}' dialog")
                    except:
                        pass

                # Verify we're actually logged in
                print("  → Verifying login success...")
                try:
                    await page.wait_for_selector('[aria-label="Home"]', timeout=10000)
                    print("  ✅ Login verification successful!")
                except:
                    print("  ⚠️ Could not verify login, but continuing...")

                # Save session for future use
                print(f"  → Saving session to {auth_file}...")
                try:
                    await context.storage_state(path=auth_file)
                    print(f"  ✅ Session saved successfully ({os.path.getsize(auth_file)} bytes)")
                except Exception as e:
                    print(f"  ⚠️ Failed to save session: {e}")

            except Exception as e:
                print(f"  ❌ Login failed: {e}")
                import traceback
                traceback.print_exc()

                # Try to close gracefully and return empty
                try:
                    await page.close()
                except:
                    pass
                try:
                    await context.close()
                except:
                    pass
                if browser:
                    try:
                        await browser.close()
                    except:
                        pass
                return []
        else:
            print("\n[STEP 5.1] Using existing valid session")
            print(f"  ✅ Session from: {auth_file} ({os.path.getsize(auth_file)} bytes)")

        print("\n[STEP 6] Navigating to Instagram profile...")
        try:
            print(f"  → URL: {profile_url}")

            # Set additional headers to look more like a real browser
            await page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })

            # Try with different wait conditions
            try:
                print("  → First attempt with 'load' state...")
                await page.goto(profile_url, wait_until='load', timeout=20000)
            except Exception as e:
                print(f"  ⚠️ Load failed ({str(e)[:50]}...), trying 'domcontentloaded'...")
                try:
                    await page.goto(profile_url, wait_until='domcontentloaded', timeout=20000)
                except Exception as e2:
                    print(f"  ⚠️ Domcontentloaded failed ({str(e2)[:50]}...), trying without wait...")
                    await page.goto(profile_url, wait_until='commit', timeout=20000)

            print("  ✅ Profile page navigated")

            # Wait for page to be somewhat interactive
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
                print("  ✅ Network idle reached")
            except:
                print("  ⚠️ Network idle timeout, continuing anyway")

            await asyncio.sleep(5)
        except Exception as e:
            print(f"  ❌ Failed to navigate to profile: {e}")
            import traceback
            traceback.print_exc()
            await page.close()
            await context.close()
            if browser:
                await browser.close()
            return []

        print("\n[STEP 7] Taking main profile screenshot...")
        try:
            if page.is_closed():
                print("  ❌ Page is closed!")
                return screenshots

            print("  → Taking screenshot...")
            screenshot = await page.screenshot(full_page=True)
            print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
            screenshots.append(('profile', screenshot))
        except Exception as e:
            print(f"  ❌ Profile screenshot failed: {e}")
            import traceback
            traceback.print_exc()

        print("\n[STEP 8] Taking highlights screenshot...")
        try:
            if page.is_closed():
                print("  ❌ Page is closed!")
            else:
                highlights = await page.query_selector_all('[role="button"][tabindex="0"]')
                print(f"  ✅ Found {len(highlights)} highlight buttons")

                if highlights and len(highlights) > 0:
                    await highlights[0].click()
                    await asyncio.sleep(2)
                    screenshot = await page.screenshot(full_page=True)
                    print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
                    screenshots.append(('highlights', screenshot))
                    await page.go_back()
                    await asyncio.sleep(2)
                else:
                    print("  ℹ️ No highlights found, skipping")
        except Exception as e:
            print(f"  ❌ Highlights screenshot failed: {e}")

        print("\n[STEP 9] Taking followers screenshot...")
        try:
            if page.is_closed():
                print("  ❌ Page is closed!")
            else:
                followers_link = await page.query_selector('a[href*="/followers/"]')

                if followers_link:
                    await followers_link.click()
                    await asyncio.sleep(3)
                    screenshot = await page.screenshot(full_page=True)
                    print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
                    screenshots.append(('followers', screenshot))
                    await page.go_back()
                    await asyncio.sleep(2)
                else:
                    print("  ℹ️ Followers link not found, skipping")
        except Exception as e:
            print(f"  ❌ Followers screenshot failed: {e}")

        print("\n[STEP 10] Taking posts screenshot...")
        try:
            if page.is_closed():
                print("  ❌ Page is closed!")
            else:
                posts = await page.query_selector_all('article img')
                print(f"  ✅ Found {len(posts)} posts")

                if posts and len(posts) > 0:
                    await posts[0].click()
                    await asyncio.sleep(3)
                    screenshot = await page.screenshot(full_page=True)
                    print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
                    screenshots.append(('posts', screenshot))
                else:
                    print("  ℹ️ No posts found, skipping")
        except Exception as e:
            print(f"  ❌ Posts screenshot failed: {e}")

        print("\n[STEP 11] Closing resources...")
        try:
            if page and not page.is_closed():
                await page.close()
                print("  ✅ Page closed")
        except Exception as e:
            print(f"  ⚠️ Error closing page: {e}")

        try:
            if context:
                await context.close()
                print("  ✅ Context closed")
        except Exception as e:
            print(f"  ⚠️ Error closing context: {e}")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[FINAL] Closing browser and Playwright...")
        try:
            if browser:
                await browser.close()
                print("  ✅ Browser closed")
        except Exception as e:
            print(f"  ⚠️ Error closing browser: {e}")

        try:
            if p:
                await p.stop()
                print("  ✅ Playwright stopped")
        except Exception as e:
            print(f"  ⚠️ Error stopping Playwright: {e}")

        print(f"\n{'=' * 60}")
        print(f"📊 RESULTS: {len(screenshots)} screenshots captured")
        for name, data in screenshots:
            print(f"  - {name}: {len(data)} bytes")
        print("=" * 60 + "\n")

    return screenshots


OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")  # or "mistral", "neural-chat", etc.


def call_ollama(messages: list, max_tokens: int = 2000) -> str:
    """Call local Ollama API instead of OpenAI"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "num_predict": max_tokens
        }

        response = requests.post(
            f"{OLLAMA_API_URL}/api/chat",
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        result = response.json()
        return result.get("message", {}).get("content", "")

    except requests.exceptions.ConnectionError:
        logging.error(f"❌ Cannot connect to Ollama at {OLLAMA_API_URL}")
        return "Ошибка: Не удалось подключиться к локальному Ollama сервису."
    except Exception as e:
        logging.error(f"❌ Ollama API error: {e}")
        return f"Ошибка при обработке запроса: {str(e)}"

# Функция для анализа через GPT
async def analyze_profile_with_gpt(screenshots: list, profile_url: str) -> str:
    """Анализирует профиль используя локальный Ollama"""
    try:
        # Подготовка изображений для Ollama
        import base64
        images_for_ollama = []
        for name, screenshot_bytes in screenshots:
            image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            images_for_ollama.append(image_base64)

        # Промпт для анализа
        system_prompt = """
        Ты эксперт по профайлингу и анализу социальных сетей. 
        Проведи глубокий анализ Instagram-профиля, используя:
        - Физиогномику и психологические особенности
        - Анализ контента и интересов
        - Социальные связи и активность
        - Стиль жизни и ценности

        Дай развернутый анализ личности человека на русском языке.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Проанализируй эти изображения Instagram профиля"
            }
        ]

        # NOTE: Basic Ollama doesn't support image inputs in the same way as OpenAI
        # If you need image support, you'll need to use a vision-capable model like llava
        # For now, we'll just use text analysis

        analysis = call_ollama(messages, max_tokens=2000)
        return analysis if analysis else "Ошибка при анализе профиля."

    except Exception as e:
        logging.error(f"❌ Ошибка при анализе через Ollama: {e}")
        return "Извините, произошла ошибка при анализе профиля."


# Функция для генерации стратегий знакомства
async def generate_strategy(analysis: str, strategy_type: str) -> str:
    """Генерирует стратегию знакомства на основе анализа"""
    try:
        strategy_prompts = {
            "professional": "Создай профессиональную стратегию знакомства для деловых целей",
            "personal": "Создай личную романтическую стратегию знакомства",
            "trash": "Создай креативную и необычную стратегию знакомства"
        }

        prompt = f"""
        На основе анализа личности создай {strategy_prompts[strategy_type]}.

        Анализ: {analysis}

        Дай конкретные рекомендации:
        - Как начать диалог
        - О чем говорить
        - Каких тем избегать
        - Какой подход использовать
        """

        messages = [{"role": "user", "content": prompt}]
        strategy = call_ollama(messages, max_tokens=1000)

        return strategy if strategy else "Ошибка при создании стратегии."

    except Exception as e:
        logging.error(f"❌ Ошибка при генерации стратегии: {e}")
        return "Извините, произошла ошибка при создании стратегии."


# Хэндлеры
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Пришли ссылку на Instagram-профиль, который хочешь проанализировать."
    )
    await state.set_state(AnalysisStates.waiting_for_link)


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


@dp.message(AnalysisStates.waiting_for_receipt, F.content_type.in_(['photo', 'document']))
async def receipt_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    instagram_url = data['instagram_url']

    # Отправка админу
    try:
        if message.photo:
            await bot.send_photo(
                ADMIN_ID,
                message.photo[-1].file_id,
                caption=f"💸 Новая заявка!\n🔗 Ссылка: {instagram_url}\n📎 Чек: фото"
            )
        elif message.document:
            await bot.send_document(
                ADMIN_ID,
                message.document.file_id,
                caption=f"💸 Новая заявка!\n🔗 Ссылка: {instagram_url}\n📎 Чек: документ"
            )
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

    await message.answer("✅ Чек получен! Начинаю анализ профиля...")

    # Создание скриншотов
    await message.answer("📸 Делаю скриншоты профиля...")
    screenshots = await take_instagram_screenshots(instagram_url)

    if not screenshots:
        await message.answer("❌ Не удалось получить доступ к профилю. Проверьте, что профиль открытый.")
        await state.clear()
        return

    # Анализ через GPT
    await message.answer("🤖 Анализирую профиль с помощью ИИ...")
    analysis = await analyze_profile_with_gpt(screenshots, instagram_url)

    # Отправка анализа
    await message.answer(f"📊 <b>Анализ профиля:</b>\n\n{analysis}")

    # Предложение выбрать стратегию
    await message.answer(
        "👇 Теперь выбери один из трёх вариантов стратегии:",
        reply_markup=get_strategy_keyboard()
    )

    await state.update_data(analysis=analysis)
    await state.set_state(AnalysisStates.waiting_for_strategy_choice)


@dp.callback_query(F.data.startswith("strategy_"))
async def strategy_handler(callback: types.CallbackQuery, state: FSMContext):
    strategy_type = callback.data.split("_")[1]
    data = await state.get_data()
    analysis = data['analysis']

    await callback.message.edit_text("🤖 Генерирую персональную стратегию знакомства...")

    strategy = await generate_strategy(analysis, strategy_type)

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