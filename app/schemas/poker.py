from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class PokerState(BaseModel):
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    player_stacks: list[int] = Field(default_factory=list, description="Стеки игроков в фишках")
    hands: dict[str, str] = Field(default_factory=dict)
    board: list[str] = Field(default_factory=list)
    pot: int = Field(default=0)
    small_blind: int = Field(default=10)
    big_blind: int = Field(default=20)
    current_player_idx: int = Field(default=0)
    num_players: int = Field(default=2)
    llm_calls: int = Field(default=0)
    street: Literal["preflop", "flop", "turn", "river", "showdown"] = Field(
        default="preflop", description="Текущий этап раздачи"
    )


class DealerState(BaseModel):
    """Состояние узла дилера с необязательными полями."""

    messages: Annotated[list, add_messages] = Field(default_factory=list)

    system_prompt: str | None = Field(default=None)
    response: str | None = Field(default=None)
    llm_calls: int = Field(default=0)


class PokerMoveSchema(BaseModel):
    """Схема входящего запроса от игрока."""

    session_id: str
    user_message: str


class NewGameSchema(BaseModel):
    """Схема создания новой игры."""

    session_id: str
    num_players: int = 2
