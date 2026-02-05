"""Agent manager -- spawn, monitor, and collect results from subagents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nevis.agents.base import AgentConfig, AgentResult, BaseAgent
from nevis.llm.base import LLMProvider
from nevis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages the lifecycle of subagents: spawning, monitoring, and result collection."""

    def __init__(self, llm: LLMProvider, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self._agents: dict[str, BaseAgent] = {}
        self._results: dict[str, AgentResult] = {}

    def spawn(self, config: AgentConfig) -> BaseAgent:
        """Create and register a new agent."""
        agent = BaseAgent(config=config, llm=self.llm, tools=self.tools)
        self._agents[agent.id] = agent
        logger.info(f"Spawned agent '{config.name}' (id={agent.id}, role={config.role})")
        return agent

    async def run_agent(self, agent: BaseAgent, task: str) -> AgentResult:
        """Run a single agent on a task."""
        result = await asyncio.wait_for(agent.run(task), timeout=agent.config.timeout)
        self._results[agent.id] = result
        return result

    async def run_sequential(
        self, configs_and_tasks: list[tuple[AgentConfig, str]]
    ) -> list[AgentResult]:
        """Run agents sequentially. Each agent receives the previous agent's output as context."""
        results = []
        prev_output = ""
        for config, task in configs_and_tasks:
            agent = self.spawn(config)
            full_task = f"{task}\n\nContext from previous step:\n{prev_output}" if prev_output else task
            result = await self.run_agent(agent, full_task)
            results.append(result)
            prev_output = result.output
        return results

    async def run_parallel(
        self, configs_and_tasks: list[tuple[AgentConfig, str]]
    ) -> list[AgentResult]:
        """Run agents in parallel and collect all results."""
        agents_and_tasks = []
        for config, task in configs_and_tasks:
            agent = self.spawn(config)
            agents_and_tasks.append((agent, task))

        tasks = [self.run_agent(agent, task) for agent, task in agents_and_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_name = configs_and_tasks[i][0].name
                final.append(AgentResult(
                    agent_name=agent_name,
                    success=False,
                    output=str(result),
                    metadata={"error_type": type(result).__name__},
                ))
            else:
                final.append(result)
        return final

    async def run_pipeline(
        self, configs: list[AgentConfig], initial_input: str
    ) -> AgentResult:
        """Pipeline: output of one agent feeds as input to the next."""
        current_input = initial_input
        last_result = AgentResult(agent_name="", success=False, output="")

        for config in configs:
            agent = self.spawn(config)
            last_result = await self.run_agent(agent, current_input)
            if not last_result.success:
                return last_result
            current_input = last_result.output

        return last_result

    async def run_debate(
        self, config_a: AgentConfig, config_b: AgentConfig,
        topic: str, rounds: int = 2,
    ) -> list[AgentResult]:
        """Two agents debate a topic. Returns all debate outputs."""
        agent_a = self.spawn(config_a)
        agent_b = self.spawn(config_b)
        results = []

        prompt = f"Argue FOR this position: {topic}"
        result_a = await self.run_agent(agent_a, prompt)
        results.append(result_a)

        for _ in range(rounds):
            prompt_b = f"Counter this argument about '{topic}':\n{result_a.output}"
            result_b = await self.run_agent(agent_b, prompt_b)
            results.append(result_b)

            prompt_a = f"Respond to this counterargument about '{topic}':\n{result_b.output}"
            result_a = await self.run_agent(agent_a, prompt_a)
            results.append(result_a)

        return results

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def get_result(self, agent_id: str) -> AgentResult | None:
        return self._results.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {"id": a.id, "name": a.config.name, "role": a.config.role}
            for a in self._agents.values()
        ]
