from typing import TypedDict, Optional, Any, Dict
import os
import json
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph as LGStateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_config

import ollama

from src.agent.github_tool import execute_github_action

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

    except Exception as e:
        print(f"[Aviso] Falha na extração com Ollama, utilizando fallback: {e}")
        text = state["current_command"].lower()
        if any(w in text for w in ["fech", "close", "encerr"]):
            parsed = GitActionSchema(action="close_issue")
        elif any(w in text for w in ["cria", "create", "novo", "nova"]):
            parsed = GitActionSchema(action="create_issue", title=state["current_command"])
        elif any(w in text for w in ["edit", "altera", "muda", "atualiza"]):
            parsed = GitActionSchema(action="edit_issue")
        else:
            parsed = GitActionSchema(action="create_issue", title=state["current_command"])

    return {"last_action": parsed.model_dump()}


def enhancer_node(state: AgentState) -> Dict[str, Any]:
    """Nó que melhora a descrição da issue e cria checklist usando Ollama."""
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    last = state.get("last_action", {})
    action = last.get("action")

    if action != "create_issue":
        return {"last_action": last}

    title = last.get("title", "")
    body = last.get("body", "")

    if not body:
        body = f"Criar issue sobre: {title}"

    system_prompt = """Você é um assistente especializado em criar issues detalhadas para GitHub.

Analise a descrição fornecida pelo usuário e crie uma descrição melhorada e profissional para uma issue.

Diretrizes:
1. Mantenha a intenção original do usuário
2. Adicione contexto e detalhes relevantes
3. Crie uma seção de checklist com itens de validação
4. Use formatação Markdown
5. Seja claro e conciso

Retorne APENAS o texto da descrição em Markdown, sem nenhum texto adicional ou explicação.

Exemplo de formato:
## Descrição
[Descrição melhorada do problema ou funcionalidade]

## Checklist
- [ ] Item de validação 1
- [ ] Item de validação 2
- [ ] Item de validação 3"""

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


def confirmator_node(state: AgentState) -> Dict[str, Any]:
    """Nó puro: solicita confirmação para ações destrutivas ou de encerramento (`close_issue`)."""
    last = state.get("last_action", {})
    action = last.get("action")
    if action == "close_issue":
        resp = input("🚨 Confirma o fechamento desta issue? (s/n): ")
        ok = str(resp).strip().lower() in {"s", "sim", "y", "yes"}
        return {"user_confirmation": ok}

    return {"user_confirmation": True}


def executor_node(state: AgentState) -> Dict[str, Any]:
    """Nó executor: executa a ação do GitHub via API REST."""
    last = state.get("last_action", {})
    action = last.get("action")

    if action == "close_issue" and not state.get("user_confirmation"):
        raise RuntimeError("fechamento de issue abortado pelo usuário")

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
    if action == "close_issue":
        return "confirmator"
    if action == "create_issue":
        return "enhancer"
    return "executor"


def route_after_enhancer(state: AgentState) -> str:
    """Após melhorar a descrição, vai para execução."""
    return "executor"


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
            "executor": "executor"
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
]
