import json
import logging

import aio_pika

from app.services.broker import PokerBroker

logger = logging.getLogger(__name__)


# async def start_poker_worker(app_state):
#     """
#     Этот метод запускается при старте приложения и слушает RabbitMQ.
#     """
#
#     broker: PokerBroker = app_state.broker
#     graph = app_state.poker_graph
#     queue = await broker.channel.get_queue("poker_tasks")
#
#     async with queue.iterator() as queue_iter:
#         async for message in queue_iter:
#             async with message.process():
#                 data = json.loads(message.body)
#                 session_id = data.get("session_id")
#                 config = {"configurable": {"thread_id": session_id}}
#
#                 # Извлекаем тип задачи: старт или ход
#                 task_type = data.get("task_type")
#                 payload = data.get("payload")
#
#                 logger.info(f"Processing {task_type} for session {session_id}")
#
#                 # Вызываем граф (одинаково для старта и хода)
#                 # LangGraph сам поймет по thread_id, создавать новую игру или продолжать
#                 result = await graph.ainvoke(payload, config=config)
#
#                 # ТУТ ВАЖНО:
#                 # Так как HTTP-ответ уже ушел, результат (ходы ботов)
#                 # нужно отправить игроку в Телеграм через бота напрямую.
#                 await send_updates_to_tg(session_id, result)


async def start_poker_worker(app_state):
    broker: PokerBroker = app_state.broker
    graph = app_state.poker_graph
    queue = await broker.channel.declare_queue("poker_tasks", durable=True)

    logger.info("Worker started, waiting for tasks...")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    body = json.loads(message.body)
                    payload = body.get("payload", {})
                    session_id = body.get("session_id")
                    config = {"configurable": {"thread_id": session_id}}

                    logger.info(f"--- Processing session: {session_id} ---")

                    result = await graph.ainvoke(payload, config=config)

                    messages_to_send = []
                    for m in result.get("messages", []):
                        if hasattr(m, "content"):
                            messages_to_send.append({"role": m.type, "content": str(m.content)})
                        elif isinstance(m, (list, tuple)) and len(m) == 2:
                            messages_to_send.append({"role": m[0], "content": str(m[1])})
                        else:
                            messages_to_send.append({"role": "info", "content": str(m)})

                    response_data = {
                        "messages": messages_to_send,
                        "pot": result.get("pot", 0),
                        "board": result.get("board", []),
                        "status": "success",
                    }

                except Exception as e:
                    logger.error(f"!!! Error in worker: {e!s}", exc_info=True)
                    response_data = {"status": "error", "message": str(e), "messages": []}

                if message.reply_to:
                    await broker.channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(response_data).encode(), correlation_id=message.correlation_id
                        ),
                        routing_key=message.reply_to,
                    )
                    logger.info(f"Sent response (status: {response_data['status']})")


async def send_updates_to_tg(session_id, result):
    # Здесь вызываешь свой Telegram Bot API (aiogram/httpx)
    # и отправляешь result['messages'] пользователю
    pass
