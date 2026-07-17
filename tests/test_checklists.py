import pytest
from unittest.mock import patch
from src.agent.graph import (
    _has_checklists,
    _mark_checklists,
    confirmator_node,
)


def test_has_checklists_true():
    body = "## Critérios\n- [ ] Item 1\n- [ ] Item 2"
    assert _has_checklists(body) is True


def test_has_checklists_false():
    body = "## Descrição\nTeste sem checklist"
    assert _has_checklists(body) is False


def test_has_checklists_empty():
    assert _has_checklists("") is False


def test_has_checklists_all_marked():
    body = "- [x] Item 1\n- [x] Item 2"
    assert _has_checklists(body) is False


def test_mark_checklists():
    body = "- [ ] Item 1\n- [ ] Item 2"
    result = _mark_checklists(body)
    assert result == "- [x] Item 1\n- [x] Item 2"


def test_mark_checklists_mixed():
    body = "- [x] Já feito\n- [ ] Pendente"
    result = _mark_checklists(body)
    assert result == "- [x] Já feito\n- [x] Pendente"


def test_mark_checklists_no_change():
    body = "Sem checklist aqui"
    result = _mark_checklists(body)
    assert result == body


def test_confirmator_close_with_checklists_yes(monkeypatch):
    mock_issue = {
        "number": 5,
        "title": "Issue Teste",
        "body": "## Critérios\n- [ ] Item 1\n- [ ] Item 2",
        "state": "open",
    }
    with patch("src.agent.graph.get_issue", return_value={"success": True, "issue": mock_issue}):
        inputs = iter(["1", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        state = {
            "last_action": {"action": "close_issue", "issue_number": 5, "repo": "owner/repo"},
            "default_repo": "owner/repo",
        }
        result = confirmator_node(state)
        assert result.get("user_confirmation") is True
        assert "- [x] Item 1" in result["last_action"]["body"]
        assert "- [x] Item 2" in result["last_action"]["body"]


def test_confirmator_close_with_checklists_no(monkeypatch):
    mock_issue = {
        "number": 5,
        "title": "Issue Teste",
        "body": "## Critérios\n- [ ] Item 1",
        "state": "open",
    }
    with patch("src.agent.graph.get_issue", return_value={"success": True, "issue": mock_issue}):
        inputs = iter(["2", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        state = {
            "last_action": {"action": "close_issue", "issue_number": 5, "repo": "owner/repo"},
            "default_repo": "owner/repo",
        }
        result = confirmator_node(state)
        assert result.get("user_confirmation") is True
        assert "body" not in result["last_action"] or "- [ ]" in result["last_action"].get("body", "")


def test_confirmator_close_without_checklists(monkeypatch):
    mock_issue = {
        "number": 3,
        "title": "Issue Simples",
        "body": "Sem checklist",
        "state": "open",
    }
    with patch("src.agent.graph.get_issue", return_value={"success": True, "issue": mock_issue}):
        inputs = iter(["1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        state = {
            "last_action": {"action": "close_issue", "issue_number": 3, "repo": "owner/repo"},
            "default_repo": "owner/repo",
        }
        result = confirmator_node(state)
        assert result.get("user_confirmation") is True


def test_confirmator_close_cancel_after_checklist(monkeypatch):
    mock_issue = {
        "number": 5,
        "title": "Issue Teste",
        "body": "- [ ] Item 1",
        "state": "open",
    }
    with patch("src.agent.graph.get_issue", return_value={"success": True, "issue": mock_issue}):
        inputs = iter(["1", "3"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        state = {
            "last_action": {"action": "close_issue", "issue_number": 5, "repo": "owner/repo"},
            "default_repo": "owner/repo",
        }
        result = confirmator_node(state)
        assert result.get("user_confirmation") is False
