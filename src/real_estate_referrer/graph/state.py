"""Estado compartido del grafo LangGraph."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from real_estate_referrer.config import SearchConfig
from real_estate_referrer.models import ScoredProperty
from real_estate_referrer.models.requirements import UserPropertyRequirements

GraphRoute = Literal["end", "coordinate"]


class ReferrerState(TypedDict):
    """Estado del pipeline multi-agente."""

    user_prompt: str
    config: SearchConfig
    requirements: UserPropertyRequirements | None
    scored: list[ScoredProperty]
    approved: list[ScoredProperty]
    round_index: int
    rounds_used: int
    route: GraphRoute
    log: Annotated[list[str], operator.add]
