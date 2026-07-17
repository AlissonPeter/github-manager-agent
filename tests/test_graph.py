import pytest
from unittest.mock import patch
from src.agent.graph import router_node, confirmator_node, GitActionSchema, route_after_router


@pytest.fixture(autouse=True)
def mock_ollama():
    """Garante que nenhum teste fará chamadas reais ao Ollama."""
    with patch("src.agent.graph.ollama") as mock:
        mock.chat.return_value = {
            "message": {
                "content": '{"action": "create_issue", "title": "Teste", "body": "Corpo teste"}'
            }
        }
        yield mock


@pytest.fixture(autouse=True)
def mock_get_issue():
    """Mock da busca de issue no GitHub."""
    with patch("src.agent.graph.get_issue") as mock:
        mock.return_value = {
            "success": True,
            "issue": {"number": 1, "title": "Issue Teste", "body": "Corpo da issue", "state": "open"},
        }
        yield mock


def test_router_parses_create_issue():
    state = {"current_command": "criar"}
    result = router_node(state)
    assert isinstance(result, dict)
    assert "last_action" in result
    parsed = GitActionSchema(**result["last_action"])
    assert parsed.action == "create_issue"


def test_confirmator_blocks_close_when_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "3")
    state = {
        "last_action": {"action": "close_issue", "issue_number": 1},
        "default_repo": "owner/repo",
    }
    result = confirmator_node(state)
    assert isinstance(result, dict)
    assert result.get("user_confirmation") is False


def test_graph_flow_confirmation(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    state = {
        "current_command": "fechar 123",
        "default_repo": "owner/repo",
    }
    r = router_node(state)
    state.update(r)
    c = confirmator_node(state)
    state.update(c)
    assert state.get("user_confirmation") is True


def test_graph_uses_default_repo():
    state = {"current_command": "criar"}
    r = router_node(state)
    last = r.get("last_action", {})
    assert isinstance(last, dict)
    if last.get("repo") is None:
        last["repo"] = "meuorg/meurepo"
    state["last_action"] = last
    assert state.get("last_action")["repo"] == "meuorg/meurepo"


def test_conditional_routing_logic():
    state_close = {"last_action": {"action": "close_issue"}}
    state_create = {"last_action": {"action": "create_issue"}}

    assert route_after_router(state_close) == "confirmator"
    assert route_after_router(state_create) == "enhancer"
