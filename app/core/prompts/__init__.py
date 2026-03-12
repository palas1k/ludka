import os
from datetime import datetime

from app.core.config import settings


def load_poker_prompt(role: str, **kwargs) -> str:
    """Загружает MD-файл промпта и подставляет в него переменные."""

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", f"poker_{role}.md")

    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    base_params = {
        "agent_name": f"{settings.PROJECT_NAME} {role.capitalize()}",
        "current_date_and_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "long_term_memory": kwargs.get("long_term_memory", "Нет данных о стиле игры противников."),
    }

    final_kwargs = {**base_params, **kwargs}

    return template.format(**final_kwargs)
