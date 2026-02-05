"""Core Nevis Assistant implementation -- wires all capability layers together."""

import asyncio
import logging
from typing import Any

from nevis.core.agent_loop import AgentLoop
from nevis.core.conversation import Conversation
from nevis.core.planner import Planner
from nevis.tools.registry import ToolRegistry
from nevis.tools.builtin import (
    web_search_tool, code_exec_tool, read_file_tool, write_file_tool, list_dir_tool,
)
from nevis.memory.working import WorkingMemory
from nevis.memory.episodic import EpisodicMemory
from nevis.memory.semantic import SemanticMemory
from nevis.memory.procedural import ProceduralMemory
from nevis.agents.manager import AgentManager
from nevis.observability.tracing import Tracer, console_exporter
from nevis.observability.audit import AuditLogger
from nevis.observability.metrics import MetricsCollector
from nevis.guardrails.pipeline import GuardrailPipeline
from nevis.guardrails.prompt_shield import PromptShield
from nevis.guardrails.pii_detector import PIIDetector
from nevis.guardrails.permissions import PermissionManager
from nevis.self_improve.reflection import ReflectionLoop
from nevis.self_improve.skill_learner import SkillLearner
from nevis.self_improve.continuity import SessionContinuity
from nevis.api.webhooks import WebhookManager

logger = logging.getLogger(__name__)


class NevisAssistant:
    """Master AI Assistant that orchestrates and connects services.

    Wires together all 7 capability layers:
      1. Core Agent Loop (LLM + tools + ReAct)
      2. Memory & Planning
      3. Multi-Agent Orchestration
      4. Observability
      5. Guardrails & Security
      6. Interfaces (API / webhooks)
      7. Self-Improvement
    """

    def __init__(self):
        self.integrations: dict[str, Any] = {}
        self._initialized = False

        # --- Layer 0: Foundation ---
        self.tools = ToolRegistry()

        # --- Layer 1: Core Agent Loop ---
        self._llm = None  # set via configure_llm()
        self.agent_loop: AgentLoop | None = None
        self.conversation = Conversation()

        # --- Layer 2: Memory & Planning ---
        self.working_memory = WorkingMemory()
        self.episodic_memory = EpisodicMemory()
        self.semantic_memory = SemanticMemory()
        self.procedural_memory = ProceduralMemory()
        self.planner: Planner | None = None

        # --- Layer 3: Multi-Agent ---
        self.agent_manager: AgentManager | None = None

        # --- Layer 4: Observability ---
        self.tracer = Tracer(service_name="nevis")
        self.audit = AuditLogger()
        self.metrics = MetricsCollector()

        # --- Layer 5: Guardrails ---
        self.guardrails = GuardrailPipeline()
        self.permissions = PermissionManager()

        # --- Layer 6: Interfaces ---
        self.webhooks = WebhookManager()

        # --- Layer 7: Self-Improvement ---
        self.continuity = SessionContinuity()
        self.reflection: ReflectionLoop | None = None
        self.skill_learner: SkillLearner | None = None

    def configure_llm(self, provider: Any) -> None:
        """Set the LLM provider and wire up dependent layers."""
        self._llm = provider
        self.agent_loop = AgentLoop(
            llm=provider,
            tools=self.tools,
            system_prompt="You are Nevis, a Master AI Assistant. "
            "Use your tools to help the user accomplish their goals.",
        )
        self.planner = Planner(
            llm=provider,
            available_tools=[t.name for t in self.tools.list_tools()],
        )
        self.agent_manager = AgentManager(llm=provider, tools=self.tools)
        self.reflection = ReflectionLoop(llm=provider)
        self.skill_learner = SkillLearner(
            procedural_memory=self.procedural_memory,
            audit_logger=self.audit,
        )

    async def initialize(self):
        """Initialize the assistant and load all layers."""
        logger.info("Initializing Nevis Assistant...")

        # Register built-in tools
        self._register_builtin_tools()

        # Set up observability
        self.tracer.add_exporter(console_exporter)

        # Set up default guardrails
        self.guardrails.add_input_guard(PromptShield())
        self.guardrails.add_guard(PIIDetector(mask=True, block=False))

        # Load integrations
        await self._load_integrations()

        # Load cross-session context
        context = await self.continuity.build_context()
        if context:
            self.conversation.add_system(context)
            logger.info("Loaded context from previous sessions")

        self._initialized = True
        logger.info("Nevis Assistant initialized successfully")

    def _register_builtin_tools(self) -> None:
        """Register the built-in tool set."""
        for tool in [web_search_tool, code_exec_tool, read_file_tool,
                     write_file_tool, list_dir_tool]:
            self.tools.register(tool)
        logger.info(f"Registered {len(self.tools)} built-in tools")

    async def _load_integrations(self):
        """Load and configure service integrations."""
        logger.info("Loading integrations...")

    async def chat(self, message: str) -> str:
        """Send a message through the full pipeline (guardrails -> agent loop -> reflection)."""
        if not self._initialized:
            raise RuntimeError("Assistant not initialized. Call initialize() first.")
        if self.agent_loop is None:
            raise RuntimeError("No LLM configured. Call configure_llm() first.")

        # Input guardrails
        passed, message, results = await self.guardrails.check_input(message)
        if not passed:
            return f"[Blocked] {results[-1].message}"

        # Run agent loop
        with self.tracer.span("chat", input_length=len(message)):
            response = await self.agent_loop.run(message, self.conversation)

        # Output guardrails
        passed, response, results = await self.guardrails.check_output(response)

        # Record in episodic memory
        await self.episodic_memory.store_event(
            action="chat",
            outcome=response[:200],
            success=True,
        )

        self.metrics.record_agent_turn(
            turn_number=len(self.conversation.messages),
            tokens=self.conversation.token_estimate(),
        )

        return response

    async def run(self):
        """Main run loop for the assistant."""
        if not self._initialized:
            raise RuntimeError("Assistant not initialized. Call initialize() first.")

        logger.info("Nevis Assistant is running...")

        while True:
            await self._process_events()

    async def _process_events(self):
        """Process incoming events and requests."""
        await asyncio.sleep(1)

    async def shutdown(self):
        """Gracefully shut down the assistant."""
        logger.info("Shutting down Nevis Assistant...")

        # Cleanup integrations
        for name, integration in self.integrations.items():
            try:
                if hasattr(integration, "shutdown"):
                    await integration.shutdown()
                logger.info(f"Integration '{name}' shut down")
            except Exception as e:
                logger.error(f"Error shutting down integration '{name}': {e}")

        self._initialized = False
        logger.info("Nevis Assistant shut down complete")

    def register_integration(self, name: str, integration: Any):
        """Register a new integration."""
        self.integrations[name] = integration
        logger.info(f"Registered integration: {name}")

    async def execute(self, action: str, **kwargs) -> Any:
        """Execute an action through the appropriate integration."""
        logger.info(f"Executing action: {action}")

        # Check permissions
        allowed, reason = await self.permissions.check_permission(action)
        if not allowed:
            return {"status": "denied", "reason": reason}

        # Route to integration
        if "." in action:
            integration_name, method = action.split(".", 1)
            integration = self.integrations.get(integration_name)
            if integration and hasattr(integration, method):
                with self.tracer.span("execute", action=action):
                    result = await getattr(integration, method)(**kwargs)
                return result

        # Fall back to tool execution
        if action in self.tools:
            return await self.tools.execute(action, **kwargs)

        return {"status": "ok", "action": action, "kwargs": kwargs}
