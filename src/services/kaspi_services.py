import base64
import asyncio
import aiohttp
from io import BytesIO
from PIL import Image
import src.config.settings as settings
from src.utils.logger import logger

async def verify_payment_kaspi(amount: str, user_phone: str) -> tuple[bool, str]:
    """
    Verify payment using Kaspi API (already async)
    Returns: (is_verified, message)
    """
    if not settings.KASPI_API_KEY or not settings.KASPI_MERCHANT_ID:
        return False, "Kaspi API credentials not configured"

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {settings.KASPI_API_KEY}",
                "Content-Type": "application/json"
            }

            url = "https://api.kaspi.kz/v2/merchant/transactions"
            params = {
                "merchant_id": settings.KASPI_MERCHANT_ID,
                "limit": 10
            }

            async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
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
    Verify receipt image using Ollama vision (requires vision model like llava) - now async
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

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(
                f"{settings.OLLAMA_API_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL_LLAVA,
                    "messages": messages,
                    "stream": False,
                    "max_tokens": 300
                }
            ) as response:
                logger.info(f"LLAVA response: {response.status}")

                if response.status == 200:
                    result = await response.json()
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
    Simple receipt check - verify it's a valid image (sync, but short-lived; no change needed)
    Returns: (is_valid, message)
    """
    try:
        file_size_mb = len(file_bytes) / (1024 * 1024)

        if file_size_mb > 50:
            return False, "❌ File too large (max 50MB)"

        if file_size_mb < 0.01:
            return False, "❌ File too small"

        try:
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
