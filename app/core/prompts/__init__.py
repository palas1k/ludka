import os
from datetime import datetime

from app.core.config import settings
from app.core.logging import logger


def load_poker_prompt(role: str, **kwargs) -> str:
    """Загружает MD-файл промпта и подставляет в него переменные."""

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", f"poker_{role}.md")

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    logger.info(kwargs)
    # base_params = {
    #     "agent_name": f"{settings.PROJECT_NAME} {role.capitalize()}",
    #     "current_date_and_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    #     "long_term_memory": kwargs.get("long_term_memory", "Нет данных о стиле игры противников."),
    #     "small_blind": kwargs.get("small_blind", "1"),
    #     "big_blind": kwargs.get("big_blind", "2"),
    #     "num_players": kwargs.get("num_players", "0"),
    #     "pot": kwargs.get("pot", "0"),
    #     "board": kwargs.get("board", "нет"),
    #     "cards": kwargs.get("cards", "не розданы"),
    #     "opponent_actions": kwargs.get("opponent_actions", "нет действий"),
    # }

    return template
