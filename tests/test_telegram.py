import pytest
import requests
from unittest.mock import patch, MagicMock
from src.agent.telegram_tool import (
    get_telegram_config,
    send_telegram_message,
    notify_github_action,
)


class TestGetTelegramConfig:
    """Testes para a função de configuração do Telegram."""

    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    def test_get_config_success(self):
        """Deve retornar configurações válidas."""
        config = get_telegram_config()
        assert config["token"] == "test_token"
        assert config["chat_id"] == "123456"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_config_missing_token(self):
        """Deve levantar erro quando TELEGRAM_TOKEN não está definido."""
        with pytest.raises(RuntimeError, match="TELEGRAM_TOKEN"):
            get_telegram_config()

    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token"}, clear=True)
    def test_get_config_missing_chat_id(self):
        """Deve levantar erro quando TELEGRAM_CHAT_ID não está definido."""
        with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID"):
            get_telegram_config()


class TestSendTelegramMessage:
    """Testes para a função de envio de mensagem."""

    @patch("src.agent.telegram_tool._get_session")
    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    def test_send_message_success(self, mock_get_session):
        """Deve enviar mensagem com sucesso."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"message_id": 123}}
        mock_session.post.return_value = mock_response

        result = send_telegram_message("Teste de mensagem")

        assert result["success"] is True
        assert result["message_id"] == 123
        mock_session.post.assert_called_once()

    @patch("src.agent.telegram_tool._get_session")
    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    def test_send_message_unauthorized(self, mock_get_session):
        """Deve levantar erro com token inválido."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.post.return_value = mock_response

        with pytest.raises(RuntimeError, match="Token do Telegram inválido"):
            send_telegram_message("Teste")

    @patch("src.agent.telegram_tool._get_session")
    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    def test_send_message_bad_request(self, mock_get_session):
        """Deve levantar erro com formatação inválida."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_session.post.return_value = mock_response

        with pytest.raises(RuntimeError, match="formatação da mensagem"):
            send_telegram_message("Teste")

    @patch("src.agent.telegram_tool._get_session")
    @patch.dict("os.environ", {"TELEGRAM_TOKEN": "test_token", "TELEGRAM_CHAT_ID": "123456"})
    def test_send_message_connection_error(self, mock_get_session):
        """Deve levantar erro de conexão."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection error")

        with pytest.raises(RuntimeError, match="conexão"):
            send_telegram_message("Teste")


class TestNotifyGithubAction:
    """Testes para a função de notificação de ação do GitHub."""

    @patch("src.agent.telegram_tool.send_telegram_message")
    def test_notify_create_issue(self, mock_send):
        """Deve notificar criação de issue com sucesso."""
        mock_send.return_value = {"success": True, "message_id": 123}

        action_data = {
            "action": "create_issue",
            "repo": "owner/repo",
            "title": "Nova Issue",
            "issue_number": 1,
            "result": {"issue": {"number": 1}},
        }

        result = notify_github_action(action_data)

        assert result["notified"] is True
        mock_send.assert_called_once()

    @patch("src.agent.telegram_tool.send_telegram_message")
    def test_notify_edit_issue(self, mock_send):
        """Deve notificar edição de issue com sucesso."""
        mock_send.return_value = {"success": True, "message_id": 124}

        action_data = {
            "action": "edit_issue",
            "repo": "owner/repo",
            "title": "Issue Editada",
            "issue_number": 2,
        }

        result = notify_github_action(action_data)

        assert result["notified"] is True
        mock_send.assert_called_once()

    @patch("src.agent.telegram_tool.send_telegram_message")
    def test_notify_close_issue(self, mock_send):
        """Deve notificar fechamento de issue com sucesso."""
        mock_send.return_value = {"success": True, "message_id": 125}

        action_data = {
            "action": "close_issue",
            "repo": "owner/repo",
            "title": "Issue Fechada",
            "issue_number": 3,
        }

        result = notify_github_action(action_data)

        assert result["notified"] is True
        mock_send.assert_called_once()

    @patch("src.agent.telegram_tool.send_telegram_message")
    def test_notify_send_failure(self, mock_send):
        """Deve retornar notificado=False quando envio falha."""
        mock_send.side_effect = Exception("Erro de envio")

        action_data = {
            "action": "create_issue",
            "repo": "owner/repo",
            "title": "Nova Issue",
            "issue_number": 1,
            "result": {"issue": {"number": 1}},
        }

        result = notify_github_action(action_data)

        assert result["notified"] is False
        assert "error" in result
