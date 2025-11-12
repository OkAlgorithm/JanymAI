def truncate_caption(caption: str, max_length: int = 1000) -> str:
    """Truncate caption to Telegram's limit"""
    if len(caption) <= max_length:
        return caption
    return caption[:max_length - 3] + "..."