import pytest
from unittest.mock import patch
import ollama
from src.agent.graph import router_node, enhancer_node


class TestRouterNodeOllamaOffline:
    """Testes para o comportamento do router_node quando Ollama está indisponível."""

    def test_router_raises_error_on_connection_failure(self):
        """Deve levantar RuntimeError quando Ollama não está acessível."""
        state = {"current_command": "criar"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.side_effect = ConnectionError("Connection refused")

            with pytest.raises(RuntimeError) as excinfo:
                router_node(state)

            assert "Falha ao conectar com Ollama" in str(excinfo.value)
            assert "ollama serve" in str(excinfo.value)

    def test_router_raises_error_on_request_error(self):
        """Deve levantar RuntimeError quando Ollama retorna erro de requisição."""
        state = {"current_command": "criar"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.side_effect = ollama.RequestError("Model not found")

            with pytest.raises(RuntimeError) as excinfo:
                router_node(state)

            assert "Erro ao processar comando com Ollama" in str(excinfo.value)

    def test_router_raises_error_on_json_parse_error(self):
        """Deve levantar RuntimeError quando resposta do Ollama não é JSON válido."""
        state = {"current_command": "criar"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {"content": "This is not valid JSON"}
            }

            with pytest.raises(RuntimeError) as excinfo:
                router_node(state)

            assert "Erro ao processar comando com Ollama" in str(excinfo.value)

    def test_router_raises_error_on_invalid_action(self):
        """Deve levantar RuntimeError quando LLM retorna ação inválida."""
        state = {"current_command": "criar"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {"content": '{"action": "invalid_action"}'}
            }

            with pytest.raises(RuntimeError) as excinfo:
                router_node(state)

            assert "Erro ao processar comando com Ollama" in str(excinfo.value)

    def test_router_valid_command_works_with_ollama(self):
        """Deve funcionar normalmente quando Ollama está disponível."""
        state = {"current_command": "criar"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": '{"action": "create_issue", "title": "Teste"}'
                }
            }

            result = router_node(state)
            assert result["last_action"]["action"] == "create_issue"

    def test_validate_command_still_works_for_known_commands(self):
        """Comandos conhecidos devem funcionar independentemente do fallback do LLM."""
        state = {"current_command": "editar 123"}

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": '{"action": "edit_issue", "issue_number": 123}'
                }
            }

            result = router_node(state)
            assert result["last_action"]["action"] == "edit_issue"
            assert result["last_action"]["issue_number"] == 123


class TestEnhancerNodeOllamaOffline:
    """Testes para o comportamento do enhancer_node quando Ollama está indisponível."""

    def test_enhancer_uses_original_description_on_failure(self):
        """Deve usar descrição original quando Ollama falha."""
        state = {
            "last_action": {
                "action": "create_issue",
                "title": "Teste",
                "body": "Descrição original",
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.side_effect = ConnectionError("Connection refused")

            result = enhancer_node(state)
            assert result["last_action"]["body"] == "Descrição original"

    def test_enhancer_generates_default_body_when_empty(self):
        """Deve manter body vazio quando descrição está vazia (usuário deve informar)."""
        state = {
            "last_action": {
                "action": "create_issue",
                "title": "Teste",
                "body": "",
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.side_effect = ConnectionError("Connection refused")

            result = enhancer_node(state)
            # Agora o body permanece vazio pois o usuário deve informar a descrição
            assert result["last_action"]["body"] == ""

    def test_enhancer_enhances_description_when_ollama_available(self):
        """Deve melhorar descrição quando Ollama está disponível."""
        state = {
            "last_action": {
                "action": "create_issue",
                "title": "Teste",
                "body": "Descrição original",
            }
        }

        with patch("src.agent.graph.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {"content": '{"title": "Título Sugerido", "body": "Descrição melhorada"}'}
            }

            result = enhancer_node(state)
            assert result["last_action"]["title"] == "Teste"
            assert result["last_action"]["body"] == "Descrição melhorada"


class TestDefaultModel:
    """Testes para garantir que o modelo padrão está padronizado."""

    def test_default_model_reads_from_env(self):
        """Modelo padrão deve ler de OLLAMA_MODEL no .env."""
        import os
        from importlib import reload
        import src.agent.graph as graph_module

        with patch.dict(os.environ, {"OLLAMA_MODEL": "custom-model"}):
            reload(graph_module)
            assert graph_module.DEFAULT_OLLAMA_MODEL == "custom-model"

    def test_no_fallback_in_code(self):
        """Código não deve ter fallback para OLLAMA_MODEL."""
        with open("src/agent/graph.py", "r", encoding="utf-8") as f:
            source = f.read()

        # Verifica que não há padrão de fallback como segundo argumento do getenv
        assert 'os.getenv("OLLAMA_MODEL", "llama3.2:3b")' not in source, \
            "Não deve haver fallback hardcoded"
        assert "os.getenv('OLLAMA_MODEL', 'llama3.2:3b')" not in source, \
            "Não deve haver fallback hardcoded"
