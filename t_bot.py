import asyncio
import logging
import re
import os
import tempfile
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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.safari.options import Options
from selenium.webdriver.safari.service import Service
import time
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
# Replace the browser launch section (STEP 1-4) with this robust version:

async def take_instagram_screenshots(profile_url: str) -> list:
    """Создает скриншоты Instagram профиля используя Selenium"""
    screenshots = []
    driver = None

    print("\n" + "=" * 60)
    print("🚀 STARTING INSTAGRAM SCREENSHOT PROCESS WITH SELENIUM")
    print("=" * 60)

    try:
        print("[STEP 0] Closing any existing Safari sessions...")
        try:
            # Try to quit any existing driver
            import atexit
            for handler in atexit._registry[:]:
                try:
                    handler()
                except:
                    pass
        except:
            pass

        time.sleep(2)

        print("[STEP 1] Setting up Safari WebDriver...")

        # Safari options
        safari_options = Options()
        safari_options.allow_insecure_certs = True

        print("✅ Safari options configured")

        print("[STEP 2] Launching Safari WebDriver...")
        print("  ⚠️ Make sure you enabled 'Allow remote automation' in Safari Settings")
        print("  → Steps: Safari → Settings → Advanced → Enable 'Allow remote automation'")

        try:
            driver = webdriver.Safari(options=safari_options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            print("✅ Safari WebDriver launched")
        except Exception as e:
            if "Allow remote automation" in str(e):
                print("❌ CRITICAL: Remote automation is not enabled in Safari!")
                print("   Please enable it in Safari → Settings → Advanced → Allow remote automation")
                return []
            raise

        print("\n[STEP 3] Logging into Instagram...")
        try:
            print("  → Navigating to Instagram login...")
            driver.get("https://www.instagram.com/accounts/login/")
            print("  → Page loaded, waiting for content...")
            time.sleep(5)

            print("  → Waiting for login form...")

            # Try multiple selectors for username field
            username_field = None
            password_field = None
            login_button = None

            selectors_to_try = [
                (By.NAME, "username"),
                (By.XPATH, "//input[@autocomplete='username']"),
                (By.XPATH, "//input[@placeholder='Phone number, username, or email']"),
                (By.CSS_SELECTOR, "input[type='text']"),
            ]

            print("  → Trying username field selectors...")
            for selector_type, selector_value in selectors_to_try:
                try:
                    print(f"    Trying: {selector_type} = {selector_value}")
                    username_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    print(f"    ✅ Found username field!")
                    break
                except:
                    continue

            if not username_field:
                print("  ❌ Could not find username field with any selector")
                print(f"  → Page title: {driver.title}")
                print(f"  → Current URL: {driver.current_url}")
                # Take screenshot for debugging
                screenshot = driver.get_screenshot_as_png()
                with open("instagram_login_debug.png", "wb") as f:
                    f.write(screenshot)
                print("  → Saved debug screenshot to: instagram_login_debug.png")
                return []

            print("  → Finding password field...")
            password_field = driver.find_element(By.NAME, "password")
            if not password_field:
                # Try alternative selectors
                password_field = driver.find_element(By.XPATH, "//input[@type='password']")

            print("  → Finding login button...")
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Log in')]")

            print("  ✅ All form elements found")
            print("  → Filling credentials...")
            print(f"    Username: {USERNAME[:3]}***")

            # Clear fields first
            print("    Clearing username field...")
            username_field.clear()
            time.sleep(0.5)

            # Type username slowly character by character
            print("    Typing username...")
            for char in USERNAME:
                username_field.send_keys(char)
                time.sleep(0.05)  # 50ms between each character

            time.sleep(1)

            # Click on password field to ensure focus
            print("    Clicking on password field...")
            password_field.click()
            time.sleep(0.5)

            # Clear password field
            print("    Clearing password field...")
            password_field.clear()
            time.sleep(0.5)

            # Type password slowly character by character
            print("    Typing password...")
            for char in PASSWORD:
                password_field.send_keys(char)
                time.sleep(0.05)  # 50ms between each character

            time.sleep(1)
            print("  ✅ Credentials entered")

            print("  → Clicking login button...")
            time.sleep(1)

            button_clicked = False

            # Try keyboard submission first (most reliable)
            keyboard_methods = [
                ("Press Tab to focus button, then Enter", lambda: (
                    driver.find_element(By.NAME, "password").send_keys("\t"),
                    time.sleep(0.3),
                    driver.find_element(By.NAME, "password").send_keys("\n")
                )),
                (
                "Direct Enter key on password field", lambda: driver.find_element(By.NAME, "password").send_keys("\n")),
                ("Press Tab multiple times then Enter", lambda: (
                    driver.find_element(By.NAME, "password").send_keys("\t\t\n")
                )),
            ]

            for method_name, method_func in keyboard_methods:
                try:
                    print(f"    Trying keyboard method: {method_name}...")
                    time.sleep(0.5)
                    method_func()
                    print(f"    ✅ Form submitted via: {method_name}")
                    button_clicked = True
                    break
                except Exception as e:
                    print(f"    ⚠️ Keyboard method failed: {str(e)[:50]}")
                    continue

            # If keyboard methods didn't work, try clicking methods
            if not button_clicked:
                print("    → Keyboard methods failed, trying click methods...")

                click_methods = [
                    ("Simple JavaScript form submit", lambda: driver.execute_script(
                        "document.querySelector('form').submit()"
                    )),
                    ("Find all buttons and click the blue one", lambda: driver.execute_script("""
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            if (btn.textContent.includes('Log') && btn.offsetParent !== null) {
                                btn.click();
                                break;
                            }
                        }
                    """)),
                    ("Click button by computed style", lambda: driver.execute_script("""
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const logBtn = buttons.find(b => b.textContent.includes('Log in'));
                        if (logBtn) logBtn.click();
                    """)),
                    ("Direct element click with JavaScript", lambda: driver.execute_script(
                        "document.querySelectorAll('button')[document.querySelectorAll('button').length - 2].click()"
                    )),
                ]

                for method_name, click_func in click_methods:
                    try:
                        print(f"    Trying: {method_name}...")
                        time.sleep(0.5)
                        click_func()
                        print(f"    ✅ Button clicked successfully via: {method_name}")
                        button_clicked = True
                        break
                    except Exception as e:
                        print(f"    ⚠️ Failed: {str(e)[:50]}")
                        continue

            if not button_clicked:
                print("  ❌ Could not submit login with any method")
                try:
                    screenshot = driver.get_screenshot_as_png()
                    with open("instagram_login_button_debug.png", "wb") as f:
                        f.write(screenshot)
                    print("  → Saved debug screenshot to: instagram_login_button_debug.png")

                    # Print page source snippet
                    page_source = driver.page_source
                    if "Log in" in page_source:
                        print("  → 'Log in' text found in page source")
                    if "<button" in page_source:
                        print("  → Buttons found in page source")

                    # Try to find any form
                    forms = driver.find_elements(By.TAG_NAME, "form")
                    print(f"  → Found {len(forms)} forms on page")

                except Exception as debug_e:
                    print(f"  → Error getting debug info: {debug_e}")
                return []

            print("  → Waiting for login to complete...")
            time.sleep(8)

            # CRITICAL: Verify login was actually successful before proceeding
            print("  → Verifying login success...")
            login_successful = False

            verification_attempts = [
                ("Home button", (By.XPATH, "//*[@aria-label='Home']")),
                ("Profile icon", (By.XPATH, "//*[@aria-label='Profile']")),
                ("Search bar", (By.XPATH, "//input[@placeholder='Search']")),
                ("Feed", (By.XPATH, "//article")),
            ]

            for verification_name, (locator_type, locator_value) in verification_attempts:
                try:
                    print(f"    Checking for: {verification_name}...")
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((locator_type, locator_value))
                    )
                    print(f"    ✅ Found {verification_name} - Login confirmed!")
                    login_successful = True
                    break
                except:
                    print(f"    ❌ {verification_name} not found")
                    continue

            if not login_successful:
                print("  ❌ CRITICAL: Login verification FAILED!")
                print("  → Instagram login did not complete successfully")
                print("  → Saving debug screenshot...")
                try:
                    screenshot = driver.get_screenshot_as_png()
                    with open("instagram_login_verification_failed.png", "wb") as f:
                        f.write(screenshot)
                    print("  → Saved to: instagram_login_verification_failed.png")
                    print(f"  → Current URL: {driver.current_url}")
                    print(f"  → Page title: {driver.title}")
                except:
                    pass
                return []

            print("  ✅ Login verified successfully - Proceeding with profile analysis")
            time.sleep(3)

            # Dismiss any popups
            print("  → Dismissing optional dialogs...")
            try:
                dismiss_buttons = driver.find_elements(By.XPATH,
                                                       "//*[contains(text(), 'Not Now') or contains(text(), 'Later')]")
                for button in dismiss_buttons[:3]:  # Limit to first 3
                    try:
                        button.click()
                        time.sleep(0.5)
                    except:
                        pass
            except:
                pass

        except Exception as e:
            print(f"  ❌ Login failed: {e}")
            import traceback
            traceback.print_exc()

            # Save debug screenshot
            try:
                screenshot = driver.get_screenshot_as_png()
                with open("instagram_login_error_debug.png", "wb") as f:
                    f.write(screenshot)
                print("  → Saved debug screenshot to: instagram_login_error_debug.png")
            except:
                pass

            return []

        print("\n[STEP 4] Navigating to Instagram profile...")
        try:
            print(f"  → URL: {profile_url}")
            driver.get(profile_url)
            print("  ✅ Profile page loaded")
            time.sleep(3)
        except Exception as e:
            print(f"  ❌ Failed to navigate to profile: {e}")
            import traceback
            traceback.print_exc()
            return []

        print("\n[STEP 5] Taking main profile screenshot...")
        try:
            screenshot = driver.get_screenshot_as_png()
            filename = "instagram_profile.png"
            with open(filename, "wb") as f:
                f.write(screenshot)
            print(f"  ✅ Screenshot saved: {filename} ({len(screenshot)} bytes)")
            screenshots.append(('profile', screenshot))
        except Exception as e:
            print(f"  ❌ Profile screenshot failed: {e}")

        print("\n[STEP 6] Taking highlights screenshot...")
        try:
            # Scroll to highlights
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(2)

            highlight_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'highlight')]")
            if highlight_buttons:
                highlight_buttons[0].click()
                time.sleep(2)
                screenshot = driver.get_screenshot_as_png()
                print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
                screenshots.append(('highlights', screenshot))
                driver.back()
                time.sleep(2)
            else:
                print("  ℹ️ No highlights found")
        except Exception as e:
            print(f"  ❌ Highlights screenshot failed: {e}")

        print("\n[STEP 7] Taking followers screenshot...")
        try:
            # Scroll back to top
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)

            followers_link = driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]")
            followers_link.click()
            time.sleep(3)
            screenshot = driver.get_screenshot_as_png()
            print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
            screenshots.append(('followers', screenshot))
            driver.back()
            time.sleep(2)
        except Exception as e:
            print(f"  ❌ Followers screenshot failed: {e}")

        print("\n[STEP 8] Taking posts screenshot...")
        try:
            # Scroll to posts section
            driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(2)

            posts = driver.find_elements(By.XPATH, "//article//img")
            if posts:
                posts[0].click()
                time.sleep(2)
                screenshot = driver.get_screenshot_as_png()
                print(f"  ✅ Screenshot captured ({len(screenshot)} bytes)")
                screenshots.append(('posts', screenshot))
            else:
                print("  ℹ️ No posts found")
        except Exception as e:
            print(f"  ❌ Posts screenshot failed: {e}")

        print("\n[STEP 9] Closing driver...")
        try:
            driver.quit()
            print("  ✅ WebDriver closed")
        except Exception as e:
            print(f"  ⚠️ Error closing driver: {e}")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

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
        # Test connection first
        print(f"  → Testing connection to Ollama at {OLLAMA_API_URL}...")
        try:
            health_response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            print(f"  ✅ Ollama is reachable")
            print(f"  → Available models: {health_response.text[:100]}")
        except Exception as e:
            print(f"  ⚠️ Cannot reach Ollama at {OLLAMA_API_URL}")
            print(f"     Make sure Ollama is running: ollama serve")
            print(f"     Or check if it's on a different host/port")
            return "Error: Ollama service not available. Make sure it's running with 'ollama serve'"

        print(f"  → Sending request to model: {OLLAMA_MODEL}")

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

        print(f"  → Response status: {response.status_code}")

        if response.status_code == 404:
            print(f"  ❌ Model '{OLLAMA_MODEL}' not found!")
            print(f"     Available models can be seen in: ollama list")
            print(f"     Pull a model with: ollama pull llama2")
            return f"Error: Model '{OLLAMA_MODEL}' not found. Run 'ollama pull {OLLAMA_MODEL}'"

        response.raise_for_status()

        result = response.json()
        return result.get("message", {}).get("content", "")

    except requests.exceptions.ConnectionError as e:
        logging.error(f"❌ Cannot connect to Ollama at {OLLAMA_API_URL}")
        print(f"\n⚠️ CONNECTION ERROR:")
        print(f"   Ollama is not running or not accessible at {OLLAMA_API_URL}")
        print(f"\n   To fix:")
        print(f"   1. Install Ollama from https://ollama.ai")
        print(f"   2. Run: ollama serve")
        print(f"   3. In another terminal, pull a model: ollama pull llama2")
        print(f"   4. Then restart this bot\n")
        return "Ошибка: Ollama сервис не доступен. Запустите: ollama serve"
    except requests.exceptions.Timeout:
        logging.error(f"❌ Ollama request timeout")
        return "Error: Ollama response timeout. The model might be processing a very long request."
    except Exception as e:
        logging.error(f"❌ Ollama API error: {e}")
        return f"Error: {str(e)}"

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