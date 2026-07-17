"""Testes para T-010: Solicitação interativa do repositório."""
from unittest.mock import patch
from src.agent.graph import _validate_repo, _prompt_repo, AgentState


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


class TestPromptRepo:
    """Testes para a função _prompt_repo."""

    @patch("builtins.input", return_value="owner/repo")
    def test_valid_input(self, mock_input):
        assert _prompt_repo() == "owner/repo"

    @patch("builtins.input", side_effect=["invalid", "owner/repo"])
    def test_invalid_then_valid(self, mock_input):
        assert _prompt_repo() == "owner/repo"

    @patch("builtins.input", side_effect=["", "owner/repo"])
    def test_empty_then_valid(self, mock_input):
        assert _prompt_repo() == "owner/repo"

    @patch("builtins.input", side_effect=["ownerrepo", "owner/repo"])
    def test_no_slash_then_valid(self, mock_input):
        assert _prompt_repo() == "owner/repo"


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
