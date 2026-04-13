import random
import re
from typing import ClassVar, Literal

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
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
        # 1. Загружаем текущие данные из стейта
        board = list(state.board)
        street = state.street
        new_pot = state.pot
        new_stacks = list(state.player_stacks) or [1000] * state.num_players
        current_hands = dict(state.hands)

        # --- ЛОГИКА РАЗДАЧИ ---
        if not current_hands:
            # САМОЕ НАЧАЛО: Раздаем руки всем игрокам
            current_hands = PokerDeck.deal_hands(state.num_players)

            # Списываем блайнды (только один раз в начале игры!)
            actual_sb = min(new_stacks[0], state.small_blind)
            new_stacks[0] -= actual_sb
            actual_bb = min(new_stacks[1], state.big_blind)
            new_stacks[1] -= actual_bb
            new_pot = actual_sb + actual_bb

            opponent_actions_text = "Блайнды поставлены. Ждем вашего хода."
        else:
            used_cards = []
            for h in current_hands.values():
                used_cards.extend([c.strip() for c in h.split(",")])
            used_cards.extend(board)

            # Переходим на следующую улицу и докладываем карты
            if street == "preflop":
                board = self.get_remaining_cards(3, used_cards)
                street = "flop"
            elif street == "flop":
                board.extend(self.get_remaining_cards(1, used_cards))
                street = "turn"
            elif street == "turn":
                board.extend(self.get_remaining_cards(1, used_cards))
                street = "river"

            opponent_actions_text = "Торги на прошлой улице завершены. Карты открыты."

        # --- РАБОТА С LLM ---
        prompt_text = load_poker_prompt(role="dealer")
        prompt_template = PromptTemplate.from_template(prompt_text)
        chain = prompt_template | self.llm_service.get_llm() | StrOutputParser()

        payload = {
            "chat_history": state.messages,
            "current_player_idx": 0,
            "num_players": state.num_players,
            "cards": f"Ваша рука: [{current_hands}]",
            "board": f"[{', '.join(board)}]" if board else "На столе пусто",
            "pot": f"Текущий банк: {new_pot} фишек",
            "street": street,
            "small_blind": state.small_blind,
            "big_blind": state.big_blind,
            "opponent_actions": opponent_actions_text,
        }

        response = await chain.ainvoke(payload)

        # --- ВОЗВРАТ ОБНОВЛЕННОГО СТЕЙТА ---
        return {
            "messages": [response],
            "pot": new_pot,
            "player_stacks": new_stacks,
            "hands": current_hands,
            "board": board,
            "street": street,
            "llm_calls": state.llm_calls + 1,
            "current_player_idx": 0,  # После выхода карт ход всегда у человека (позиция 0)
        }

    def get_remaining_cards(self, count: int, exclude: list):
        """Вспомогательный метод: берет случайные карты, которых нет в exclude"""
        full_deck = [f"{r}{s}" for r in PokerDeck.ranks for s in PokerDeck.suits]
        remaining = [c for c in full_deck if c not in exclude]
        random.shuffle(remaining)
        return [remaining.pop() for _ in range(count)]

    def _router(self, state: PokerState) -> Literal["human_player", "ai_player", "__end__"]:
        """Главный мозг графа: решает кто ходит следующим"""
        print(f"DEBUG: Router check. Current player: {state.current_player_idx}, LLM calls: {state.llm_calls}")

        if state.llm_calls >= 20 or (state.messages and "showdown" in state.messages[-1].content.lower()):
            return END

        if state.current_player_idx == 0:
            return "human_player"
        print(state)
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


class PokerDeck:
    ranks: ClassVar[list[str]] = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suits: ClassVar[list[str]] = ["♠", "♣", "♥", "♦"]

    @classmethod
    def _get_full_deck(cls):
        return [f"{r}{s}" for r in cls.ranks for s in cls.suits]

    @classmethod
    def deal_hands(cls, num_players: int):
        """Раздает карты игрокам (начало префлопа)."""
        deck = cls._get_full_deck()
        random.shuffle(deck)

        hands = {}
        hands["human"] = f"{deck.pop()}, {deck.pop()}"
        for i in range(1, num_players):
            hands[f"ai_{i}"] = f"{deck.pop()}, {deck.pop()}"
        return hands

    @classmethod
    def get_remaining_cards(cls, count: int, exclude: list):
        """Добирает N карт для стола, которых нет в exclude."""
        deck = [c for c in cls._get_full_deck() if c not in exclude]
        random.shuffle(deck)
        return [deck.pop() for _ in range(count)]
