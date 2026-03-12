import asyncio
import logging
import os
import sys

from langchain_core.runnables.graph import MermaidDrawMethod

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 1. Сначала логгер, чтобы видеть ошибки
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("worker")


async def run():
    logger.info(" [1] Инициализация воркера...")

    # Импортируем брокера
    from app.core.config import settings
    from app.services.broker import PokerBroker

    url = os.getenv("BROKER_URL", settings.RABBITMQ_URL)
    broker = PokerBroker(url)
    await broker.connect()
    logger.info(" [2] RabbitMQ подключен")

    from app.services.factory import GraphFactory
    from app.services.worker import start_poker_worker

    logger.info(" [3] Создание графа...")
    poker_graph = await GraphFactory.create_poker_game()

    try:
        # Генерируем PNG через API (метод по умолчанию)
        # Добавляем max_retries, чтобы не падать при разовом сбое сети
        png_data = poker_graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API, max_retries=5, retry_delay=2.0
        )

        with open("graph.png", "wb") as f:  # noqa
            f.write(png_data)
        print("Картинка успешно сохранена в файл graph.png")

    except Exception as e:
        print(f"Не удалось создать PNG через API: {e}")
        print("Используйте текст из print(draw_mermaid()) в https://mermaid.live для ручного сохранения.")

    class State:
        def __init__(self, b, g):
            self.broker = b
            self.poker_graph = g

    logger.info(" [4] Поехали!")
    await start_poker_worker(State(broker, poker_graph))


if __name__ == "__main__":
    asyncio.run(run())
