"""FastAPI REST API and WebSocket server for Nevis."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# --- Request/Response models ---

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    usage: dict[str, Any] = Field(default_factory=dict)


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    tool_name: str
    result: Any
    success: bool


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str


class HealthResponse(BaseModel):
    status: str
    version: str


# --- App factory ---

def create_app(nevis_app: Any = None) -> Any:
    """Create the FastAPI application.

    Args:
        nevis_app: The Nevis application instance providing agent_loop, tools, etc.
    """
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import StreamingResponse
    except ImportError:
        raise ImportError("Install fastapi: pip install fastapi uvicorn")

    app = FastAPI(
        title="Nevis API",
        description="Master AI Assistant API",
        version="0.1.0",
    )

    # Store state
    conversations: dict[str, Any] = {}

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(status="ok", version="0.1.0")

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Send a message and get a response."""
        if nevis_app is None:
            return ChatResponse(
                conversation_id="",
                response="Nevis app not initialized",
            )

        conv_id = request.conversation_id or uuid.uuid4().hex[:12]
        conversation = conversations.get(conv_id)

        if conversation is None:
            from nevis.core.conversation import Conversation
            conversation = Conversation(id=conv_id)
            conversations[conv_id] = conversation

        if request.stream:
            async def generate():
                async for token in nevis_app.agent_loop.run_streaming(
                    request.message, conversation
                ):
                    yield f"data: {json.dumps({'token': token})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        response = await nevis_app.agent_loop.run(request.message, conversation)
        return ChatResponse(
            conversation_id=conv_id,
            response=response,
        )

    @app.get("/conversations/{conversation_id}")
    async def get_conversation(conversation_id: str):
        conv = conversations.get(conversation_id)
        if conv is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Conversation not found")
        return json.loads(conv.to_json())

    @app.post("/tools/{tool_name}", response_model=ToolCallResponse)
    async def call_tool(tool_name: str, request: ToolCallRequest):
        """Execute a tool directly."""
        if nevis_app is None:
            return ToolCallResponse(tool_name=tool_name, result=None, success=False)

        result = await nevis_app.tools.execute(tool_name, **request.arguments)
        is_error = isinstance(result, dict) and "error" in result
        return ToolCallResponse(
            tool_name=tool_name,
            result=result,
            success=not is_error,
        )

    @app.get("/tools")
    async def list_tools():
        if nevis_app is None:
            return {"tools": []}
        return {"tools": nevis_app.tools.get_schemas()}

    @app.get("/agents", response_model=list[AgentInfo])
    async def list_agents():
        if nevis_app is None or not hasattr(nevis_app, "agent_manager"):
            return []
        return [
            AgentInfo(**info) for info in nevis_app.agent_manager.list_agents()
        ]

    @app.get("/metrics")
    async def metrics():
        if nevis_app is None or not hasattr(nevis_app, "metrics"):
            return {}
        return nevis_app.metrics.snapshot()

    # --- WebSocket endpoint ---

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        conv_id = uuid.uuid4().hex[:12]

        from nevis.core.conversation import Conversation
        conversation = Conversation(id=conv_id)
        conversations[conv_id] = conversation

        try:
            await websocket.send_json({"type": "connected", "conversation_id": conv_id})

            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                user_message = msg.get("message", "")
                if not user_message:
                    continue

                if nevis_app is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Nevis app not initialized",
                    })
                    continue

                # Stream response token-by-token
                await websocket.send_json({"type": "start"})
                full_response = ""

                async for token in nevis_app.agent_loop.run_streaming(
                    user_message, conversation
                ):
                    full_response += token
                    await websocket.send_json({"type": "token", "content": token})

                await websocket.send_json({
                    "type": "done",
                    "content": full_response,
                    "conversation_id": conv_id,
                })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {conv_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close()

    return app
