import pytest
from unittest.mock import patch, MagicMock
from src.agent.github_tool import (
    get_issue,
    create_issue,
    edit_issue,
    close_issue,
    execute_github_action,
)


@pytest.fixture(autouse=True)
def mock_github_token():
    """Mock do token do GitHub para evitar requisições reais."""
    with patch("src.agent.github_tool.GITHUB_TOKEN", "fake_token_for_testing"):
        yield


def test_create_issue_success():
    """Testa criação bem-sucedida de uma issue."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"number": 1, "title": "Test Issue"}

    with patch("src.agent.github_tool.requests.post", return_value=mock_response):
        result = create_issue("owner/repo", "Test Issue", "Body da issue")
        assert result["success"] is True
        assert result["issue"]["number"] == 1


def test_create_issue_not_found():
    """Testa erro 404 ao criar issue em repositório inexistente."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("src.agent.github_tool.requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Repositório não encontrado"):
            create_issue("owner/repo", "Test Issue")


def test_create_issue_unauthorized():
    """Testa erro 401 com token inválido."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("src.agent.github_tool.requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Token inválido"):
            create_issue("owner/repo", "Test Issue")


def test_edit_issue_success():
    """Testa edição bem-sucedida de uma issue."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"number": 1, "title": "Updated Title"}

    with patch("src.agent.github_tool.requests.patch", return_value=mock_response):
        result = edit_issue("owner/repo", 1, title="Updated Title")
        assert result["success"] is True


def test_edit_issue_no_fields():
    """Testa erro quando nenhum campo é fornecido para edição."""
    with pytest.raises(RuntimeError, match="Nenhum campo para atualizar"):
        edit_issue("owner/repo", 1)


def test_close_issue_success():
    """Testa fechamento bem-sucedido de uma issue."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"number": 1, "state": "closed"}

    with patch("src.agent.github_tool.requests.patch", return_value=mock_response):
        result = close_issue("owner/repo", 1)
        assert result["success"] is True
        assert result["issue"]["state"] == "closed"


def test_execute_github_action_create():
    """Testa execução de ação de criação de issue."""
    action_data = {
        "action": "create_issue",
        "repo": "owner/repo",
        "title": "Nova Issue",
        "body": "Descrição",
        "labels": ["bug", "enhancement"],
    }

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"number": 1}

    with patch("src.agent.github_tool.requests.post", return_value=mock_response):
        result = execute_github_action(action_data)
        assert result["success"] is True


def test_execute_github_action_close():
    """Testa execução de ação de fechamento de issue."""
    action_data = {
        "action": "close_issue",
        "repo": "owner/repo",
        "issue_number": 1,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"number": 1, "state": "closed"}

    with patch("src.agent.github_tool.requests.patch", return_value=mock_response):
        result = execute_github_action(action_data)
        assert result["success"] is True


def test_execute_github_action_unknown():
    """Testa erro para ação desconhecida."""
    action_data = {"action": "delete_issue", "repo": "owner/repo"}

    with pytest.raises(RuntimeError, match="Ação desconhecida"):
        execute_github_action(action_data)


def test_execute_github_action_missing_repo():
    """Testa erro quando repositório não é especificado."""
    action_data = {"action": "create_issue", "title": "Teste"}

    with pytest.raises(RuntimeError, match="Repositório não especificado"):
        execute_github_action(action_data)


def test_execute_github_action_missing_title():
    """Testa erro quando título não é fornecido para criação."""
    action_data = {"action": "create_issue", "repo": "owner/repo"}

    with pytest.raises(RuntimeError, match="Título da issue obrigatório"):
        execute_github_action(action_data)


def test_get_issue_success():
    """Testa busca bem-sucedida de uma issue."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "number": 1,
        "title": "Test Issue",
        "body": "Corpo da issue",
        "state": "open",
    }

    with patch("src.agent.github_tool.requests.get", return_value=mock_response):
        result = get_issue("owner/repo", 1)
        assert result["success"] is True
        assert result["issue"]["title"] == "Test Issue"
        assert result["issue"]["body"] == "Corpo da issue"


def test_get_issue_not_found():
    """Testa erro 404 ao buscar issue inexistente."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("src.agent.github_tool.requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Issue #999 ou repositório não encontrado"):
            get_issue("owner/repo", 999)
