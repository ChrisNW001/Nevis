# Nevis Master Agent -- Capability Roadmap

> A phased plan to bring Nevis from skeleton to state-of-the-art master AI agent.

---

## Current State (v0.1.0)

- Async Python skeleton with lifecycle management (`initialize` / `run` / `shutdown`)
- One integration: Notion (database queries, page CRUD, block ops, search)
- No LLM reasoning, no tool calling, no memory, no external API surface
- Action routing is a stub that echoes back `{"status": "ok"}`

---

## What a Master Agent Must Have

A state-of-the-art master agent is defined by seven capability layers. Each layer builds on the ones below it.

```
  7. Self-Improvement    -- reflection, self-correction, learning
  6. Interfaces          -- REST API, WebSocket, chat, webhooks, MCP server
  5. Guardrails          -- safety filters, PII detection, sandboxing, RBAC
  4. Observability       -- tracing, structured audit logs, metrics
  3. Multi-Agent         -- subagents, role-based delegation, A2A protocol
  2. Memory & Planning   -- working/long-term memory, RAG, plan-and-execute
  1. Core Agent Loop     -- LLM reasoning, tool calling, streaming, context mgmt
  0. Foundation          -- async runtime, config, integrations (YOU ARE HERE)
```

---

## Phase 1 -- Core Agent Loop

**Goal:** Nevis can reason, call tools, and hold a conversation.

### 1.1 LLM Provider Abstraction

Create `src/nevis/llm/` with a provider-agnostic interface.

```
src/nevis/llm/
  __init__.py
  base.py          # Abstract LLMProvider: chat(), stream(), embed()
  anthropic.py     # Claude via Anthropic SDK (messages API)
  openai.py        # GPT via OpenAI SDK (chat completions)
```

- Pydantic config per provider (`AnthropicConfig`, `OpenAIConfig`)
- `from_env()` factory on each provider
- Async streaming via `async for chunk in provider.stream(messages)`
- Model selection, temperature, max_tokens as config
- Token counting and cost tracking per call

### 1.2 ReAct Agent Loop

Implement the core reasoning cycle in `src/nevis/core/agent_loop.py`:

```
while not done:
    1. THINK  -- Send messages + tool results to LLM, get response
    2. ACT    -- If LLM requests tool calls, execute them
    3. OBSERVE -- Append tool results to conversation
    4. CHECK  -- If LLM returns final answer (no tool calls), done
```

- Max iteration limit (default 25) to prevent infinite loops
- Configurable stop conditions
- Error handling: if a tool call fails, feed the error back to the LLM for recovery

### 1.3 Tool System

Create `src/nevis/tools/` with a registry and execution engine.

```
src/nevis/tools/
  __init__.py
  registry.py      # ToolRegistry: register, discover, list tools
  base.py          # @tool decorator, Tool dataclass (name, description, schema, fn)
  builtin/
    web_search.py  # HTTP-based web search
    code_exec.py   # Sandboxed Python execution
    file_ops.py    # Read/write/search files
```

- Tools defined as async functions with a `@tool` decorator
- JSON Schema auto-generated from type hints (Pydantic)
- Tool calls formatted for the LLM provider's function-calling API
- MCP client support: connect to external MCP servers and discover their tools at runtime
- Per-tool timeout and error handling

### 1.4 Context Window Management

- Track token usage per conversation
- Compaction strategy: when context exceeds threshold (e.g., 80% of window), summarize older messages while preserving recent context and key decisions
- Structured scratchpad: agent can write notes to a `scratchpad` field that persists across compaction

### 1.5 Conversation Management

Create `src/nevis/core/conversation.py`:

- `Conversation` class holding a list of typed messages (`system`, `user`, `assistant`, `tool_result`)
- Serialization to/from JSON for persistence
- Fork/branch conversations for parallel exploration

**Deliverable:** Nevis can receive a user message, reason with an LLM, call tools, and return a grounded answer.

---

## Phase 2 -- Memory & Planning

**Goal:** Nevis remembers past interactions and can decompose complex tasks.

### 2.1 Working Memory

- Current conversation context (already in Phase 1)
- Scratchpad for intermediate reasoning and task state
- Active variables / key-value store scoped to current session

### 2.2 Long-Term Memory

Create `src/nevis/memory/`:

```
src/nevis/memory/
  __init__.py
  base.py          # Abstract MemoryStore: store(), retrieve(), search()
  episodic.py      # Past interactions: what happened, what worked, what failed
  semantic.py      # Facts, embeddings, vector search (via chromadb or pgvector)
  procedural.py    # Learned skills, reusable action sequences
```

- **Episodic memory:** Timestamped event log of agent actions + outcomes. Queryable by time range, topic, success/failure.
- **Semantic memory:** Vector store for embeddings. Used for RAG and fact retrieval. Support multiple backends (ChromaDB local, pgvector for production).
- **Procedural memory:** Stored tool chains / action sequences that the agent has learned work well. Can be replayed or adapted.

### 2.3 Agentic RAG

- Retrieval as a tool: the agent decides when to search its knowledge base, not a fixed pipeline step
- Document ingestion pipeline: chunk, embed, store
- Hybrid search: vector similarity + keyword (BM25)
- Source attribution in agent responses

### 2.4 Plan-and-Execute

Create `src/nevis/core/planner.py`:

```
1. DECOMPOSE  -- Given a complex goal, break into ordered sub-tasks
2. EXECUTE    -- Run each sub-task through the agent loop
3. REPLAN     -- If a sub-task fails, revise remaining plan
4. AGGREGATE  -- Combine sub-task results into final answer
```

- Plans represented as a DAG (directed acyclic graph) for parallel execution where possible
- Each sub-task has: description, dependencies, assigned tools, success criteria
- Plan persistence for resumability across sessions

**Deliverable:** Nevis can handle multi-step tasks, recall past interactions, and search a knowledge base.

---

## Phase 3 -- Multi-Agent Orchestration

**Goal:** Nevis can delegate to specialized subagents and coordinate their work.

### 3.1 Subagent System

Create `src/nevis/agents/`:

```
src/nevis/agents/
  __init__.py
  base.py          # BaseAgent: role, tools, system_prompt, constraints
  manager.py       # AgentManager: spawn, monitor, collect results
  router.py        # TaskRouter: match tasks to the best agent
```

- Agent definitions: role (e.g., "researcher", "coder", "reviewer"), available tools, system prompt, constraints
- Spawn subagents as async tasks with isolated conversations
- Collect and aggregate results back to the master agent
- Timeout and cancellation support

### 3.2 Orchestration Patterns

Support multiple coordination modes in `src/nevis/core/orchestrator.py`:

| Pattern | When to Use |
|---------|-------------|
| **Sequential** | Tasks have strict dependencies (A -> B -> C) |
| **Parallel Fan-Out** | Independent tasks can run simultaneously |
| **Pipeline** | Output of one agent feeds into the next |
| **Debate** | Two agents argue opposing sides, master synthesizes |
| **Supervisor** | Master reviews and approves subagent outputs before continuing |

### 3.3 Inter-Agent Communication

- Typed message passing between agents (Pydantic models)
- Shared blackboard for collaborative state
- Event bus for publish/subscribe patterns
- A2A protocol support (Google/Linux Foundation standard) for interop with external agents

**Deliverable:** Nevis can spin up specialized agents, coordinate parallel work, and synthesize results.

---

## Phase 4 -- Observability & Production Hardening

**Goal:** Nevis is debuggable, auditable, and safe to run in production.

### 4.1 Tracing & Metrics

Create `src/nevis/observability/`:

- OpenTelemetry integration with GenAI semantic conventions
- Trace every: LLM call, tool invocation, retrieval step, agent decision
- Nested spans: conversation > turn > llm_call > tool_call
- Metrics: tokens/turn, cost/conversation, latency p50/p95/p99, tool success rate
- Exporters: console (dev), OTLP (production)

### 4.2 Structured Audit Logging

Every agent action logged as:

```json
{
  "timestamp": "...",
  "agent_id": "...",
  "action": "tool_call",
  "tool": "notion.query_database",
  "input": { ... },
  "output": { ... },
  "duration_ms": 142,
  "trigger": "user_request",
  "conversation_id": "..."
}
```

### 4.3 Error Handling & Resilience

- Retry with exponential backoff for transient failures (API rate limits, network errors)
- Circuit breaker pattern for failing integrations
- Graceful degradation: if a tool is unavailable, agent can still reason with remaining tools
- Dead letter queue for failed async tasks

### 4.4 Configuration Management

- Environment-based config (already exists) plus YAML/TOML config files for complex setups
- Config validation at startup (fail fast)
- Secret management: support for env vars, `.env` files, and secret managers (AWS SSM, Vault)

**Deliverable:** Nevis has full observability, structured logs, and resilient error handling.

---

## Phase 5 -- Guardrails & Security

**Goal:** Nevis is safe, respects boundaries, and protects sensitive data.

### 5.1 Input Guardrails

Create `src/nevis/guardrails/`:

```
src/nevis/guardrails/
  __init__.py
  pipeline.py      # GuardrailPipeline: chain of checks before/after LLM calls
  prompt_shield.py # Detect prompt injection attempts
  topic_filter.py  # Keep agent within allowed domains
  pii_detector.py  # Identify and mask PII in inputs/outputs
```

- Pre-LLM checks: prompt injection detection, topic boundaries
- Post-LLM checks: PII masking, toxicity filtering, output validation
- Configurable per-agent (some agents may have stricter rules)

### 5.2 Permission System

- RBAC: define what tools each agent/user can access
- Per-tool permission grants (not platform-level blanket access)
- Human-in-the-loop gates: for high-risk actions (e.g., database writes, external API calls), pause and request user approval
- Approval can be: always-allow, ask-once, ask-every-time, never-allow

### 5.3 Sandboxed Execution

- Code execution in isolated environments (subprocess with resource limits, or containers)
- File system access restrictions
- Network access whitelisting per tool
- Resource limits: CPU time, memory, output size

### 5.4 Rate Limiting

- Per-user, per-agent, and per-tool rate limits
- Token budget per conversation/session
- Cost caps with configurable thresholds and alerts

**Deliverable:** Nevis has layered safety controls, permission management, and sandboxed execution.

---

## Phase 6 -- Interfaces & Ecosystem

**Goal:** Nevis is accessible via multiple channels and interoperable with other systems.

### 6.1 REST API

Create `src/nevis/api/`:

- FastAPI async server
- Endpoints: `POST /chat`, `GET /conversations/{id}`, `POST /tools/{name}`, `GET /agents`
- Streaming responses via SSE (`text/event-stream`)
- API key authentication
- OpenAPI docs auto-generated

### 6.2 WebSocket Interface

- Real-time bidirectional communication
- Streaming token-by-token responses
- Connection lifecycle management (heartbeat, reconnect)

### 6.3 Chat Integrations

- **Slack:** Bot using `slack-bolt` async, event subscriptions, slash commands
- **Discord:** Bot using `discord.py`, slash commands
- **Web chat widget:** Embeddable frontend component

### 6.4 MCP Server

Expose Nevis capabilities as MCP tools so other agents can call Nevis:

- Nevis actions available as MCP tools
- JSON-RPC 2.0 transport
- Tool discovery for external clients

### 6.5 Webhook System

- Register webhook URLs for event notifications
- Events: task_completed, error, approval_needed, agent_spawned
- Retry with exponential backoff on delivery failure
- HMAC signature verification

**Deliverable:** Nevis is accessible via HTTP API, WebSocket, Slack, and can be called by other agents via MCP.

---

## Phase 7 -- Self-Improvement & Learning

**Goal:** Nevis gets better over time.

### 7.1 Reflection Loop

After completing a task:

```
1. EVALUATE  -- Did the result meet the success criteria?
2. CRITIQUE  -- What could be improved? (separate LLM call with evaluator role)
3. REVISE    -- If quality is below threshold, retry with feedback (max 1-2 loops)
4. RECORD    -- Store outcome in episodic memory for future reference
```

- Limit to 1-2 refinement iterations (cost/latency control)
- External verification preferred over self-assessment (e.g., run tests, check API responses)

### 7.2 Skill Learning

- When the agent discovers an effective tool-call sequence, save it as a procedural memory
- Named skills that can be triggered by keyword or pattern matching
- Skill versioning: track which version worked best

### 7.3 User Preference Learning

- Track user feedback (explicit: thumbs up/down; implicit: re-prompts, edits)
- Adapt response style, tool preferences, and verbosity over time
- Per-user preference profiles stored in long-term memory

### 7.4 Cross-Session Continuity

- Structured notes persisted between sessions (key decisions, open tasks, blockers)
- Session initializer that loads relevant context from past sessions
- Project-level memory: understanding of the user's codebase, preferences, and recurring tasks

**Deliverable:** Nevis learns from experience, adapts to users, and maintains continuity across sessions.

---

## Implementation Priority & Dependencies

```
Phase 1 (Core Agent Loop)          <-- START HERE, no dependencies
  |
Phase 2 (Memory & Planning)        <-- requires Phase 1
  |
Phase 3 (Multi-Agent)              <-- requires Phase 1, benefits from Phase 2
  |
Phase 4 (Observability)            <-- can start alongside Phase 2-3
  |
Phase 5 (Guardrails)               <-- requires Phase 1, benefits from Phase 4
  |
Phase 6 (Interfaces)               <-- requires Phase 1, benefits from all above
  |
Phase 7 (Self-Improvement)         <-- requires Phase 2 (memory), benefits from Phase 4
```

**Recommended order:** 1 -> 2 -> 4 -> 3 -> 5 -> 6 -> 7

Observability (Phase 4) is pulled forward because debugging agent behavior without tracing is painful. Ship it before multi-agent complexity.

---

## Key Technical Decisions to Make

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Primary LLM | Claude, GPT-4, local models | Claude (Anthropic SDK) as default, GPT-4 as fallback |
| Vector store | ChromaDB, pgvector, Pinecone | ChromaDB for dev, pgvector for production |
| API framework | FastAPI, Litestar, Starlette | FastAPI (ecosystem, async, OpenAPI) |
| Message queue | Redis Streams, RabbitMQ, Kafka | Redis Streams for simplicity, Kafka at scale |
| MCP implementation | Custom, official SDK | Official `mcp` Python SDK |
| Tracing | OpenTelemetry, custom | OpenTelemetry (industry standard) |
| Task persistence | SQLite, PostgreSQL, Redis | SQLite for dev, PostgreSQL for production |

---

## Suggested New Dependencies

### Phase 1
- `anthropic>=0.40.0` -- Claude API client
- `openai>=1.50.0` -- OpenAI API client
- `tiktoken>=0.7.0` -- Token counting

### Phase 2
- `chromadb>=0.5.0` -- Vector store (dev/local)
- `rank-bm25>=0.2.2` -- BM25 keyword search

### Phase 3
- `mcp>=1.0.0` -- MCP Python SDK

### Phase 4
- `opentelemetry-api>=1.27.0` -- Tracing API
- `opentelemetry-sdk>=1.27.0` -- Tracing SDK
- `opentelemetry-exporter-otlp>=1.27.0` -- OTLP exporter

### Phase 6
- `fastapi>=0.115.0` -- REST API
- `uvicorn>=0.32.0` -- ASGI server
- `slack-bolt>=1.20.0` -- Slack integration
