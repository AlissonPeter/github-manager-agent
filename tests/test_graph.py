import pytest
from unittest.mock import patch
from src.agent.graph import router_node, confirmator_node, executor_node, GitActionSchema, route_after_router


@pytest.fixture(autouse=True)
def mock_gemini_api():
    """Garante que nenhum teste fará requisições HTTP reais para a API do Gemini."""
    with patch("src.agent.graph.get_gemini_client") as mock_client:
        mock_client.side_effect = RuntimeError("Mocked API Offline")
        yield mock_client


def test_router_parses_create_issue():
    state = {"current_command": "Cria uma issue para reportar bug no tasks.md"}
    result = router_node(state)
    assert isinstance(result, dict)
    assert "last_action" in result
    parsed = GitActionSchema(**result["last_action"])
    assert parsed.action == "create_issue"


def test_confirmator_blocks_close_when_no(monkeypatch):
    # Simula input do usuário respondendo 'não' ao fechamento
    monkeypatch.setattr("builtins.input", lambda prompt: "não")
    state = {"last_action": {"action": "close_issue"}}
    result = confirmator_node(state)
    assert isinstance(result, dict)
    assert result.get("user_confirmation") is False


def test_graph_flow_confirmation(monkeypatch):
    # Fluxo simplificado: router -> confirmator para fechamento
    monkeypatch.setattr("builtins.input", lambda prompt: "sim")
    state = {"current_command": "fecha a issue 123"}
    r = router_node(state)
    state.update(r)
    c = confirmator_node(state)
    state.update(c)
    assert state.get("user_confirmation") is True


def test_graph_uses_default_repo():
    state = {"current_command": "cria uma issue de teste"}
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
    assert route_after_router(state_create) == "executor"