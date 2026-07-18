"""Testes para T-012: Comando de histórico de issues."""
from unittest.mock import patch
from src.agent.graph import (
    historico_node,
    router_node,
    _validate_command,
    GitActionSchema,
    route_after_router,
)


class TestHistoricoNode:
    """Testes para a função historico_node."""

    def test_historico_empty(self):
        state = {"history": []}
        with patch("builtins.print"):
            result = historico_node(state)
            assert result == {}

    def test_historico_none(self):
        state = {}
        with patch("builtins.print"):
            result = historico_node(state)
            assert result == {}

    def test_historico_with_entries(self):
        state = {
            "history": [
                {"action": "create_issue", "title": "Bug Fix", "issue_number": 1, "repo": "owner/repo"},
                {"action": "close_issue", "title": "Bug Fix", "issue_number": 1, "repo": "owner/repo"},
            ]
        }
        with patch("builtins.print") as mock_print:
            result = historico_node(state)
            assert result == {}
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("Bug Fix" in call for call in calls)
            assert any("#1" in call for call in calls)

    def test_historico_chronological_order(self):
        state = {
            "history": [
                {"action": "create_issue", "title": "Primeira", "issue_number": 1, "repo": "owner/repo"},
                {"action": "edit_issue", "title": "Segunda", "issue_number": 2, "repo": "owner/repo"},
                {"action": "close_issue", "title": "Terceira", "issue_number": 3, "repo": "owner/repo"},
            ]
        }
        with patch("builtins.print") as mock_print:
            result = historico_node(state)
            assert result == {}
            calls = [str(call) for call in mock_print.call_args_list]
            found_terceira = False
            found_segunda = False
            found_primeira = False
            for call in calls:
                if "Terceira" in call:
                    found_terceira = True
                elif "Segunda" in call:
                    found_segunda = True
                elif "Primeira" in call:
                    found_primeira = True
            assert found_terceira
            assert found_segunda
            assert found_primeira


class TestHistoricoCommand:
    """Testes para o comando histórico no router."""

    def test_validate_command_historico(self):
        command = "histórico"
        parsed = GitActionSchema(action="create_issue")
        result = _validate_command(command, parsed)
        assert result.action == "historico"

    def test_validate_command_historico_variations(self):
        for cmd in ["historico", "history", "hist"]:
            parsed = GitActionSchema(action="create_issue")
            result = _validate_command(cmd, parsed)
            assert result.action == "historico"

    def test_route_after_router_historico(self):
        state = {"last_action": {"action": "historico"}}
        assert route_after_router(state) == "historico"

    def test_router_node_historico(self):
        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": '{"action": "historico"}'
                }
            }
            state = {"current_command": "histórico"}
            result = router_node(state)
            assert result["last_action"]["action"] == "historico"
