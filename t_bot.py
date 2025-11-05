import asyncio
import logging
import re
import os
import tempfile
from datetime import datetime
from io import BytesIO

import aiohttp
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

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()

            #Логин на профиль
            if context.storage_state():
                print("🔄 Opening login page...")
                await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")
                await page.wait_for_timeout(3000)
                try:
                    print("⏳ Waiting for username field...")
                    await page.wait_for_selector('input[name="username"]', timeout=10000)
                    await page.wait_for_selector('input[name="password"]', timeout=10000)
                    await page.wait_for_selector('button[type="submit"]', timeout=10000)
                except TimeoutError:
                    print("❌ Timeout: Login form did not load in time.")
                    await browser.close()
                    return

                print("✍️ Filling login form...")
                await page.fill('input[name="username"]', USERNAME)
                await page.fill('input[name="password"]', PASSWORD)
                await page.click('button[type="submit"]')

                print("⏳ Waiting for login to complete...")
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(5000)
                except TimeoutError:
                    print("⚠️ Login may not have completed — continuing anyway.")

            # Handle optional "Save Your Login Info?" / "Turn on Notifications"
            for label in ["Not Now", "Later"]:
                try:
                    await page.click(f'text="{label}"', timeout=3000)
                except:
                    pass

            # Save session
            await context.storage_state(path="auth_state.json")
            print("✅ Login complete. Session saved to auth_state.json")

            # Переход на профиль
            await page.goto(profile_url, wait_until='networkidle')
            await page.wait_for_timeout(5000)

            safe_filename = re.sub(r'\\W+', '_', profile_url)

            # Основной профиль
            try:
                screenshot = await page.screenshot(path=f"{profile_url}_profile.png", full_page=True)
                screenshots.append(('profile', screenshot))
                logging.info(f"✅ Profile screenshot saved: {safe_filename}_profile.png")
            except Exception as e:
                logging.error(f"profile screenshots were not taken")

            # Попытка сделать дополнительные скриншоты
            try:
                # Хайлайты (если есть)
                highlights = await page.query_selector_all('[role="button"][tabindex="0"]')
                if highlights:
                    await highlights[0].click()
                    await page.wait_for_timeout(2000)
                    screenshot = await page.screenshot(full_page=True)
                    screenshots.append(('highlights', screenshot))
                    logging.info(f"✅ highlights screenshot saved")
                    await page.go_back()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                logging.error(f"highlights screenshots were not taken")

            try:
                # Подписки/подписчики
                followers_link = await page.query_selector('a[href*="/followers/"]')
                if followers_link:
                    await followers_link.click()
                    await page.wait_for_timeout(3000)
                    screenshot = await page.screenshot(full_page=True)
                    screenshots.append(('followers', screenshot))
                    logging.info(f"✅ followers screenshot saved")
                    await page.go_back()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                logging.error(f"followers screenshots were not taked")
                pass

            try:
                # Посты
                posts = await page.query_selector_all('article img')
                if posts and len(posts) > 0:
                    await posts[0].click()
                    await page.wait_for_timeout(3000)
                    screenshot = await page.screenshot(full_page=True)
                    screenshots.append(('posts', screenshot))
                    logging.info(f"✅ Posts screenshot saved")
            except Exception as e:
                logging.error(f"posts screenshots were not taked")
                pass

            await browser.close()

    except Exception as e:
        logging.error(f"Ошибка при создании скриншотов: {e}")

    return screenshots


# Функция для анализа через GPT
async def analyze_profile_with_gpt(screenshots: list, profile_url: str) -> str:
    """Анализирует профиль используя GPT-4o"""
    try:
        # Подготовка изображений для GPT
        images_for_gpt = []
        for name, screenshot_bytes in screenshots:
            # Конвертируем в base64
            import base64
            image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            images_for_gpt.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}"
                }
            })

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
                "content": [
                    {"type": "text", "text": f"Проанализируй эти изображения"},
                    *images_for_gpt
                ]
            }
        ]

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=2000
        )

        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"Ошибка при анализе через GPT: {e}")
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

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )

        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"Ошибка при генерации стратегии: {e}")
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