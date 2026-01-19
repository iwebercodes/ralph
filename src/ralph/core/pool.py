"""Agent pool for managing multiple AI agents."""

from __future__ import annotations

import contextlib
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ralph.core.agent import Agent


class AgentPool:
    """Pool of agents for rotation when one becomes exhausted."""

    def __init__(self, agents: list[Agent]) -> None:
        """Create a pool from a list of agents.

        Args:
            agents: List of agents to include in the pool
        """
        self._agents: list[Agent] = list(agents)

    def select_random(self) -> Agent:
        """Pick a random agent from the pool.

        Returns:
            A randomly selected agent

        Raises:
            ValueError: If the pool is empty
        """
        if not self._agents:
            raise ValueError("No agents available in pool")
        return random.choice(self._agents)

    def remove(self, agent: Agent) -> None:
        """Remove an agent from the pool.

        This operation is idempotent - removing an agent that's not
        in the pool does nothing.

        Args:
            agent: The agent to remove
        """
        with contextlib.suppress(ValueError):
            self._agents.remove(agent)

    def is_empty(self) -> bool:
        """Check if the pool has no agents remaining.

        Returns:
            True if the pool is empty
        """
        return len(self._agents) == 0

    @property
    def available_agents(self) -> list[str]:
        """Get names of all agents currently in the pool.

        Returns:
            List of agent names
        """
        return [agent.name for agent in self._agents]
