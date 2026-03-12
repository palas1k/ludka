from fastapi import APIRouter, Request

from app.schemas.poker import NewGameSchema, PokerMoveSchema

router = APIRouter()


@router.post("/start")
async def start_game(request: Request, data: NewGameSchema):
    broker = request.app.state.broker

    # Отправляем в Rabbit и ЖДЕМ (RPC)
    result = await broker.call_poker_ai(
        session_id=data.session_id,
        task_type="START_GAME",
        payload={"messages": [("user", "Начни раздачу")], "num_players": data.num_players},
    )

    return {"log": [m["content"] for m in result["messages"]]}


# @router.post("/play")
# async def play_turn(request: Request, data: PokerMoveSchema):
#     broker = request.app.state.broker
#
#     # Формируем задачу на ход
#     payload = {"messages": [("user", data.user_message)]}
#
#     await broker.publish_move(
#         session_id=data.session_id,
#         task_type="PLAYER_MOVE",
#         payload=payload
#     )
#     return {"status": "ok", "message": "Ставка принята, боты думают..."}


@router.post("/play")
async def play_turn(request: Request, data: PokerMoveSchema):
    broker = request.app.state.broker

    payload = {"messages": [("user", data.user_message)]}

    try:
        # Это вызов RPC: он создаст временную очередь и будет ждать ответа 60с
        result = await broker.call_poker_ai(session_id=data.session_id, task_type="PLAYER_MOVE", payload=payload)

        # Теперь тут чистый JSON, который прислал воркер
        return {
            "events": [m["content"] for m in result.get("messages", []) if m["role"] != "user"],
            "pot": result.get("pot"),
            "board": result.get("board"),
        }
    except Exception as e:
        return {"error": f"Ошибка при получении ответа от ИИ: {e!s}"}
