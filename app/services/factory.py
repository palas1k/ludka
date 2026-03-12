from langgraph.graph.state import CompiledStateGraph

from app.core.langgraph.graph import PokerGraph
from app.schemas.poker import PokerState
from app.services.poker import PokerService


class GraphFactory:
    @staticmethod
    async def create_poker_game() -> CompiledStateGraph:
        poker_service = PokerService()

        engine = PokerGraph(service=poker_service, state_schema=PokerState)

        return engine.create_swarm()
