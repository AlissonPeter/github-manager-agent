from typing import TypedDict, Optional, Any, Dict
import os
import json
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph as LGStateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_config

import ollama

from src.agent.github_tool import execute_github_action, get_issue

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class AgentState(TypedDict):
    current_command: str
    last_action: Dict[str, Any]
    user_confirmation: bool


class GitActionSchema(BaseModel):
    action: str = Field(..., description="Ação a ser executada: create_issue | edit_issue | close_issue")
    repo: Optional[str] = Field(None, description="Nome do repositório no formato 'owner/repo' (opcional)")
    issue_number: Optional[int] = Field(None, description="Número da issue no GitHub (obrigatório se edit ou close)")
    title: Optional[str] = Field(None, description="Título da issue (necessário se create ou edit)")
    body: Optional[str] = Field(None, description="Conteúdo ou descrição do corpo da issue (opcional)")

    @field_validator("action")
    def validate_action(cls, v: str) -> str:
        allowed = {"create_issue", "edit_issue", "close_issue"}
        if v not in allowed:
            raise ValueError(f"ação inválida: {v}")
        return v


def _extract_number(words: list) -> int:
    """Extrai o primeiro número encontrado nas palavras."""
    for w in words:
        if w.isdigit():
            return int(w)
    return None


def _validate_command(command: str, parsed: GitActionSchema) -> GitActionSchema:
    """Valida o comando do usuário e ajusta os dados extraídos."""
    words = command.strip().lower().split()
    action_word = words[0] if words else ""

    is_create = action_word in {"criar", "create", "cria"}
    is_edit = action_word in {"editar", "edit", "alterar", "altera", "mudar", "muda", "atualizar", "atualiza"}
    is_close = action_word in {"fechar", "close", "encerrar", "encerr", "fecha"}

    if is_create:
        allowed_words = {"issue", "uma", "a", "o", "de", "do", "da", "para", "sobre", "no", "na"}
        extra_words = [w for w in words[1:] if w not in allowed_words and not w.isdigit()]
        if extra_words:
            raise ValueError("Comando inválido. Use: criar (será solicitado título e descrição)")
        return GitActionSchema(action="create_issue")

    if is_edit:
        number = _extract_number(words[1:])
        if not number:
            raise ValueError("Comando inválido. Use: editar <número_da_issue>")
        return GitActionSchema(action="edit_issue", issue_number=number, title=parsed.title, body=parsed.body)

    if is_close:
        number = _extract_number(words[1:])
        if not number:
            raise ValueError("Comando inválido. Use: fechar <número_da_issue>")
        return GitActionSchema(action="close_issue", issue_number=number)

    raise ValueError("Comando não reconhecido. Use: criar, editar <número> ou fechar <número>")


def router_node(state: AgentState) -> Dict[str, Any]:
    """Nó puro: extrai ação estruturada usando Ollama."""
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2")

    system_prompt = """Analise o comando do usuário e extraia os dados em formato JSON.
Retorne APENAS o JSON válido sem nenhum texto adicional.

REGRAS IMPORTANTES:
- NÃO invente repositórios. Se o usuário não mencionou um repositório, NÃO inclua o campo "repo"
- Se não houver descrição, NÃO inclua o campo "body"
- O campo "title" deve conter APENAS o título da issue, sem a palavra "issue"

Schema esperado:
{
  "action": "create_issue" | "edit_issue" | "close_issue",
  "repo": "owner/repo" (APENAS se o usuário mencionou explicitamente),
  "issue_number": número (obrigatório para edit/close),
  "title": "título da issue" (obrigatório para create/edit),
  "body": "descrição da issue" (APENAS se o usuário forneceu uma descrição)
}"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Comando: {state['current_command']}"}
            ],
            options={"temperature": 0.1}
        )

        response_text = response["message"]["content"]
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            response_text = response_text[json_start:json_end]

        parsed_data = json.loads(response_text)
        parsed = GitActionSchema(**parsed_data)

    except Exception:
        parsed = GitActionSchema(action="create_issue")

    validated = _validate_command(state["current_command"], parsed)
    return {"last_action": validated.model_dump()}


def enhancer_node(state: AgentState) -> Dict[str, Any]:
    """Nó que melhora a descrição da issue e cria checklist usando Ollama."""
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    last = state.get("last_action", {})
    action = last.get("action")

    if action != "create_issue":
        return {"last_action": last}

    if not last.get("title"):
        print("\n--- Criar Nova Issue ---")
        title = input("📌 Título da issue: ").strip()
        body = input("📄 Descrição (Enter para pular): ").strip()
        last = {**last, "title": title, "body": body}

    title = last.get("title", "")
    body = last.get("body", "")

    if not body:
        body = f"Criar issue sobre: {title}"

    system_prompt = """Você é um assistente especializado em criar issues detalhadas para GitHub.

Analise a descrição fornecida pelo usuário e crie uma descrição melhorada e profissional para uma issue.

Diretrizes:
1. Mantenha a intenção original do usuário
2. Adicione contexto e detalhes relevantes
3. Crie uma seção de critérios de aceitação com itens de validação
4. Use formatação Markdown
5. Seja claro e conciso

Retorne APENAS o texto da descrição em Markdown, sem nenhum texto adicional ou explicação.

Exemplo de formato:
## Descrição
[Descrição melhorada do problema ou funcionalidade]

## Critérios de Aceitação
- [ ] Critério de aceitação 1
- [ ] Critério de aceitação 2
- [ ] Critério de aceitação 3"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Título: {title}\n\nDescrição original: {body}"}
            ],
            options={"temperature": 0.3}
        )

        enhanced_body = response["message"]["content"].strip()
        updated_action = {**last, "body": enhanced_body}
        return {"last_action": updated_action}

    except Exception as e:
        print(f"[Aviso] Falha ao melhorar descrição, usando descrição original: {e}")
        return {"last_action": last}


def _format_issue_preview(action_data: Dict[str, Any]) -> str:
    """Formata os dados da issue para exibição no terminal."""
    action = action_data.get("action")
    lines = []

    if action == "create_issue":
        lines.append("📝 Criar Nova Issue")
    elif action == "edit_issue":
        lines.append(f"✏️  Editar Issue #{action_data.get('issue_number', '?')}")
    elif action == "close_issue":
        lines.append(f"🔒 Fechar Issue #{action_data.get('issue_number', '?')}")

    if action_data.get("repo"):
        lines.append(f"📦 Repositório: {action_data['repo']}")

    if action_data.get("title"):
        lines.append(f"📌 Título: {action_data['title']}")

    if action_data.get("body"):
        lines.append(f"📄 Descrição:\n{action_data['body']}")

    return "\n".join(lines)


def _prompt_edit(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Solicita ao usuário que edite título e/ou descrição da issue."""
    print(f"\n{'=' * 40}\n{_format_issue_preview(action_data)}\n{'=' * 40}")

    current_title = action_data.get("title", "")
    current_body = action_data.get("body", "")

    print("\n--- Edição da Issue ---")

    print(f"\nTítulo atual: {current_title}")
    new_title = input("Novo título (Enter para manter): ").strip()
    if not new_title:
        new_title = current_title

    print(f"\nDescrição atual:\n{current_body}")
    new_body = input("Nova descrição (Enter para manter): ").strip()
    if not new_body:
        new_body = current_body

    return {**action_data, "title": new_title, "body": new_body}


def confirmator_node(state: AgentState) -> Dict[str, Any]:
    """Nó de confirmação: exibe preview da issue e oferece opções de confirmação, edição ou cancelamento."""
    last = state.get("last_action", {})

    config = get_config()
    default_repo = config.get("configurable", {}).get("default_repo")
    if not last.get("repo") and default_repo:
        last = {**last, "repo": default_repo}

    action = last.get("action")
    repo = last.get("repo")
    issue_number = last.get("issue_number")

    if action in ("edit_issue", "close_issue") and repo and issue_number:
        try:
            result = get_issue(repo, issue_number)
            issue_data = result.get("issue", {})
        except Exception as e:
            raise RuntimeError(f"Issue #{issue_number} não encontrada no repositório {repo}: {e}")

        if action == "edit_issue":
            last = {**last, "title": issue_data.get("title", ""), "body": issue_data.get("body", "")}
            last = _prompt_edit(last)

    preview = _format_issue_preview(last)
    print(f"\n{'=' * 40}\n{preview}\n{'=' * 40}")

    while True:
        resp = input("\nConfirma a operação?\n  1-Confirmar\n  2-Editar\n  3-Cancelar\n→ ").strip()

        if resp == "1":
            return {"last_action": last, "user_confirmation": True}
        elif resp == "2":
            last = _prompt_edit(last)
            print(f"\n{'=' * 40}\n{_format_issue_preview(last)}\n{'=' * 40}")
        elif resp == "3":
            print("❌ Operação cancelada pelo usuário.")
            return {"user_confirmation": False, "last_action": last}
        else:
            print("Opção inválida. Digite 1, 2 ou 3.")


def executor_node(state: AgentState) -> Dict[str, Any]:
    """Nó executor: executa a ação do GitHub via API REST."""
    last = state.get("last_action", {})

    if not state.get("user_confirmation"):
        raise RuntimeError("operação abortada pelo usuário")

    config = get_config()
    default_repo = config.get("configurable", {}).get("default_repo")

    if not last.get("repo") and default_repo:
        last = {**last, "repo": default_repo}

    try:
        result = execute_github_action(last)
        updated_action = {**last, "executed": True, "result": result}
        return {"last_action": updated_action}
    except RuntimeError as e:
        if default_repo and "Repositório não encontrado" in str(e):
            last = {**last, "repo": default_repo}
            result = execute_github_action(last)
            updated_action = {**last, "executed": True, "result": result}
            return {"last_action": updated_action}
        raise RuntimeError(f"Falha na execução da ação GitHub: {e}")


def route_after_router(state: AgentState) -> str:
    """Decide se o fluxo vai para confirmação, enhancer ou direto para execução."""
    action = state.get("last_action", {}).get("action")
    if action == "create_issue":
        return "enhancer"
    return "confirmator"


def route_after_enhancer(state: AgentState) -> str:
    """Após melhorar a descrição, vai para confirmação."""
    return "confirmator"


def build_graph(default_repo: Optional[str] = None) -> Any:
    """Constrói e compila o grafo do LangGraph sem nenhuma dependência do LangChain."""
    g = LGStateGraph(AgentState)

    g.add_node("router", router_node)
    g.add_node("enhancer", enhancer_node)
    g.add_node("confirmator", confirmator_node)
    g.add_node("executor", executor_node)

    g.add_edge(START, "router")

    g.add_conditional_edges(
        "router",
        route_after_router,
        {
            "confirmator": "confirmator",
            "enhancer": "enhancer",
            "executor": "executor"
        }
    )

    g.add_conditional_edges(
        "enhancer",
        route_after_enhancer,
        {
            "confirmator": "confirmator"
        }
    )

    g.add_edge("confirmator", "executor")
    g.add_edge("executor", END)

    memory = MemorySaver()
    app = g.compile(checkpointer=memory)

    if default_repo:
        setattr(app, "default_repo", default_repo)

    return app


__all__ = [
    "AgentState",
    "GitActionSchema",
    "router_node",
    "enhancer_node",
    "confirmator_node",
    "executor_node",
    "build_graph",
    "execute_github_action",
    "_format_issue_preview",
    "_prompt_edit",
]
