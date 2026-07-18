"""Testes para T-010 e T-011: Solicitação interativa e validação do repositório."""
from unittest.mock import patch, MagicMock
import requests
from src.agent.graph import _validate_repo, _prompt_repo, AgentState
from src.agent.github_tool import check_repo_access


class TestValidateRepo:
    """Testes para a função _validate_repo."""

    def test_valid_repo(self):
        assert _validate_repo("owner/repo") is True

    def test_valid_repo_with_hyphens(self):
        assert _validate_repo("my-org/my-repo") is True

    def test_valid_repo_with_underscores(self):
        assert _validate_repo("my_org/my_repo") is True

    def test_empty_repo(self):
        assert _validate_repo("") is False

    def test_none_repo(self):
        assert _validate_repo(None) is False

    def test_missing_slash(self):
        assert _validate_repo("ownerrepo") is False

    def test_missing_owner(self):
        assert _validate_repo("/repo") is False

    def test_missing_repo(self):
        assert _validate_repo("owner/") is False

    def test_multiple_slashes(self):
        assert _validate_repo("owner/repo/extra") is False

    def test_only_slash(self):
        assert _validate_repo("/") is False

    def test_with_spaces(self):
        assert _validate_repo(" owner / repo ") is True


class TestCheckRepoAccess:
    """Testes para a função check_repo_access."""

    @patch("src.agent.github_tool.requests.get")
    @patch("src.agent.github_tool.GITHUB_TOKEN", "test-token")
    def test_repo_with_push_permission(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"permissions": {"push": True, "pull": True, "admin": False}}
        mock_get.return_value = mock_response
        assert check_repo_access("owner/repo") is True

    @patch("src.agent.github_tool.requests.get")
    @patch("src.agent.github_tool.GITHUB_TOKEN", "test-token")
    def test_repo_without_push_permission(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"permissions": {"push": False, "pull": True, "admin": False}}
        mock_get.return_value = mock_response
        assert check_repo_access("owner/repo") is False

    @patch("src.agent.github_tool.requests.get")
    @patch("src.agent.github_tool.GITHUB_TOKEN", "test-token")
    def test_repo_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        assert check_repo_access("owner/nonexistent") is False

    @patch("src.agent.github_tool.requests.get")
    @patch("src.agent.github_tool.GITHUB_TOKEN", "test-token")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError
        import requests as req
        with patch("src.agent.github_tool.requests.get", side_effect=req.exceptions.ConnectionError):
            try:
                check_repo_access("owner/repo")
                assert False, "Deveria ter levantado RuntimeError"
            except RuntimeError as e:
                assert "conexão" in str(e).lower() or "conexao" in str(e).lower()

    @patch("src.agent.github_tool.requests.get")
    @patch("src.agent.github_tool.GITHUB_TOKEN", "test-token")
    def test_timeout_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout
        try:
            check_repo_access("owner/repo")
            assert False, "Deveria ter levantado RuntimeError"
        except RuntimeError as e:
            assert "timeout" in str(e).lower()


class TestPromptRepo:
    """Testes para a função _prompt_repo."""

    @patch("src.agent.graph.check_repo_access", return_value=True)
    @patch("builtins.input", return_value="owner/repo")
    def test_valid_input(self, mock_input, mock_check):
        assert _prompt_repo() == "owner/repo"

    @patch("src.agent.graph.check_repo_access", return_value=True)
    @patch("builtins.input", side_effect=["invalid", "owner/repo"])
    def test_invalid_then_valid(self, mock_input, mock_check):
        assert _prompt_repo() == "owner/repo"

    @patch("src.agent.graph.check_repo_access", return_value=True)
    @patch("builtins.input", side_effect=["", "owner/repo"])
    def test_empty_then_valid(self, mock_input, mock_check):
        assert _prompt_repo() == "owner/repo"

    @patch("src.agent.graph.check_repo_access", return_value=True)
    @patch("builtins.input", side_effect=["ownerrepo", "owner/repo"])
    def test_no_slash_then_valid(self, mock_input, mock_check):
        assert _prompt_repo() == "owner/repo"

    @patch("src.agent.graph.check_repo_access", side_effect=[False, True])
    @patch("builtins.input", side_effect=["owner/nonexistent", "owner/repo"])
    def test_repo_not_exists_then_valid(self, mock_input, mock_check):
        assert _prompt_repo() == "owner/repo"

    @patch("src.agent.graph.check_repo_access", side_effect=[RuntimeError("Erro de conexão"), True])
    @patch("builtins.input", side_effect=["owner/repo", "owner/existing"])
    def test_connection_error_then_valid(self, mock_input, mock_check):
        result = _prompt_repo()
        assert result == "owner/existing"


class TestAgentState:
    """Testes para o AgentState com default_repo."""

    def test_agent_state_has_default_repo(self):
        state: AgentState = {
            "current_command": "criar",
            "last_action": {},
            "user_confirmation": False,
            "default_repo": "owner/repo",
        }
        assert state["default_repo"] == "owner/repo"

    def test_agent_state_default_repo_optional(self):
        state: AgentState = {
            "current_command": "criar",
            "last_action": {},
            "user_confirmation": False,
        }
        assert state.get("default_repo") is None
