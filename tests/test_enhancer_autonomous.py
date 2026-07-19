from unittest.mock import patch
import json
from src.agent.graph import enhancer_node, _format_issue_preview, _prompt_edit, _handle_edit_issue


class TestEnhancerNodeTitleGeneration:
    """Testes para geração automática de título no enhancer_node."""

    def test_enhancer_generates_title_from_description(self):
        """Deve gerar título a partir da descrição quando não fornecido."""
        state = {
            "last_action": {
                "action": "create_issue",
                "body": "Bug no login quando usuário digita senha incorreta",
            }
        }

        mock_response = {
            "message": {
                "content": json.dumps({
                    "title": "Bug no login com senha incorreta",
                    "body": (
                        "## Descrição\n"
                        "Bug ao tentar fazer login com senha incorreta.\n\n"
                        "## Critérios de Aceitação\n"
                        "- [ ] Login deve exibir mensagem de erro"
                    )
                })
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama, \
             patch("src.agent.graph._input_multiline", return_value="Bug no login quando usuário digita senha incorreta"):
            mock_ollama.chat.return_value = mock_response
            result = enhancer_node(state)

        assert result["last_action"]["title"] == "Bug no login com senha incorreta"
        assert "## Descrição" in result["last_action"]["body"]

    def test_enhancer_keeps_existing_title(self):
        """Deve manter título existente quando fornecido."""
        state = {
            "last_action": {
                "action": "create_issue",
                "title": "Meu Título Customizado",
                "body": "Descrição da issue",
            }
        }

        mock_response = {
            "message": {
                "content": json.dumps({
                    "title": "Título Melhorado",
                    "body": "Descrição melhorada"
                })
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = mock_response
            result = enhancer_node(state)

        assert result["last_action"]["title"] == "Meu Título Customizado"

    def test_enhancer_suggests_labels(self):
        """Deve sugerir labels com base no conteúdo."""
        state = {
            "last_action": {
                "action": "create_issue",
                "body": "Documentação da API está desatualizada",
            }
        }

        mock_response = {
            "message": {
                "content": json.dumps({
                    "title": "Documentação da API desatualizada",
                    "body": "## Descrição\nA documentação precisa ser atualizada."
                })
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama, \
             patch("src.agent.graph._input_multiline", return_value="Documentação da API está desatualizada"):
            mock_ollama.chat.return_value = mock_response
            result = enhancer_node(state)

        assert result["last_action"]["title"] == "Documentação da API desatualizada"

    def test_enhancer_fallback_when_ollama_unavailable(self):
        """Deve usar descrição original quando Ollama indisponível."""
        state = {
            "last_action": {
                "action": "create_issue",
                "body": "Descrição qualquer",
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama, \
             patch("src.agent.graph._input_multiline", return_value="Descrição qualquer"):
            mock_ollama.chat.side_effect = ConnectionError("Offline")
            result = enhancer_node(state)

        assert result["last_action"]["body"] == "Descrição qualquer"

    def test_enhancer_skips_for_non_create(self):
        """Deve pular processamento para ações que não são create_issue."""
        state = {
            "last_action": {
                "action": "edit_issue",
                "title": "Título",
            }
        }

        result = enhancer_node(state)
        assert result["last_action"]["action"] == "edit_issue"


class TestFormatIssuePreview:
    """Testes para formatação do preview da issue."""

    def test_preview_includes_labels(self):
        """Preview deve incluir labels quando presentes."""
        action_data = {
            "action": "create_issue",
            "title": "Teste",
            "labels": ["bug", "urgent"],
            "body": "Corpo da issue",
        }

        preview = _format_issue_preview(action_data)
        assert "🏷️  Labels: bug, urgent" in preview

    def test_preview_without_labels(self):
        """Preview deve funcionar sem labels."""
        action_data = {
            "action": "create_issue",
            "title": "Teste",
            "body": "Corpo da issue",
        }

        preview = _format_issue_preview(action_data)
        assert "🏷️" not in preview

    def test_preview_edit_with_labels(self):
        """Preview de edição deve incluir labels."""
        action_data = {
            "action": "edit_issue",
            "issue_number": 42,
            "title": "Teste",
            "labels": ["feature"],
        }

        preview = _format_issue_preview(action_data)
        assert "Editar Issue #42" in preview
        assert "🏷️  Labels: feature" in preview


class TestPromptEdit:
    """Testes para o prompt de edição."""

    def test_prompt_edit_keeps_current_values(self):
        """Deve manter valores atuais quando Enter pressionado."""
        action_data = {
            "action": "create_issue",
            "title": "Título Atual",
            "body": "Corpo atual",
            "labels": ["bug"],
        }

        with patch("builtins.input", side_effect=["", "Corpo atual", "", ""]):
            result = _prompt_edit(action_data)

        assert result["title"] == "Título Atual"
        assert result["body"] == "Corpo atual"
        assert result["labels"] == ["bug"]

    def test_prompt_edit_updates_title(self):
        """Deve atualizar título quando fornecido."""
        action_data = {
            "action": "create_issue",
            "title": "Título Antigo",
            "body": "Corpo",
            "labels": [],
        }

        with patch("builtins.input", side_effect=["Novo Título", "Corpo", "", ""]):
            result = _prompt_edit(action_data)

        assert result["title"] == "Novo Título"

    def test_prompt_edit_updates_labels(self):
        """Deve atualizar labels quando fornecidas."""
        action_data = {
            "action": "create_issue",
            "title": "Título",
            "body": "Corpo",
            "labels": ["bug"],
        }

        with patch("builtins.input", side_effect=["", "Corpo", "", "feature, docs", ""]):
            result = _prompt_edit(action_data)

        assert result["labels"] == ["feature", "docs"]


class TestHandleEditIssue:
    """Testes para edição de issues com sugestões LLM."""

    def test_handle_edit_suggests_improvements(self):
        """Deve sugerir melhorias via LLM na edição."""
        last = {
            "action": "edit_issue",
            "issue_number": 1,
        }
        issue_data = {
            "title": "Bug antigo",
            "body": "Descrição antiga",
            "labels": ["bug"],
        }

        mock_response = {
            "message": {
                "content": json.dumps({
                    "title": "Bug melhorado",
                    "body": "Descrição melhorada com detalhes"
                })
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = mock_response
            with patch("builtins.input", side_effect=["Nova descrição do bug", ""]):
                result = _handle_edit_issue(last, issue_data)

        assert result["action"] == "edit_issue"
        assert result["title"] == "Bug melhorado"
        assert result["body"] == "Descrição melhorada com detalhes"
        assert result["labels"] == ["bug"]

    def test_handle_edit_applies_suggestions(self):
        """Deve aplicar sugestões do LLM na edição."""
        last = {
            "action": "edit_issue",
            "issue_number": 1,
        }
        issue_data = {
            "title": "Título Original",
            "body": "Corpo Original",
            "labels": ["bug"],
        }

        mock_response = {
            "message": {
                "content": json.dumps({
                    "title": "Título Sugerido",
                    "body": "Corpo Sugerido"
                })
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = mock_response
            with patch("builtins.input", side_effect=["Nova descrição", ""]):
                result = _handle_edit_issue(last, issue_data)

        assert result["title"] == "Título Sugerido"
        assert result["labels"] == ["bug"]
        assert result["body"] == "Corpo Sugerido"

    def test_handle_edit_keeps_current_on_empty_description(self):
        """Deve manter dados atuais quando descrição vazia."""
        last = {
            "action": "edit_issue",
            "issue_number": 1,
        }
        issue_data = {
            "title": "Título Original",
            "body": "Corpo Original",
            "labels": ["bug"],
        }

        with patch("builtins.input", side_effect=["", "", "", "", ""]):
            result = _handle_edit_issue(last, issue_data)

        assert result["title"] == "Título Original"
        assert result["labels"] == ["bug"]
        assert result["body"] == "Corpo Original"
