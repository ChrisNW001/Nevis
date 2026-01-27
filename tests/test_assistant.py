"""Tests for the core assistant."""

import pytest
from nevis.core.assistant import NevisAssistant


@pytest.fixture
def assistant():
    """Create a fresh assistant instance."""
    return NevisAssistant()


class TestNevisAssistant:
    """Tests for NevisAssistant class."""

    async def test_initialize(self, assistant):
        """Test assistant initialization."""
        assert not assistant._initialized
        await assistant.initialize()
        assert assistant._initialized

    async def test_register_integration(self, assistant):
        """Test registering an integration."""
        mock_integration = {"name": "test"}
        assistant.register_integration("test", mock_integration)
        assert "test" in assistant.integrations

    async def test_execute(self, assistant):
        """Test executing an action."""
        await assistant.initialize()
        result = await assistant.execute("test_action", param="value")
        assert result["status"] == "ok"
        assert result["action"] == "test_action"

    async def test_shutdown(self, assistant):
        """Test assistant shutdown."""
        await assistant.initialize()
        await assistant.shutdown()
        assert not assistant._initialized
