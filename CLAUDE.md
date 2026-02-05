# CLAUDE.md - Nevis Project Guide

## Project Overview

Nevis is a Master AI Assistant that connects everything -- a central orchestration layer with all 7 capability layers implemented. Version 0.2.0.

## Tech Stack

- **Language:** Python 3.10+
- **Package Manager:** pip + setuptools (src layout)
- **Async Runtime:** asyncio
- **HTTP Client:** httpx
- **Config Validation:** Pydantic v2
- **Environment:** python-dotenv
- **LLM Providers:** Anthropic Claude, OpenAI GPT (optional deps `[llm]`)
- **API Framework:** FastAPI (optional dep `[api]`)
- **External APIs:** Notion

## Project Structure

```
src/nevis/
  __init__.py                    # Package root, __version__
  main.py                       # Entry point, logging, async run loop
  core/
    assistant.py                 # NevisAssistant -- wires all 7 layers
    agent_loop.py                # ReAct loop: think -> act -> observe
    conversation.py              # Messages, compaction, forking
    planner.py                   # Plan-and-execute (goal -> DAG of sub-tasks)
  llm/
    base.py                      # Abstract LLMProvider, Message, ToolCall
    anthropic.py                 # AnthropicProvider (Claude)
    openai.py                    # OpenAIProvider (GPT)
  tools/
    base.py                      # @tool decorator, auto JSON Schema
    registry.py                  # ToolRegistry
    builtin/                     # web_search, code_exec, file_ops
  memory/
    base.py                      # Abstract MemoryStore, MemoryEntry
    working.py                   # Scratchpad, variables, task stack
    episodic.py                  # Timestamped action/outcome log
    semantic.py                  # Vector/keyword search, document ingestion
    procedural.py                # Learned Skills with versioning
  agents/
    base.py                      # BaseAgent, AgentConfig
    manager.py                   # Sequential, parallel, pipeline, debate
    router.py                    # Keyword-based task routing
  observability/
    tracing.py                   # Tracer with nested Spans
    audit.py                     # Structured JSONL audit trail
    metrics.py                   # Counters, histograms, gauges
  guardrails/
    pipeline.py                  # Pre/post check chain
    prompt_shield.py             # Prompt injection detection
    pii_detector.py              # PII masking (email, SSN, phone, CC)
    topic_filter.py              # Topic allowlist/blocklist
    permissions.py               # RBAC, human-in-the-loop gates
  api/
    server.py                    # FastAPI REST + SSE + WebSocket
    webhooks.py                  # HMAC-signed webhook delivery with retry
  self_improve/
    reflection.py                # Evaluate -> critique -> revise loop
    skill_learner.py             # Extract skills from audit log
    continuity.py                # Cross-session notes and context
  integrations/
    notion.py                    # Notion API (async)
tests/
  test_assistant.py              # Core assistant tests
  test_tools.py                  # Tool system tests
  test_memory.py                 # Memory store tests
  test_guardrails.py             # Guardrails and permissions tests
  test_observability.py          # Tracing, audit, metrics tests
```

## Quick Reference Commands

```bash
# Install
pip install -e ".[dev]"           # Full dev (all extras + test/lint)
pip install -e ".[llm]"           # LLM providers only
pip install -e ".[api]"           # FastAPI server only

# Run
nevis                             # CLI entry point
python -m nevis.main              # Module entry point
uvicorn nevis.api.server:create_app --factory --reload  # API server

# Test
pytest                            # All tests (asyncio_mode=auto)
pytest tests/test_guardrails.py   # Specific module

# Lint
ruff check src/                   # Lint
ruff check src/ --fix             # Auto-fix
ruff format src/                  # Format
```

## Code Conventions

- **Async-first:** All I/O uses async/await. Tests use pytest-asyncio with `asyncio_mode = "auto"`.
- **Type hints:** Modern PEP 604 (`str | None`, `dict[str, Any]`).
- **Line length:** 100 chars (ruff). **Target:** Python 3.10.
- **Logging:** `logging.getLogger(__name__)` per module.
- **Config:** Pydantic `BaseModel` + `from_env()` factory classmethod.
- **Exports:** `__all__` in every `__init__.py`.
- **Tests:** Grouped in classes, pytest fixtures, async methods.
- **Tools:** `@tool` decorator auto-generates JSON Schema from type hints.
- **Memory:** JSONL files in `.nevis/` (gitignored). Swap backends for prod.

## Architecture -- The 7 Layers

`NevisAssistant` wires all layers. Chat pipeline:

```
User message
  -> GuardrailPipeline.check_input (prompt shield, PII mask)
  -> AgentLoop.run (ReAct: LLM -> tool calls -> observe -> repeat)
  -> GuardrailPipeline.check_output (PII mask)
  -> EpisodicMemory.store_event
  -> MetricsCollector.record_agent_turn
  -> Response
```

| Layer | Package | Key Classes |
|-------|---------|-------------|
| 1. Agent Loop | `core/`, `llm/`, `tools/` | `AgentLoop`, `LLMProvider`, `ToolRegistry` |
| 2. Memory | `memory/` | `WorkingMemory`, `EpisodicMemory`, `SemanticMemory`, `ProceduralMemory`, `Planner` |
| 3. Multi-Agent | `agents/` | `BaseAgent`, `AgentManager`, `TaskRouter` |
| 4. Observability | `observability/` | `Tracer`, `AuditLogger`, `MetricsCollector` |
| 5. Guardrails | `guardrails/` | `GuardrailPipeline`, `PromptShield`, `PIIDetector`, `PermissionManager` |
| 6. Interfaces | `api/` | `create_app`, `WebhookManager` |
| 7. Self-Improve | `self_improve/` | `ReflectionLoop`, `SkillLearner`, `SessionContinuity` |

### Adding a New Tool

```python
from nevis.tools.base import tool

@tool(name="my_tool", description="Does something useful.")
async def my_tool(param: str, count: int = 5) -> dict:
    return {"result": param * count}
```

### Adding a New Integration

1. Create `src/nevis/integrations/<name>.py`
2. Pydantic config + class with `from_env()`, `initialize()`, `shutdown()`
3. Export from `__init__.py`, register with `assistant.register_integration()`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Claude | Anthropic API key |
| `OPENAI_API_KEY` | For GPT | OpenAI API key |
| `NOTION_TOKEN` | For Notion | Notion integration token |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Important Notes

- Never commit `.env` files -- gitignored. Use `.env.example`.
- `src/` layout -- source under `src/nevis/`, not repo root.
- LLM providers lazy-load (no hard dep on anthropic/openai at import).
- Call `configure_llm(provider)` before `initialize()` to enable agent loop.
- Memory persists to `.nevis/` (JSONL). Swap for DB in production.
- See `docs/ROADMAP.md` for the original planning document.
