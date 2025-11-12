from aiogram.fsm.storage.base import StorageKey
from src.utils.logger import logger

async def get_user_state_data(storage, user_id: int, chat_id: int = None, bot_id: int = None) -> dict:
    """
    Safely get user's FSM data from Redis

    Args:
        storage: RedisStorage instance
        user_id: Telegram user ID
        chat_id: Optional chat ID (defaults to user_id for private chats)
        bot_id: Bot ID (defaults to storage's bot_id)

    Returns:
        Dictionary with user data, empty dict if not found
    """
    try:
        chat_id = chat_id or user_id
        bot_id = bot_id or storage.bot_id if hasattr(storage, 'bot_id') else None
        key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)

        data = await storage.get_data(key=key)
        return data if data else {}
    except Exception as e:
        logger.error(f"Error getting FSM data for user {user_id}: {e}")
        return {}

async def update_user_state_data(storage, user_id: int, data: dict, chat_id: int = None, bot_id: int = None) -> bool:
    """
    Safely update user's FSM data in Redis

    Args:
        storage: RedisStorage instance
        user_id: Telegram user ID
        data: Dictionary with data to save
        chat_id: Optional chat ID (defaults to user_id for private chats)
        bot_id: Bot ID (defaults to storage's bot_id if available)

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        bot_id = bot_id or storage.bot_id if hasattr(storage, 'bot_id') else None
        key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)

        await storage.set_data(key=key, data=data)
        return True
    except Exception as e:
        logger.error(f"Error updating FSM data for user {user_id}: {e}")
        return False

async def set_user_state(storage, user_id: int, state, chat_id: int = None, bot_id: int = None) -> bool:
    """
    Safely set user's FSM state in Redis

    Args:
        storage: RedisStorage instance
        user_id: Telegram user ID
        state: FSM State to set
        chat_id: Optional chat ID (defaults to user_id for private chats)
        bot_id: Bot ID

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        bot_id = bot_id or storage.bot_id if hasattr(storage, 'bot_id') else None
        key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)

        await storage.set_state(key=key, state=state)
        return True
    except Exception as e:
        logger.error(f"Error setting FSM state for user {user_id}: {e}")
        return False

async def clear_user_state(storage, user_id: int, chat_id: int = None, bot_id: int = None) -> bool:
    """
    Safely clear user's FSM state and data in Redis

    Args:
        storage: RedisStorage instance
        user_id: Telegram user ID
        chat_id: Optional chat ID (defaults to user_id for private chats)
        bot_id: Bot ID

    Returns:
        True if successful, False otherwise
    """
    try:
        chat_id = chat_id or user_id
        bot_id = bot_id or storage.bot_id if hasattr(storage, 'bot_id') else None
        key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)

        await storage.set_state(key=key, state=None)
        await storage.set_data(key=key, data={})
        return True
    except Exception as e:
        logger.error(f"Error clearing FSM state for user {user_id}: {e}")
        return False