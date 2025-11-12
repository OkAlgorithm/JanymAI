import aiohttp
import asyncio
import src.config.settings as settings
from src.utils.logger import logger
from src.utils.validators import truncate_caption


async def call_ollama(
        messages: list,
        model: str = None,
        max_tokens: int = 3000,
        temperature: float = 0.7,
        **extra_payload
) -> str:
    """
    Async call to local Ollama API with flexible payload support

    Args:
        messages: List of message dicts with role & content
        model: Model name (defaults to OLLAMA_MODEL_LLAMA2)
        max_tokens: Maximum tokens in response
        temperature: Temperature for generation (0.0-1.0)
        **extra_payload: Additional fields for the API request

    Returns:
        Model response text or error message
    """
    model = model or settings.OLLAMA_MODEL_LLAMA2

    try:
        logger.info(f"🤖 Testing connection to Ollama at {settings.OLLAMA_API_URL}...")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{settings.OLLAMA_API_URL}/api/tags") as health_response:
                    logger.info("✅ Ollama is reachable")
        except Exception as e:
            logger.error(f"⚠️ Cannot reach Ollama at {settings.OLLAMA_API_URL}: {e}")
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

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            async with session.post(
                    f"{settings.OLLAMA_API_URL}/api/chat",
                    json=payload
            ) as response:
                logger.info(f"→ Response status: {response.status}")

                if response.status == 404:
                    error_msg = f"Model '{model}' not found! Run: ollama pull {model}"
                    logger.error(f"❌ {error_msg}")
                    return f"Error: {error_msg}"

                response.raise_for_status()

                result = await response.json()
                content = result.get("message", {}).get("content", "")
                logger.info(f"✅ Response received ({len(content)} chars)")
                return content

    except aiohttp.ClientConnectionError as e:
        logger.error(f"❌ Cannot connect to Ollama: {e}")
        return "Error: Ollama service not available."
    except asyncio.TimeoutError:
        logger.error("❌ Ollama request timeout")
        return "Error: Ollama response timeout."
    except Exception as e:
        logger.error(f"❌ Ollama API error: {e}")
        return f"Error: {str(e)}"


async def analyze_profile_with_ollama(profile_url: str) -> str:
    """Анализирует Instagram профиль используя Ollama (async)"""
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
        analysis = await call_ollama(messages, max_tokens=2000)

        if analysis.startswith("Error:"):
            logger.error(f"Analysis failed: {analysis}")
            return "Извините, произошла ошибка при анализе профиля."

        logger.info(f"✅ Analysis completed ({len(analysis)} characters)")
        return analysis

    except Exception as e:
        logger.error(f"❌ Error analyzing profile: {e}")
        return "Извините, произошла ошибка при анализе профиля."


async def generate_strategy(analysis: str, strategy_type: str) -> str:
    """Генерирует стратегию знакомства на основе анализа (async)"""
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
        strategy = await call_ollama(messages, max_tokens=1000)

        logger.info("Strategy generation complete")
        return strategy if not strategy.startswith("Error:") else "Ошибка при создании стратегии."

    except Exception as e:
        logger.error(f"Error generating strategy: {e}")
        return "Ошибка при создании стратегии."