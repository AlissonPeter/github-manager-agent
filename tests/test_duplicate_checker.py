from unittest.mock import patch
from src.agent.graph import (
    duplicate_checker,
    _calculate_similarity,
    _extract_task_codes,
)


class TestCalculateSimilarity:
    """Testes para a função _calculate_similarity."""

    def test_identical_strings(self):
        assert _calculate_similarity("bug no login", "bug no login") == 1.0

    def test_completely_different(self):
        assert _calculate_similarity("bug no login", "feature de cadastro") == 0.0

    def test_partial_similarity(self):
        similarity = _calculate_similarity("bug no login do usuário", "bug no logout do usuário")
        assert 0.5 < similarity < 1.0

    def test_empty_strings(self):
        assert _calculate_similarity("", "") == 0.0

    def test_one_empty_string(self):
        assert _calculate_similarity("bug no login", "") == 0.0

    def test_case_insensitive(self):
        assert _calculate_similarity("Bug no Login", "bug no login") == 1.0


class TestExtractTaskCodes:
    """Testes para a função _extract_task_codes."""

    def test_single_code(self):
        assert _extract_task_codes("T-001") == ["T-001"]

    def test_multiple_codes(self):
        assert _extract_task_codes("T-001 e T-012") == ["T-001", "T-012"]

    def test_code_in_title_and_body(self):
        text = "Título T-005\nDescrição com T-010"
        codes = _extract_task_codes(text)
        assert "T-005" in codes
        assert "T-010" in codes

    def test_no_codes(self):
        assert _extract_task_codes("Sem códigos aqui") == []

    def test_invalid_format(self):
        assert _extract_task_codes("T-abc") == []

    def test_zero_padded(self):
        assert _extract_task_codes("T-001") == ["T-001"]

    def test_lowercase_code(self):
        assert _extract_task_codes("t-55") == ["T-55"]

    def test_mixed_case_codes(self):
        assert _extract_task_codes("T-001 e t-002") == ["T-001", "T-002"]


class TestDuplicateChecker:
    """Testes para o nó duplicate_checker."""

    @patch("src.agent.graph.list_open_issues")
    def test_no_duplicates_found(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Feature de cadastro", "body": "", "labels": []}
        ]
        state = {
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Bug no login",
                "body": "Descrição do bug",
            }
        }
        result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Bug no login"

    @patch("src.agent.graph.list_open_issues")
    def test_duplicate_title_found_user_confirms(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Bug no login", "body": "", "labels": []}
        ]
        state = {
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Bug no login",
                "body": "Descrição",
            }
        }
        with patch("builtins.input", return_value="1"):
            result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Bug no login"

    @patch("src.agent.graph.list_open_issues")
    def test_duplicate_title_found_user_cancels(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Bug no login", "body": "", "labels": []}
        ]
        state = {
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Bug no login",
                "body": "Descrição",
            }
        }
        with patch("builtins.input", return_value="2"):
            result = duplicate_checker(state)
        assert result.get("user_confirmation") is False

    @patch("src.agent.graph.list_open_issues")
    def test_duplicate_task_code_found(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Feature", "body": "Implementar T-001", "labels": []}
        ]
        state = {
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Nova feature T-001",
                "body": "Descrição",
            }
        }
        with patch("builtins.input", return_value="1"):
            result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Nova feature T-001"

    @patch("src.agent.graph.list_open_issues")
    def test_skips_for_non_create_edit(self, mock_list_issues):
        state = {
            "last_action": {
                "action": "close_issue",
                "repo": "owner/repo",
                "issue_number": 1,
            }
        }
        result = duplicate_checker(state)
        assert "last_action" in result
        mock_list_issues.assert_not_called()

    @patch("src.agent.graph.list_open_issues")
    def test_skips_same_issue_number(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Bug no login", "body": "", "labels": []}
        ]
        state = {
            "last_action": {
                "action": "edit_issue",
                "repo": "owner/repo",
                "issue_number": 1,
                "title": "Bug no login",
                "body": "Descrição",
            }
        }
        result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Bug no login"

    @patch("src.agent.graph.list_open_issues")
    def test_api_error_continues(self, mock_list_issues):
        mock_list_issues.side_effect = Exception("API Error")
        state = {
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Bug no login",
                "body": "Descrição",
            }
        }
        result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Bug no login"

    @patch("src.agent.graph.list_open_issues")
    def test_detects_task_code_from_current_command(self, mock_list_issues):
        mock_list_issues.return_value = [
            {"number": 1, "title": "Feature", "body": "Implementar T-55", "labels": []}
        ]
        state = {
            "current_command": "criar T-55 sobre bug no login",
            "last_action": {
                "action": "create_issue",
                "repo": "owner/repo",
                "title": "Bug no login",
                "body": "Descrição",
            }
        }
        with patch("builtins.input", return_value="1"):
            result = duplicate_checker(state)
        assert result["last_action"]["title"] == "Bug no login"
