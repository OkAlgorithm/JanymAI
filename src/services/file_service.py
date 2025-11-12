import io
from src.utils.logger import logger


async def download_file(bot, file_id: str) -> bytes:
    """
    Download file bytes from Telegram (photo or document)

    Args:
        bot: Aiogram Bot instance
        file_id: Telegram file ID

    Returns:
        File bytes
    """
    try:
        file_info = await bot.get_file(file_id)
        file = await bot.download_file(file_info.file_path)
        return file.read()
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        raise