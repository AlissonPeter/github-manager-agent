import os
import requests
from typing import Dict, Any

TELEGRAM_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT = 5

_session = None


def _get_session() -> requests.Session:
    """Retorna uma sessão HTTP persistente para reutilizar conexões."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"Content-Type": "application/json"})
    return _session


def get_telegram_config() -> Dict[str, str]:
    """Retorna as configurações do Telegram do arquivo .env."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token:
        raise RuntimeError("Variável TELEGRAM_TOKEN não definida no arquivo .env")
    if not chat_id:
        raise RuntimeError("Variável TELEGRAM_CHAT_ID não definida no arquivo .env")

    return {"token": token, "chat_id": chat_id}


def send_telegram_message(message: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
    """Envia uma mensagem via Telegram usando sessão persistente."""
    config = get_telegram_config()

    url = f"{TELEGRAM_API_BASE}/bot{config['token']}/sendMessage"
    payload = {
        "chat_id": config["chat_id"],
        "text": message,
        "parse_mode": parse_mode
    }

    session = _get_session()

    try:
        response = session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return {"success": True, "message_id": response.json().get("result", {}).get("message_id")}
        elif response.status_code == 401:
            raise RuntimeError("Token do Telegram inválido. Verifique a variável TELEGRAM_TOKEN no .env")
        elif response.status_code == 400:
            error_desc = response.json().get("description", "") if response.text else ""
            if "chat not found" in error_desc.lower() or "chat_id" in error_desc.lower():
                raise RuntimeError(
                    "Chat ID inválido ou bot não adicionado ao chat. "
                    "Verifique a variável TELEGRAM_CHAT_ID no .env"
                )
            raise RuntimeError("Erro na formatação da mensagem. Verifique o parse_mode.")
        else:
            raise RuntimeError(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Erro de conexão com a API do Telegram.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Timeout ao conectar com a API do Telegram.")


def notify_github_action(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica sobre uma ação do GitHub via Telegram."""
    action = action_data.get("action")
    repo = action_data.get("repo")
    title = action_data.get("title")
    issue_number = action_data.get("issue_number")
    result = action_data.get("result", {})

    action_labels = {
        "create_issue": "✅ Issue Criada",
        "edit_issue": "✏️ Issue Editada",
        "close_issue": "🔒 Issue Fechada"
    }

    action_label = action_labels.get(action, action)
    issue_url = f"https://github.com/{repo}/issues/{issue_number}" if issue_number else ""

    message = f"*{action_label}*\n\n"
    message += f"*Repositório:* `{repo}`\n"
    if title:
        message += f"*Título:* {title}\n"
    if issue_number:
        message += f"*Número:* #{issue_number}\n"
        message += f"*Link:* [Ver Issue]({issue_url})\n"

    if action == "create_issue" and result.get("issue"):
        message += "\n✅ Issue criada com sucesso!"
    elif action == "edit_issue":
        message += "\n✏️ Issue editada com sucesso!"
    elif action == "close_issue":
        message += "\n🔒 Issue fechada com sucesso!"
    try:
        send_result = send_telegram_message(message)
        return {"notified": True, "telegram_result": send_result}
    except Exception as e:
        print(f"\n⚠️  Não foi possível enviar notificação via Telegram: {e}")
        return {"notified": False, "error": str(e)}


__all__ = [
    "get_telegram_config",
    "send_telegram_message",
    "notify_github_action",
]
