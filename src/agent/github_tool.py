import os
import requests
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE = "https://api.github.com"


def get_headers() -> Dict[str, str]:
    """Retorna os headers de autenticação para a API do GitHub."""
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN não encontrado nas variáveis de ambiente.")
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def create_issue(repo: str, title: str, body: Optional[str] = None) -> Dict[str, Any]:
    """Cria uma issue no GitHub."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    payload = {"title": title}
    if body:
        payload["body"] = body

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 201:
        return {"success": True, "issue": response.json()}
    elif response.status_code == 404:
        raise RuntimeError(f"Repositório não encontrado: {repo}")
    elif response.status_code == 401:
        raise RuntimeError("Token inválido ou sem permissão.")
    else:
        raise RuntimeError(f"Erro ao criar issue: {response.status_code} - {response.text}")


def get_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    """Busca os dados de uma issue existente no GitHub."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    response = requests.get(url, headers=get_headers())

    if response.status_code == 200:
        return {"success": True, "issue": response.json()}
    elif response.status_code == 404:
        raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
    elif response.status_code == 401:
        raise RuntimeError("Token inválido ou sem permissão.")
    else:
        raise RuntimeError(f"Erro ao buscar issue: {response.status_code} - {response.text}")


def edit_issue(repo: str, issue_number: int, title: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
    """Edita uma issue existente no GitHub."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body

    if not payload:
        raise RuntimeError("Nenhum campo para atualizar foi fornecido.")

    response = requests.patch(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        return {"success": True, "issue": response.json()}
    elif response.status_code == 404:
        raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
    elif response.status_code == 401:
        raise RuntimeError("Token inválido ou sem permissão.")
    else:
        raise RuntimeError(f"Erro ao editar issue: {response.status_code} - {response.text}")


def close_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    """Fecha uma issue no GitHub (muda status para closed)."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    payload = {"state": "closed"}

    response = requests.patch(url, json=payload, headers=get_headers())

    if response.status_code == 200:
        return {"success": True, "issue": response.json()}
    elif response.status_code == 404:
        raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
    elif response.status_code == 401:
        raise RuntimeError("Token inválido ou sem permissão.")
    else:
        raise RuntimeError(f"Erro ao fechar issue: {response.status_code} - {response.text}")


def execute_github_action(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Executa uma ação do GitHub com base nos dados estruturados."""
    action = action_data.get("action")
    repo = action_data.get("repo")
    issue_number = action_data.get("issue_number")
    title = action_data.get("title")
    body = action_data.get("body")

    if not repo:
        raise RuntimeError("Repositório não especificado (campo 'repo' obrigatório).")

    if action == "create_issue":
        if not title:
            raise RuntimeError("Título da issue obrigatório para criação.")
        return create_issue(repo, title, body)

    elif action == "edit_issue":
        if not issue_number:
            raise RuntimeError("Número da issue obrigatório para edição.")
        return edit_issue(repo, issue_number, title, body)

    elif action == "close_issue":
        if not issue_number:
            raise RuntimeError("Número da issue obrigatório para fechamento.")
        if body:
            edit_issue(repo, issue_number, body=body)
        return close_issue(repo, issue_number)

    else:
        raise RuntimeError(f"Ação desconhecida: {action}")


__all__ = [
    "get_issue",
    "create_issue",
    "edit_issue",
    "close_issue",
    "execute_github_action",
]
