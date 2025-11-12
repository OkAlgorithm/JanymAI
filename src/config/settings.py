import os
from dotenv import load_dotenv
import src.config.settings as settings

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
KASPI_NUMBER = os.getenv("KASPI_NUMBER")
PAYMENT_AMOUNT = os.getenv("PAYMENT_AMOUNT")
KASPI_API_KEY = os.getenv("KASPI_API_KEY", "")
KASPI_MERCHANT_ID = os.getenv("KASPI_MERCHANT_ID", "")
USE_KASPI_API = os.getenv("USE_KASPI_API", "false").lower() == "true"
PAYMENT_AMOUNT_FLOAT = float(settings.PAYMENT_AMOUNT.replace(' ₸', '').replace('₸', '').strip())
# Ollama settings
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL_LLAMA2 = os.getenv("OLLAMA_MODEL_LLAMA2", "llama2")
OLLAMA_MODEL_LLAVA = os.getenv("OLLAMA_MODEL_LLAVA", "llava")

# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Redis URL
redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Constants
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

# Database
DB_PATH = os.getenv("DB_PATH", "flirt_ai.db")