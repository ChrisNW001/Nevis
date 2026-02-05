# CLAUDE.md - Nevis Project Guide

## Project Overview

Nevis is a Master AI Assistant that connects everything -- a central orchestration layer that integrates and coordinates multiple AI services, tools, and projects. Currently at v0.1.0 (early development).

## Tech Stack

- **Language:** Python 3.10+
- **Package Manager:** pip + setuptools (src layout)
- **Async Runtime:** asyncio
- **HTTP Client:** httpx
- **Config Validation:** Pydantic v2
- **Environment:** python-dotenv
- **External APIs:** Notion (implemented), OpenAI/Anthropic (planned)

## Project Structure

```
src/nevis/
  __init__.py              # Package root, exports __version__
  main.py                  # Entry point, logging setup, async run loop
  core/
    __init__.py            # Exports NevisAssistant
    assistant.py           # Central orchestrator class
  integrations/
    __init__.py            # Exports NotionIntegration, NotionConfig
    notion.py              # Notion API integration (async)
tests/
  __init__.py
  test_assistant.py        # Tests for NevisAssistant
```

## Quick Reference Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run the assistant
nevis                      # CLI entry point
python -m nevis.main       # Module entry point

# Tests
pytest                     # Run all tests (asyncio_mode=auto)
pytest tests/ -v           # Verbose output

# Linting and formatting
ruff check src/            # Lint
ruff check src/ --fix      # Lint with auto-fix
ruff format src/           # Format code
```

## Code Conventions

- **Async-first:** All I/O operations use async/await. Tests use pytest-asyncio with `asyncio_mode = "auto"`.
- **Type hints:** Modern Python syntax (PEP 604 union types with `|`, `dict[str, Any]` over `Dict[str, Any]`).
- **Line length:** 100 characters max (configured in ruff).
- **Target version:** Python 3.10 (ruff target-version).
- **Logging:** Use `logging.getLogger(__name__)` per module. Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
- **Config:** Environment-based via python-dotenv. Use Pydantic `BaseModel` for config validation. Factory classmethod `from_env()` for constructing from env vars.
- **Exports:** Each subpackage uses `__all__` in `__init__.py` to define its public API.
- **Test style:** Tests grouped in classes (e.g., `TestNevisAssistant`), use pytest fixtures for setup, async test methods.

## Architecture

### Integration Pattern

New integrations follow this structure:

1. Create `src/nevis/integrations/<name>.py`
2. Define a Pydantic config class (e.g., `NotionConfig`)
3. Create an integration class with:
   - `__init__(self, config)` -- accepts validated config
   - `from_env()` classmethod -- constructs from environment variables
   - `initialize()` async method -- establishes connections
   - `shutdown()` async method -- cleanup
4. Export from `src/nevis/integrations/__init__.py`
5. Register with `NevisAssistant.register_integration(name, instance)`

### Core Orchestration

`NevisAssistant` is the central hub:
- Maintains a registry of integrations (`self.integrations: dict[str, Any]`)
- Routes actions via `execute(action, **kwargs)`
- Manages lifecycle: `initialize()` -> `run()` -> `shutdown()`
- Graceful shutdown iterates all integrations and calls their `shutdown()` methods

## Environment Variables

See `.env.example` for the full template. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_TOKEN` | For Notion | Notion API integration token |
| `NOTION_DEFAULT_DATABASE_ID` | No | Default database for queries |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Configuration

All project config lives in `pyproject.toml`:
- Project metadata and dependencies under `[project]`
- Dev dependencies under `[project.optional-dependencies.dev]`
- Ruff settings under `[tool.ruff]`
- Pytest settings under `[tool.pytest.ini_options]`

## Roadmap

See `docs/ROADMAP.md` for the full capability plan. The seven phases in priority order:

1. **Core Agent Loop** -- LLM provider abstraction, ReAct reasoning, tool system, context management
2. **Memory & Planning** -- Working/long-term memory, agentic RAG, plan-and-execute
3. **Observability** -- OpenTelemetry tracing, structured audit logs, metrics
4. **Multi-Agent** -- Subagent spawning, orchestration patterns, A2A protocol
5. **Guardrails** -- Prompt shields, PII detection, RBAC, sandboxed execution
6. **Interfaces** -- FastAPI REST, WebSocket, Slack/Discord bots, MCP server
7. **Self-Improvement** -- Reflection loops, skill learning, cross-session continuity

## Important Notes

- Never commit `.env` files -- they are gitignored. Use `.env.example` as a template.
- The project uses a `src/` layout -- source code is under `src/nevis/`, not at the repo root.
- Pagination is handled automatically in Notion operations (cursor-based).
- The main run loop (`assistant.run()`) requires `initialize()` to be called first or it raises `RuntimeError`.
