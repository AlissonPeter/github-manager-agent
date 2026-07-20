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
REQUEST_TIMEOUT = 30


def get_headers() -> Dict[str, str]:
    """Retorna os headers de autenticação para a API do GitHub."""
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN não encontrado nas variáveis de ambiente.")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgenteLangGraph-Alisson",
    }


def check_repo_access(repo: str) -> bool:
    """Verifica se o token tem acesso ao repositório (permissão de escrita)."""
    url = f"{GITHUB_API_BASE}/repos/{repo}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            permissions = data.get("permissions", {})
            return permissions.get("push", False)
        return False
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Erro de conexão com a API do GitHub.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout ao conectar com a API do GitHub.")
    except Exception as e:
        raise RuntimeError(f"Erro ao verificar repositório: {e}")


def create_issue(repo: str, title: str, body: Optional[str] = None, labels: Optional[list] = None) -> Dict[str, Any]:
    """Cria uma issue no GitHub com retry automático."""
    import time

    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    payload = {"title": title}
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = labels

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=get_headers(), timeout=REQUEST_TIMEOUT)

            if response.status_code == 201:
                return {"success": True, "issue": response.json()}
            elif response.status_code == 503:
                last_error = "API do GitHub indisponível (503)"
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            elif response.status_code == 404:
                raise RuntimeError(f"Repositório não encontrado: {repo}")
            elif response.status_code == 401:
                raise RuntimeError("Token inválido ou sem permissão.")
            else:
                raise RuntimeError(f"Erro ao criar issue: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Erro de conexão: {e}"
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        except requests.exceptions.Timeout:
            last_error = "Timeout ao conectar com a API do GitHub"
            if attempt < max_retries - 1:
                time.sleep(1)
                continue

    raise RuntimeError(f"{last_error}. Tente novamente em alguns instantes.")


def get_issue(repo: str, issue_number: int, max_retries: int = 3) -> Dict[str, Any]:
    """Busca os dados de uma issue existente no GitHub com retry automático."""
    import time

    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    last_error = None
    last_response = None
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                return {"success": True, "issue": response.json()}
            elif response.status_code == 503:
                last_error = "API do GitHub indisponível (503)"
                last_response = response
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            elif response.status_code == 404:
                raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
            elif response.status_code == 401:
                raise RuntimeError("Token inválido ou sem permissão.")
            else:
                raise RuntimeError(f"Erro ao buscar issue: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Erro de conexão: {e}"
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
        except requests.exceptions.Timeout:
            last_error = "Timeout ao conectar com a API do GitHub"
            last_exception = TimeoutError("Timeout")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue

    error_details = "\n\n🔍 Detalhes do erro técnico:"
    error_details += f"\n   URL: {url}"
    error_details += f"\n   Headers enviados: {get_headers()}"
    if last_response:
        error_details += f"\n   Status HTTP: {last_response.status_code}"
        error_details += f"\n   Headers resposta: {dict(last_response.headers)}"
        error_details += f"\n   Corpo resposta: {last_response.text[:500]}"
    elif last_exception:
        error_details += f"\n   Exceção: {type(last_exception).__name__}: {last_exception}"
    raise RuntimeError(f"{last_error}.{error_details}")


def edit_issue(
    repo: str, issue_number: int,
    title: Optional[str] = None, body: Optional[str] = None,
    labels: Optional[list] = None
) -> Dict[str, Any]:
    """Edita uma issue existente no GitHub com retry automático."""
    import time

    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    payload = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if labels is not None:
        payload["labels"] = labels

    if not payload:
        raise RuntimeError("Nenhum campo para atualizar foi fornecido.")

    max_retries = 3
    last_error = None
    last_response = None
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = requests.patch(url, json=payload, headers=get_headers(), timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                return {"success": True, "issue": response.json()}
            elif response.status_code == 503:
                last_error = "API do GitHub indisponível (503)"
                last_response = response
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            elif response.status_code == 404:
                raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
            elif response.status_code == 401:
                raise RuntimeError("Token inválido ou sem permissão.")
            else:
                raise RuntimeError(f"Erro ao editar issue: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Erro de conexão: {e}"
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
        except requests.exceptions.Timeout:
            last_error = "Timeout ao conectar com a API do GitHub"
            last_exception = TimeoutError("Timeout")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue

    error_details = "\n\n🔍 Detalhes do erro técnico:"
    error_details += f"\n   URL: {url}"
    error_details += f"\n   Headers enviados: {get_headers()}"
    if last_response:
        error_details += f"\n   Status HTTP: {last_response.status_code}"
        error_details += f"\n   Headers resposta: {dict(last_response.headers)}"
        error_details += f"\n   Corpo resposta: {last_response.text[:500]}"
    elif last_exception:
        error_details += f"\n   Exceção: {type(last_exception).__name__}: {last_exception}"
    raise RuntimeError(f"{last_error}.{error_details}")


def close_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    """Fecha uma issue no GitHub (muda status para closed) com retry automático."""
    import time

    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{issue_number}"
    payload = {"state": "closed"}

    max_retries = 3
    last_error = None
    last_response = None
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = requests.patch(url, json=payload, headers=get_headers(), timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                return {"success": True, "issue": response.json()}
            elif response.status_code == 503:
                last_error = "API do GitHub indisponível (503)"
                last_response = response
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            elif response.status_code == 404:
                raise RuntimeError(f"Issue #{issue_number} ou repositório não encontrado.")
            elif response.status_code == 401:
                raise RuntimeError("Token inválido ou sem permissão.")
            else:
                raise RuntimeError(f"Erro ao fechar issue: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Erro de conexão: {e}"
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
        except requests.exceptions.Timeout:
            last_error = "Timeout ao conectar com a API do GitHub"
            last_exception = TimeoutError("Timeout")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue

    error_details = "\n\n🔍 Detalhes do erro técnico:"
    error_details += f"\n   URL: {url}"
    error_details += f"\n   Headers enviados: {get_headers()}"
    if last_response:
        error_details += f"\n   Status HTTP: {last_response.status_code}"
        error_details += f"\n   Headers resposta: {dict(last_response.headers)}"
        error_details += f"\n   Corpo resposta: {last_response.text[:500]}"
    elif last_exception:
        error_details += f"\n   Exceção: {type(last_exception).__name__}: {last_exception}"
    raise RuntimeError(f"{last_error}.{error_details}")


def list_open_issues(repo: str) -> list:
    """Lista todas as issues abertas de um repositório."""
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    params = {"state": "open", "per_page": 100}

    try:
        response = requests.get(url, headers=get_headers(), params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            issues = response.json()
            return [
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "body": issue.get("body", ""),
                    "labels": [label["name"] for label in issue.get("labels", [])],
                }
                for issue in issues
                if not issue.get("pull_request")
            ]
        elif response.status_code == 404:
            raise RuntimeError(f"Repositório não encontrado: {repo}")
        elif response.status_code == 401:
            raise RuntimeError("Token inválido ou sem permissão.")
        else:
            raise RuntimeError(f"Erro ao listar issues: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Erro de conexão com a API do GitHub.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout ao conectar com a API do GitHub.")


def execute_github_action(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Executa uma ação do GitHub com base nos dados estruturados."""
    action = action_data.get("action")
    repo = action_data.get("repo")
    issue_number = action_data.get("issue_number")
    title = action_data.get("title")
    body = action_data.get("body")
    labels = action_data.get("labels")

    if not repo:
        raise RuntimeError("Repositório não especificado (campo 'repo' obrigatório).")

    if action == "create_issue":
        if not title:
            raise RuntimeError("Título da issue obrigatório para criação.")
        return create_issue(repo, title, body, labels)

    elif action == "edit_issue":
        if not issue_number:
            raise RuntimeError("Número da issue obrigatório para edição.")
        return edit_issue(repo, issue_number, title, body, labels)

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
    "list_open_issues",
    "execute_github_action",
    "check_repo_access",
]
