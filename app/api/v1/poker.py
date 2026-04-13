from fastapi import APIRouter, Request

from app.schemas.poker import NewGameSchema, PokerMoveSchema

router = APIRouter()


@router.post("/start")
async def start_game(request: Request, data: NewGameSchema):
    broker = request.app.state.broker

    result = await broker.call_poker_ai(
        session_id=data.session_id,
        task_type="START_GAME",
        payload={"messages": [("user", "Начни раздачу")], "num_players": data.num_players},
    )

    last_msg = result["messages"][-1]

    log_content = last_msg.get("content") if isinstance(last_msg, dict) else last_msg

    return {"log": [log_content]}


@router.post("/play")
async def play_turn(request: Request, data: PokerMoveSchema):
    broker = request.app.state.broker

    payload = {"messages": [("user", data.user_message)]}

    try:
        # Это вызов RPC: он создаст временную очередь и будет ждать ответа 60с
        result = await broker.call_poker_ai(session_id=data.session_id, task_type="PLAYER_MOVE", payload=payload)
        messages = result.get("messages", [])
        if not messages:
            return {"events": [], "pot": result.get("pot"), "board": result.get("board")}

        last_message = messages[-1]

        content = last_message.get("content") if isinstance(last_message, dict) else last_message

        return {
            "events": [content],
            "pot": result.get("pot"),
            "board": result.get("board"),
        }
    except Exception as e:
        return {"error": f"Ошибка при получении ответа от ИИ: {e!s}"}


@router.post("/clear")
async def clear_game(request: Request, session_id: str):
    broker = request.app.state.broker
    await broker.clear_session(session_id)
    return {"status": "request_sent", "session_id": session_id}
