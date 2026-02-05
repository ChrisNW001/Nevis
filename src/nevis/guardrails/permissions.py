"""Permission system -- RBAC and human-in-the-loop approval gates."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    ALWAYS_ALLOW = "always_allow"
    ASK_ONCE = "ask_once"
    ASK_EVERY_TIME = "ask_every_time"
    NEVER_ALLOW = "never_allow"


class ToolPermission(BaseModel):
    """Permission configuration for a specific tool."""

    tool_name: str
    permission: Permission = Permission.ASK_EVERY_TIME
    allowed_agents: list[str] = Field(default_factory=list)  # empty = all agents
    allowed_users: list[str] = Field(default_factory=list)  # empty = all users
    requires_approval: bool = False


class PermissionManager:
    """Manages RBAC and per-tool permission grants.

    Supports human-in-the-loop approval gates for high-risk actions.
    """

    def __init__(self):
        self._tool_permissions: dict[str, ToolPermission] = {}
        self._approved_once: set[str] = set()  # tool names approved via ask_once
        self._approval_callback: Any | None = None  # async fn(tool, args) -> bool

    def set_tool_permission(self, perm: ToolPermission) -> None:
        """Set permission for a tool."""
        self._tool_permissions[perm.tool_name] = perm

    def set_approval_callback(self, callback: Any) -> None:
        """Set the human-in-the-loop approval callback.

        Should be an async function: (tool_name, arguments) -> bool
        """
        self._approval_callback = callback

    async def check_permission(
        self,
        tool_name: str,
        agent_id: str = "",
        user_id: str = "",
        arguments: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check if a tool call is permitted. Returns (allowed, reason)."""
        perm = self._tool_permissions.get(tool_name)

        # No explicit permission set: default allow
        if perm is None:
            return True, "no_restriction"

        # Check agent allowlist
        if perm.allowed_agents and agent_id not in perm.allowed_agents:
            return False, f"Agent '{agent_id}' not in allowed list for tool '{tool_name}'"

        # Check user allowlist
        if perm.allowed_users and user_id not in perm.allowed_users:
            return False, f"User '{user_id}' not in allowed list for tool '{tool_name}'"

        # Check permission level
        if perm.permission == Permission.ALWAYS_ALLOW:
            return True, "always_allow"

        if perm.permission == Permission.NEVER_ALLOW:
            return False, f"Tool '{tool_name}' is never allowed"

        if perm.permission == Permission.ASK_ONCE:
            if tool_name in self._approved_once:
                return True, "previously_approved"
            approved = await self._request_approval(tool_name, arguments)
            if approved:
                self._approved_once.add(tool_name)
                return True, "user_approved"
            return False, "user_denied"

        if perm.permission == Permission.ASK_EVERY_TIME:
            approved = await self._request_approval(tool_name, arguments)
            return (True, "user_approved") if approved else (False, "user_denied")

        return True, "default_allow"

    async def _request_approval(
        self, tool_name: str, arguments: dict[str, Any] | None
    ) -> bool:
        """Request human approval for a tool call."""
        if self._approval_callback:
            return await self._approval_callback(tool_name, arguments or {})
        # Default: log and allow (no human in the loop configured)
        logger.warning(f"No approval callback set. Auto-approving tool '{tool_name}'")
        return True

    def get_allowed_tools(self, agent_id: str = "", user_id: str = "") -> list[str]:
        """List tools that are definitely allowed for given agent/user."""
        allowed = []
        for name, perm in self._tool_permissions.items():
            if perm.permission == Permission.NEVER_ALLOW:
                continue
            if perm.allowed_agents and agent_id not in perm.allowed_agents:
                continue
            if perm.allowed_users and user_id not in perm.allowed_users:
                continue
            allowed.append(name)
        return allowed
