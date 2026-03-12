import re
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.core.prompts import load_poker_prompt
from app.schemas.poker import PokerState
from app.services import llm_service


class PokerService:
    def __init__(self):
        self.llm_service = llm_service
        self.memory = MemorySaver()

    async def _call_agent(self, state: PokerState, config):
        current_idx = state.current_player_idx

        my_cards = state.hands.get(str(current_idx), "Карты не получены")
        chain = load_poker_prompt(role="player") | self.llm_service

        response = await chain.ainvoke(
            {
                "chat_history": state.messages,
                "my_cards": my_cards,
                "board": ", ".join(state.board) if state.board else "Пусто",
                "pot": state.pot,
                "player_stack": state.player_stacks[current_idx],
            }
        )

        bet_match = re.search(r"(\d+)", response.content)
        bet_amount = int(bet_match.group(1)) if bet_match else 0

        new_stacks = list(state.player_stacks)
        actual_bet = min(new_stacks[current_idx], bet_amount)
        new_stacks[current_idx] -= actual_bet

        next_idx = (current_idx + 1) % state.num_players  #  noqa

        print("call дошел")

        # return {
        #     "messages": [response],
        #     "pot": state.pot + actual_bet,
        #     "player_stacks": new_stacks,
        #     "llm_calls": state.llm_calls + 1,
        #     "current_player_idx": next_idx
        # }

        return {"messages": [response], "llm_calls": state.get("llm_calls", 0) + 1}

    async def _create_dealer_agent(self, state: PokerState):
        """Логика начала раздачи (как у тебя, но с фиксом инициализации)"""
        sb_amount, bb_amount = state.small_blind, state.big_blind

        new_stacks = list(state.player_stacks)
        if not new_stacks:
            new_stacks = [1000] * state.num_players

        actual_sb = min(new_stacks[0], sb_amount)
        new_stacks[0] -= actual_sb
        actual_bb = min(new_stacks[1], bb_amount)
        new_stacks[1] -= actual_bb

        new_pot = actual_sb + actual_bb

        chain = load_poker_prompt(role="dealer") | self.llm_service

        num_players = state.get("num_players", 1)

        response = await chain.ainvoke(
            {
                "chat_history": state["messages"],
                "current_player_idx": 0,
                "num_players": num_players,
                "cards": state.get("hands", {}).get("human", "Не розданы"),
                "board": state.get("board", "Пусто"),
                "pot": new_pot,
            }
        )

        print(response)

        return {
            "messages": [response],
            "pot": new_pot,
            "player_stacks": new_stacks,
            "llm_calls": state.llm_calls + 1,
            "current_player_idx": 2 % state.num_players,
        }

    def _router(self, state: PokerState) -> Literal["human_player", "ai_player", "__end__"]:
        """Главный мозг графа: решает кто ходит следующим"""
        print(f"DEBUG: Router check. Current player: {state.current_player_idx}, LLM calls: {state.llm_calls}")

        if state.llm_calls >= 20 or (state.messages and "showdown" in state.messages[-1].content.lower()):
            return END

        if state.current_player_idx == 0:
            return "human_player"
        return "ai_player"

    def create_swarm(self):
        builder = StateGraph(PokerState)

        builder.add_node("dealer", self._create_dealer_agent)
        builder.add_node("human_player", lambda state: {"current_player_idx": 0})
        builder.add_node("ai_player", self._call_agent)

        builder.add_edge(START, "dealer")

        # После каждого узла идем в роутер
        builder.add_conditional_edges("dealer", self._router)
        builder.add_conditional_edges("human_player", self._human_node)
        builder.add_conditional_edges("ai_player", self._router)

        return builder.compile(checkpointer=self.memory, interrupt_before=["human_player"])

    def _should_continue(self, state: PokerState):
        # Логика выхода (например, лимит ходов или ключевое слово)
        if state.get("llm_calls", 0) >= 10 or "stop" in state["messages"][-1].content:
            return "end"
        return "continue"

    def _bot_router(self, state: PokerState):
        # ВОТ ЗДЕСЬ мы берем кол-во игроков из State
        # (Вы должны положить его туда в методе start_new_game)
        total_ai_needed = state.get("num_players", 1) - 1

        # Определяем индекс текущего бота из сообщений или спец. поля
        current_idx = state.get("current_player_idx", 0)

        if current_idx < total_ai_needed:
            return "next"
        return "human"

    async def _human_node(self, state: PokerState):
        # Эта нода ничего не делает, просто точка остановки
        return {"current_player_idx": 0}
