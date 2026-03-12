"""This file contains the LangGraph Agent/workflow and interactions with the LLM."""

from langgraph.constants import START
from langgraph.graph import (
    StateGraph,
)


class PokerGraph:
    def __init__(self, service, state_schema):
        self.service = service
        self.state_schema = state_schema

    def create_swarm(self):
        builder = StateGraph(self.state_schema)
        builder.add_node("dealer", self.service._create_dealer_agent)
        builder.add_node("human_player", lambda state: state)

        max_bots = 5
        ai_names = [f"ai_player_{i}" for i in range(max_bots)]

        for name in ai_names:
            builder.add_node(name, self.service._call_agent)

        builder.add_edge(START, "dealer")
        builder.add_edge("dealer", "human_player")

        # После человека идем к ПЕРВОМУ боту
        builder.add_edge("human_player", ai_names[0])

        # Динамические переходы между ботами
        for i in range(max_bots):
            current_name = ai_names[i]

            if i < max_bots - 1:
                next_name = ai_names[i + 1]
                builder.add_conditional_edges(
                    current_name, self.service._bot_router, {"next": next_name, "human": "human_player"}
                )
            else:
                builder.add_edge(current_name, "human_player")

        return builder.compile(checkpointer=self.service.memory, interrupt_before=["human_player"])
