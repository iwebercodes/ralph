"""Tests for AgentPool."""

from __future__ import annotations

import pytest

from ralph.core.agent import AgentResult
from ralph.core.pool import AgentPool


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str = "MockAgent"):
        self._name = name
        self.invoke_count = 0
        self.responses: list[AgentResult] = []
        self.exhausted_after: int | None = None

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
        idx = self.invoke_count
        self.invoke_count += 1
        if idx < len(self.responses):
            return self.responses[idx]
        return AgentResult("Mock output", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        if self.exhausted_after is not None:
            return self.invoke_count > self.exhausted_after
        return False


class TestAgentPoolConstruction:
    """Tests for AgentPool construction."""

    def test_create_with_single_agent(self) -> None:
        """Test creating pool with single agent."""
        agent = MockAgent("Agent1")
        pool = AgentPool([agent])
        assert pool.available_agents == ["Agent1"]

    def test_create_with_multiple_agents(self) -> None:
        """Test creating pool with multiple agents."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2"), MockAgent("Agent3")]
        pool = AgentPool(agents)
        assert pool.available_agents == ["Agent1", "Agent2", "Agent3"]

    def test_create_empty_pool(self) -> None:
        """Test creating empty pool is allowed."""
        pool = AgentPool([])
        assert pool.available_agents == []
        assert pool.is_empty() is True


class TestAgentPoolSelectRandom:
    """Tests for AgentPool.select_random()."""

    def test_returns_agent_from_single_agent_pool(self) -> None:
        """Test returns the agent from single-agent pool."""
        agent = MockAgent("OnlyAgent")
        pool = AgentPool([agent])
        selected = pool.select_random()
        assert selected is agent

    def test_returns_agent_from_multi_agent_pool(self) -> None:
        """Test returns an agent from multi-agent pool."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2")]
        pool = AgentPool(agents)
        selected = pool.select_random()
        assert selected in agents

    def test_raises_when_pool_empty(self) -> None:
        """Test raises ValueError when pool is empty."""
        pool = AgentPool([])
        with pytest.raises(ValueError, match="No agents available"):
            pool.select_random()

    def test_distribution_is_random(self) -> None:
        """Test distribution is approximately random with many calls."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2")]
        pool = AgentPool(agents)

        counts = {"Agent1": 0, "Agent2": 0}
        for _ in range(100):
            selected = pool.select_random()
            counts[selected.name] += 1

        # Both should be selected at least 20 times (expect ~50 each)
        assert counts["Agent1"] >= 20
        assert counts["Agent2"] >= 20


class TestAgentPoolRemove:
    """Tests for AgentPool.remove()."""

    def test_removes_agent_from_pool(self) -> None:
        """Test removes agent from pool."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2")]
        pool = AgentPool(agents)
        pool.remove(agents[0])
        assert pool.available_agents == ["Agent2"]

    def test_pool_size_decreases_after_removal(self) -> None:
        """Test pool size decreases after removal."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2")]
        pool = AgentPool(agents)
        assert len(pool.available_agents) == 2
        pool.remove(agents[0])
        assert len(pool.available_agents) == 1

    def test_removing_twice_is_idempotent(self) -> None:
        """Test removing agent twice does not raise error."""
        agent = MockAgent("Agent1")
        pool = AgentPool([agent])
        pool.remove(agent)
        pool.remove(agent)  # Should not raise
        assert pool.is_empty() is True

    def test_removing_nonexistent_agent_is_idempotent(self) -> None:
        """Test removing non-existent agent does not raise error."""
        agent1 = MockAgent("Agent1")
        agent2 = MockAgent("Agent2")  # Not in pool
        pool = AgentPool([agent1])
        pool.remove(agent2)  # Should not raise
        assert pool.available_agents == ["Agent1"]


class TestAgentPoolIsEmpty:
    """Tests for AgentPool.is_empty()."""

    def test_returns_false_for_non_empty_pool(self) -> None:
        """Test returns False for non-empty pool."""
        pool = AgentPool([MockAgent("Agent1")])
        assert pool.is_empty() is False

    def test_returns_true_for_empty_pool(self) -> None:
        """Test returns True for empty pool."""
        pool = AgentPool([])
        assert pool.is_empty() is True

    def test_returns_true_after_removing_all_agents(self) -> None:
        """Test returns True after removing all agents."""
        agent = MockAgent("Agent1")
        pool = AgentPool([agent])
        pool.remove(agent)
        assert pool.is_empty() is True


class TestAgentPoolAvailableAgents:
    """Tests for AgentPool.available_agents property."""

    def test_returns_empty_list_for_empty_pool(self) -> None:
        """Test returns empty list for empty pool."""
        pool = AgentPool([])
        assert pool.available_agents == []

    def test_returns_list_of_agent_names(self) -> None:
        """Test returns list of agent names."""
        agents = [MockAgent("Claude"), MockAgent("Codex")]
        pool = AgentPool(agents)
        assert pool.available_agents == ["Claude", "Codex"]

    def test_reflects_current_pool_state(self) -> None:
        """Test reflects current pool state after removals."""
        agents = [MockAgent("Agent1"), MockAgent("Agent2")]
        pool = AgentPool(agents)
        pool.remove(agents[0])
        assert pool.available_agents == ["Agent2"]
