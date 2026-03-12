import asyncio
import json
import uuid

import aio_pika
from aio_pika import Message, connect

from app.core.logging import logger


class PokerBroker:
    def __init__(self, url: str):
        self.url = url
        self.connection = None
        self.channel = None

    async def connect(self):
        self.connection = await connect(self.url)
        self.channel = await self.connection.channel()

        await self.channel.declare_queue("poker_tasks", durable=True)

    async def publish_move(self, session_id: str, task_type: str, payload: dict):
        """Отправляет данные в очередь"""
        data = {"session_id": session_id, "task_type": task_type, **payload}
        await self.channel.default_exchange.publish(
            Message(body=json.dumps(data).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="poker_tasks",
        )

    async def process_task(self, message: aio_pika.IncomingMessage, graph, broker):
        async with message.process():
            body = json.loads(message.body)
            payload = body.get("payload")
            session_id = body.get("session_id")
            config = {"configurable": {"thread_id": session_id}}

            # 1. Запуск LangGraph
            result = await graph.ainvoke(payload, config=config)

            # 2. Сериализация (LangGraph сообщения -> список строк/словарей)
            # Нам нужно превратить объекты BaseMessage в обычный текст для JSON
            messages_to_send = []
            for m in result.get("messages", []):
                if hasattr(m, "content"):
                    messages_to_send.append({"role": m.type, "content": m.content})
                else:
                    messages_to_send.append(m)

            response_payload = {"messages": messages_to_send, "pot": result.get("pot"), "board": result.get("board")}

            # 3. Отправка ответа в callback-очередь (reply_to)
            if message.reply_to:
                await broker.channel.default_exchange.publish(
                    aio_pika.Message(body=json.dumps(response_payload).encode(), correlation_id=message.correlation_id),
                    routing_key=message.reply_to,
                )

    async def call_poker_ai(self, session_id: str, task_type: str, payload: dict):
        """
        Отправляет задачу и ЖДЕТ ответа от ИИ (RPC)
        """
        # 1. Создаем временную эксклюзивную очередь для получения ответа
        # exclusive=True значит, что очередь удалится, когда мы закроем соединение
        callback_queue = await self.channel.declare_queue(exclusive=True)

        # Уникальный ID запроса, чтобы не перепутать ответы разных игроков
        corr_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        # 2. Функция-обработчик ответа
        async def on_response(message: aio_pika.IncomingMessage):
            if message.correlation_id == corr_id:
                # Кладем результат в future, чтобы основной поток проснулся
                future.set_result(json.loads(message.body))

        # Начинаем слушать временную очередь
        consumer_tag = await callback_queue.consume(on_response, no_ack=True)

        # 3. Публикуем задачу в общую очередь 'poker_tasks'
        data = {"session_id": session_id, "task_type": task_type, "payload": payload}

        logger.info("call_poker_ai")

        await self.channel.default_exchange.publish(
            Message(
                body=json.dumps(data).encode(),
                reply_to=callback_queue.name,  # Указываем Воркеру, куда слать ответ
                correlation_id=corr_id,  # Помечаем запрос
            ),
            routing_key="poker_tasks",
        )

        # 4. Ждем ответа (ставим 60 сек, покерные боты могут думать долго)
        try:
            return await asyncio.wait_for(future, timeout=60.0)
        finally:
            # Обязательно чистим за собой
            await callback_queue.cancel(consumer_tag)
            await callback_queue.delete()
