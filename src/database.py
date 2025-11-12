import sqlite3
import asyncio
from src.utils.logger import logger

DB_PATH = 'flirt_ai.db'  # Will be overridden by settings

def init_db():
    """Initialize DB table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  balance REAL DEFAULT 0.0,
                  analyses_available INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    logger.info("✅ DB initialized")

async def get_user_data(user_id: int) -> tuple[float, int]:
    """Get balance and analyses for user (async wrapper)."""
    def _query():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT balance, analyses_available FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return result[0], result[1]
        else:
            # Insert if new user
            c.execute("INSERT INTO users (user_id, balance, analyses_available) VALUES (?, 0.0, 0)",
                      (user_id,))
            conn.commit()
            conn.close()
            return 0.0, 0

    return await asyncio.to_thread(_query)

async def credit_payment(user_id: int, amount: float, analyses_per_payment: int = 3):
    """Credit balance and analyses on payment (async)."""
    def _update():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ?, analyses_available = analyses_available + ? WHERE user_id = ?",
                  (amount, analyses_per_payment, user_id))
        conn.commit()
        conn.close()

    await asyncio.to_thread(_update)
    logger.info(f"💰 Credited {amount} KZT and {analyses_per_payment} analyses to user {user_id}")

async def use_analysis(user_id: int) -> bool:
    """Decrement analyses if available (async); return True if successful."""
    def _decrement():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET analyses_available = analyses_available - 1 WHERE user_id = ? AND analyses_available > 0",
                  (user_id,))
        affected = c.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    success = await asyncio.to_thread(_decrement)
    if success:
        logger.info(f"📊 Used 1 analysis for user {user_id}")
    else:
        logger.warning(f"⚠️ No analyses available for user {user_id}")
    return success