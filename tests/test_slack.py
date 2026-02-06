"""Tests for the Slack integration."""

from unittest.mock import AsyncMock, patch

import pytest
from nevis.integrations.slack import SlackConfig, SlackIntegration


@pytest.fixture
def slack_config():
    """Create a test Slack configuration."""
    return SlackConfig(bot_token="xoxb-test-token", default_channel="C0123456789")


@pytest.fixture
def slack(slack_config):
    """Create a Slack integration instance with mocked client."""
    integration = SlackIntegration(config=slack_config)
    integration.client = AsyncMock()
    return integration


class TestSlackConfig:
    """Tests for SlackConfig."""

    def test_required_fields(self):
        config = SlackConfig(bot_token="xoxb-test")
        assert config.bot_token == "xoxb-test"
        assert config.default_channel is None

    def test_optional_fields(self):
        config = SlackConfig(bot_token="xoxb-test", default_channel="C123")
        assert config.default_channel == "C123"


class TestSlackIntegration:
    """Tests for SlackIntegration."""

    def test_from_env_missing_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
                SlackIntegration.from_env()

    def test_from_env_success(self):
        env = {"SLACK_BOT_TOKEN": "xoxb-env-token", "SLACK_DEFAULT_CHANNEL": "C999"}
        with patch.dict("os.environ", env, clear=True):
            integration = SlackIntegration.from_env()
            assert integration.config.bot_token == "xoxb-env-token"
            assert integration.config.default_channel == "C999"

    async def test_initialize(self, slack):
        slack.client.auth_test.return_value = {"user": "testbot"}
        await slack.initialize()
        assert slack._initialized is True
        slack.client.auth_test.assert_awaited_once()

    async def test_initialize_failure(self, slack):
        slack.client.auth_test.side_effect = Exception("auth failed")
        with pytest.raises(Exception, match="auth failed"):
            await slack.initialize()
        assert slack._initialized is False

    async def test_shutdown(self, slack):
        slack._initialized = True
        await slack.shutdown()
        assert slack._initialized is False

    async def test_send_message(self, slack):
        slack.client.chat_postMessage.return_value = AsyncMock(
            data={"ok": True, "ts": "1234.5678"}
        )
        result = await slack.send_message("Hello!")
        slack.client.chat_postMessage.assert_awaited_once_with(
            channel="C0123456789", text="Hello!"
        )
        assert result["ok"] is True

    async def test_send_message_explicit_channel(self, slack):
        slack.client.chat_postMessage.return_value = AsyncMock(
            data={"ok": True, "ts": "1234.5678"}
        )
        await slack.send_message("Hello!", channel="C999")
        slack.client.chat_postMessage.assert_awaited_once_with(channel="C999", text="Hello!")

    async def test_send_message_no_channel(self):
        config = SlackConfig(bot_token="xoxb-test")
        integration = SlackIntegration(config=config)
        with pytest.raises(ValueError, match="No channel"):
            await integration.send_message("Hello!")

    async def test_send_message_with_thread(self, slack):
        slack.client.chat_postMessage.return_value = AsyncMock(data={"ok": True})
        await slack.send_message("Reply", thread_ts="1234.5678")
        slack.client.chat_postMessage.assert_awaited_once_with(
            channel="C0123456789", text="Reply", thread_ts="1234.5678"
        )

    async def test_update_message(self, slack):
        slack.client.chat_update.return_value = AsyncMock(data={"ok": True})
        result = await slack.update_message("C123", "1234.5678", "Updated text")
        slack.client.chat_update.assert_awaited_once_with(
            channel="C123", ts="1234.5678", text="Updated text"
        )
        assert result["ok"] is True

    async def test_delete_message(self, slack):
        slack.client.chat_delete.return_value = AsyncMock(data={"ok": True})
        await slack.delete_message("C123", "1234.5678")
        slack.client.chat_delete.assert_awaited_once_with(channel="C123", ts="1234.5678")

    async def test_add_reaction(self, slack):
        slack.client.reactions_add.return_value = AsyncMock(data={"ok": True})
        await slack.add_reaction("C123", "1234.5678", "thumbsup")
        slack.client.reactions_add.assert_awaited_once_with(
            channel="C123", timestamp="1234.5678", name="thumbsup"
        )

    async def test_get_channel_history(self, slack):
        slack.client.conversations_history.return_value = {
            "messages": [{"text": "hello"}]
        }
        result = await slack.get_channel_history("C123", limit=10)
        assert len(result) == 1
        assert result[0]["text"] == "hello"

    async def test_get_thread_replies(self, slack):
        slack.client.conversations_replies.return_value = {
            "messages": [{"text": "original"}, {"text": "reply"}]
        }
        result = await slack.get_thread_replies("C123", "1234.5678")
        assert len(result) == 2

    async def test_get_user_info(self, slack):
        slack.client.users_info.return_value = {
            "user": {"id": "U123", "name": "testuser"}
        }
        result = await slack.get_user_info("U123")
        assert result["name"] == "testuser"

    async def test_list_channels_single_page(self, slack):
        slack.client.conversations_list.return_value = {
            "channels": [{"id": "C1"}, {"id": "C2"}],
            "response_metadata": {"next_cursor": ""},
        }
        result = await slack.list_channels()
        assert len(result) == 2

    async def test_list_users_single_page(self, slack):
        slack.client.users_list.return_value = {
            "members": [{"id": "U1"}],
            "response_metadata": {"next_cursor": ""},
        }
        result = await slack.list_users()
        assert len(result) == 1
