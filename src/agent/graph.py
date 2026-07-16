from typing import TypedDict, Optional, Any, Dict
import os
import json
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph as LGStateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


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


def get_gemini_client() -> genai.Client:
    """Retorna o cliente oficial do Google GenAI utilizando a GEMINI_API_KEY."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")
    return genai.Client(api_key=GEMINI_API_KEY)


def router_node(state: AgentState) -> Dict[str, Any]:
    """Nó puro: extrai ação estruturada usando o SDK nativo do Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name,
            contents=f"Extraia os dados estruturados para o seguinte comando: {state['current_command']}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GitActionSchema,
                temperature=0.1,
            ),
        )
        parsed_data = json.loads(response.text)
        parsed = GitActionSchema(**parsed_data)

    except Exception as e:
        print(f"[Aviso] Falha na extração nativa do Gemini, utilizando fallback: {e}")
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
    """Nó puro: executor placeholder."""
    last = state.get("last_action", {})
    action = last.get("action")
    if action == "close_issue" and not state.get("user_confirmation"):
        raise RuntimeError("fechamento de issue abortado pelo usuário")

    updated_action = {**last, "executed": True}
    return {"last_action": updated_action}


def route_after_router(state: AgentState) -> str:
    """Decide se o fluxo vai para confirmação ou direto para execução."""
    action = state.get("last_action", {}).get("action")
    if action == "close_issue":
        return "confirmator"
    return "executor"


def build_graph(default_repo: Optional[str] = None) -> Any:
    """Constrói e compila o grafo do LangGraph sem nenhuma dependência do LangChain."""
    g = LGStateGraph(AgentState)

    g.add_node("router", router_node)
    g.add_node("confirmator", confirmator_node)
    g.add_node("executor", executor_node)

    g.add_edge(START, "router")

    g.add_conditional_edges(
        "router",
        route_after_router,
        {
            "confirmator": "confirmator",
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
    "get_gemini_client",
    "router_node",
    "confirmator_node",
    "executor_node",
    "build_graph",
]
