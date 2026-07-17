import pytest
from unittest.mock import patch
from src.agent.graph import (
    router_node,
    confirmator_node,
    executor_node,
    GitActionSchema,
    route_after_router,
    route_after_enhancer,
    _format_issue_preview,
    _prompt_edit,
)


@pytest.fixture(autouse=True)
def mock_ollama():
    """Garante que nenhum teste fará chamadas reais ao Ollama."""
    with patch("src.agent.graph.ollama") as mock:
        mock.chat.return_value = {
            "message": {
                "content": '{"action": "create_issue", "title": "Teste", "body": "Descrição teste"}'
            }
        }
        yield mock


@pytest.fixture(autouse=True)
def mock_get_config():
    """Mock da configuração do LangGraph."""
    with patch("src.agent.graph.get_config") as mock:
        mock.return_value = {"configurable": {"default_repo": "owner/repo"}}
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


def test_confirmator_confirm():
    state = {"last_action": {"action": "create_issue", "title": "Teste"}}
    with patch("builtins.input", return_value="1"):
        result = confirmator_node(state)
    assert result.get("user_confirmation") is True


def test_confirmator_cancel():
    state = {"last_action": {"action": "create_issue", "title": "Teste"}}
    with patch("builtins.input", return_value="3"):
        result = confirmator_node(state)
    assert result.get("user_confirmation") is False


def test_confirmator_invalid_then_confirm():
    state = {"last_action": {"action": "create_issue", "title": "Teste"}}
    with patch("builtins.input", side_effect=["x", "1"]):
        result = confirmator_node(state)
    assert result.get("user_confirmation") is True


def test_confirmator_edit_then_confirm():
    state = {"last_action": {"action": "edit_issue", "title": "Título Antigo"}}
    with patch("builtins.input", side_effect=["2", "Título Novo", "", "1"]):
        result = confirmator_node(state)
    assert result.get("user_confirmation") is True


def test_format_issue_preview_create():
    data = {"action": "create_issue", "title": "Bug Fix", "repo": "owner/repo"}
    preview = _format_issue_preview(data)
    assert "Criar Nova Issue" in preview
    assert "Bug Fix" in preview
    assert "owner/repo" in preview


def test_format_issue_preview_edit():
    data = {"action": "edit_issue", "issue_number": 42, "title": "Edit"}
    preview = _format_issue_preview(data)
    assert "Editar Issue #42" in preview


def test_format_issue_preview_close():
    data = {"action": "close_issue", "issue_number": 7}
    preview = _format_issue_preview(data)
    assert "Fechar Issue #7" in preview


def test_prompt_edit_keep_current():
    data = {"title": "Original", "body": "Corpo original"}
    with patch("builtins.input", side_effect=["", ""]):
        result = _prompt_edit(data)
    assert result["title"] == "Original"
    assert result["body"] == "Corpo original"


def test_prompt_edit_change_title():
    data = {"title": "Original", "body": "Corpo"}
    with patch("builtins.input", side_effect=["Novo título", ""]):
        result = _prompt_edit(data)
    assert result["title"] == "Novo título"
    assert result["body"] == "Corpo"


def test_executor_blocks_when_not_confirmed():
    state = {
        "last_action": {"action": "create_issue", "repo": "owner/repo", "title": "Test"},
        "user_confirmation": False,
    }
    with pytest.raises(RuntimeError, match="abortada"):
        executor_node(state)


def test_route_after_router_create():
    state = {"last_action": {"action": "create_issue"}}
    assert route_after_router(state) == "enhancer"


def test_route_after_router_edit():
    state = {"last_action": {"action": "edit_issue"}}
    assert route_after_router(state) == "confirmator"


def test_route_after_router_close():
    state = {"last_action": {"action": "close_issue"}}
    assert route_after_router(state) == "confirmator"


def test_route_after_enhancer():
    state = {"last_action": {}}
    assert route_after_enhancer(state) == "confirmator"


def test_graph_flow_create_issue(monkeypatch):
    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    state = {"last_action": {"action": "create_issue", "title": "Teste"}}
    result = confirmator_node(state)
    assert result.get("user_confirmation") is True


def test_graph_flow_close_issue_cancel(monkeypatch):
    inputs = iter(["3"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    state = {"last_action": {"action": "close_issue", "issue_number": 5}}
    result = confirmator_node(state)
    assert result.get("user_confirmation") is False
