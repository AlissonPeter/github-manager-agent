from typing import TypedDict, Optional, Any, Dict, List
import os
import json
from pydantic import BaseModel, Field, field_validator

from langgraph.graph import StateGraph as LGStateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

import ollama

from src.agent.github_tool import execute_github_action, get_issue, check_repo_access

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


import re
import threading
import sys


DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
if not DEFAULT_OLLAMA_MODEL:
    raise RuntimeError("Variável OLLAMA_MODEL não definida no arquivo .env")


class _Spinner:
    """Spinner simples que roda em thread separada."""
    def __init__(self, message: str = "Processando"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def _run(self):
        chars = "|/-\\"
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {chars[i % len(chars)]} {self.message}...")
            sys.stdout.flush()
            self._stop.wait(0.15)
            i += 1


def _ollama_chat(model: str, messages: list, options: dict = None) -> dict:
    """Chama ollama.chat com spinner de progresso."""
    with _Spinner("Processando"):
        return ollama.chat(model=model, messages=messages, options=options or {})


class AgentState(TypedDict):
    current_command: str
    last_action: Dict[str, Any]
    user_confirmation: bool
    default_repo: Optional[str]
    history: Optional[List[Dict[str, Any]]]
    issue_titles: Optional[Dict[int, str]]


def _validate_repo(repo: str) -> bool:
    """Valida o formato do repositório (owner/repo)."""
    if not repo:
        return False
    parts = repo.split("/")
    return len(parts) == 2 and all(part.strip() for part in parts)


def _input_multiline(prompt: str, allow_empty: bool = True, default: str = "") -> str:
    """Lê entrada de múltiplas linhas do usuário.

    Enter confirma e envia. Shift+Enter (ou Ctrl+J) cria uma nova linha.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.lexers import PygmentsLexer
    from prompt_toolkit.styles import Style
    from prompt_toolkit.key_binding import KeyBindings
    from pygments.lexers import MarkdownLexer

    print(prompt)
    print("  (Enter para confirmar, Ctrl+L para nova linha)")

    custom_style = Style.from_dict({
        "prompt": "#ffffff bg:#3c3c3c",
    })

    kb = KeyBindings()

    # 1. ENTER CONFIRMA: Força o envio imediato do buffer atual
    @kb.add('enter')
    def _(event):
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add('c-l')
    def _(event):
        event.current_buffer.insert_text('\n')

    try:
        session = PromptSession(
            lexer=PygmentsLexer(MarkdownLexer),
            style=custom_style,
            multiline=True,  # Mantemos True para permitir o \n no buffer
            key_bindings=kb,
        )
        result = session.prompt("  > ", default=default)
        if not result.strip() and not allow_empty:
            return default
        return result if result.strip() else default
    except Exception:
        # Fallback se o terminal for muito antigo
        lines = []
        while True:
            line = input("  > ").rstrip("\n")
            if not line and allow_empty and not lines:
                return ""
            if not line and lines:
                break
            lines.append(line)
        result = "\n".join(lines)
        return result if result else default


def _prompt_repo() -> str:
    """Solicita ao usuário o repositório e valida o formato e existência."""
    while True:
        repo = input("📦 Informe o repositório (owner/repo): ").strip()
        if not _validate_repo(repo):
            print("❌ Formato inválido. Use: owner/repo")
            continue
        try:
            if check_repo_access(repo):
                return repo
            print(f"❌ Sem acesso ao repositório '{repo}'. Verifique o token ou o nome do repositório.")
        except RuntimeError as e:
            print(f"❌ {e}")


def _has_checklists(body: str) -> bool:
    """Verifica se o corpo da issue contém itens de checklist."""
    return bool(re.search(r"- \[ \]", body))


def _mark_checklists(body: str) -> str:
    """Marca todos os itens de checklist como concluídos."""
    return re.sub(r"- \[ \]", "- [x]", body)


class GitActionSchema(BaseModel):
    action: str = Field(..., description="Ação a ser executada: create_issue | edit_issue | close_issue")
    repo: Optional[str] = Field(None, description="Nome do repositório no formato 'owner/repo' (opcional)")
    issue_number: Optional[int] = Field(None, description="Número da issue no GitHub (obrigatório se edit ou close)")
    title: Optional[str] = Field(None, description="Título da issue (necessário se create ou edit)")
    body: Optional[str] = Field(None, description="Conteúdo ou descrição do corpo da issue (opcional)")
    labels: Optional[List[str]] = Field(None, description="Labels da issue (opcional)")

    @field_validator("action")
    def validate_action(cls, v: str) -> str:
        allowed = {"create_issue", "edit_issue", "close_issue", "historico"}
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
    is_historico = action_word in {"histórico", "historico", "history", "hist"}

    if is_historico:
        return GitActionSchema(action="historico")

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

    raise ValueError("Comando não reconhecido. Use: criar, editar <número>, fechar <número> ou histórico")


def router_node(state: AgentState) -> Dict[str, Any]:
    """Nó puro: extrai ação estruturada usando Ollama."""
    model_name = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

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
  "labels": ["label1", "label2"] (obrigatório para create/edit),
  "body": "descrição da issue" (APENAS se o usuário forneceu uma descrição)
}"""

    try:
        response = _ollama_chat(
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

    except ConnectionError as e:
        raise RuntimeError(
            f"Falha ao conectar com Ollama: {e}. "
            "Verifique se o servidor está rodando (ollama serve)."
        )
    except Exception as e:
        raise RuntimeError(
            f"Erro ao processar comando com Ollama: {e}. "
            "Verifique se o modelo está disponível."
        )

    validated = _validate_command(state["current_command"], parsed)
    return {"last_action": validated.model_dump()}


def enhancer_node(state: AgentState) -> Dict[str, Any]:
    """Nó que melhora a descrição da issue e cria checklist usando Ollama."""
    model_name = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    last = state.get("last_action", {})
    action = last.get("action")

    if action != "create_issue":
        return {"last_action": last}

    if not last.get("title"):
        print("\n--- Criar Nova Issue ---")
        body = _input_multiline("📄 Descrição (Enter duas vezes para pular):")
        last = {**last, "body": body}

    title = last.get("title", "")
    body = last.get("body", "")

    if not body:
        body = f"Criar issue sobre: {title}"
        last = {**last, "body": body}

    system_prompt = """Você é um assistente especializado em criar issues detalhadas para GitHub.

Analise a descrição fornecida pelo usuário e crie uma descrição melhorada e profissional para uma issue.

Diretrizes:
1. Mantenha a intenção original do usuário
2. Adicione contexto e detalhes relevantes
3. Crie título claro e conciso (máximo 72 caracteres)
4. Labels: escolha APENAS entre fix/bug, feature, infra, backend, frontend, docs. Máximo 3
5. Crie uma seção de critérios de aceitação com itens de validação
6. Use formatação Markdown
7. Seja claro e conciso

Retorne APENAS um JSON válido com os campos "title", "labels" e "body".

Exemplo:
{"title": "Título da issue", "labels": ["bug"], "body": "## Descrição\\n...\\n\\n## Critérios\\n- [ ] Critério 1"}"""

    try:
        response = _ollama_chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Título: {title}\n\nDescrição original: {body}"}
            ],
            options={"temperature": 0.3}
        )

        response_text = response["message"]["content"].strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        json_start = response_text.find("{")
        json_end = response_text.rfind("}")
        if json_start != -1 and json_end != -1 and json_start <= json_end:
            response_text = response_text[json_start:json_end + 1]
        else:
            raise ValueError(f"Resposta não contém JSON: {response_text[:200]}")

        parsed_data = json.loads(response_text, strict=False)
        suggested_title = parsed_data.get("title", "")
        suggested_labels = parsed_data.get("labels", [])
        enhanced_body = parsed_data.get("body", body)

        final_title = title if title else suggested_title
        updated_action = {**last, "title": final_title, "labels": suggested_labels, "body": enhanced_body}
        return {"last_action": updated_action}

    except Exception as e:
        print(f"\n⚠️  Ollama indisponível: {e}")
        print("   Usando descrição original (sem melhoria automática).")
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

    if action_data.get("labels"):
        lines.append(f"🏷️  Labels: {', '.join(action_data['labels'])}")

    if action_data.get("body"):
        lines.append(f"📄 Descrição:\n{action_data['body']}")

    return "\n".join(lines)


def _prompt_edit(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Solicita ao usuário que edite título, descrição e/ou labels da issue."""
    print(f"\n{'=' * 40}\n{_format_issue_preview(action_data)}\n{'=' * 40}")

    current_title = action_data.get("title", "")
    current_body = action_data.get("body", "")
    current_labels = action_data.get("labels", [])

    print("\n--- Edição da Issue ---")

    print(f"\nTítulo atual: {current_title}")
    new_title = input("Novo título (Enter para manter): ").strip()
    if not new_title:
        new_title = current_title

    print(f"\nDescrição atual:\n{current_body}")
    new_body = _input_multiline("Nova descrição (Enter para manter):", allow_empty=True, default=current_body)
    if not new_body:
        new_body = current_body

    print(f"\nLabels atuais: {', '.join(current_labels) if current_labels else 'nenhuma'}")
    new_labels_str = input("Novas labels (Enter para manter, ou separadas por vírgula): ").strip()
    if not new_labels_str:
        new_labels = current_labels
    else:
        new_labels = [label.strip() for label in new_labels_str.split(",") if label.strip()]

    return {**action_data, "title": new_title, "body": new_body, "labels": new_labels}


def _handle_edit_issue(last: Dict[str, Any], issue_data: Dict) -> Dict[str, Any]:
    """Lida com a edição de uma issue existente, sugerindo melhorias via LLM."""
    model_name = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    raw_labels = issue_data.get("labels", [])
    if raw_labels and isinstance(raw_labels[0], dict):
        label_names = [label["name"] for label in raw_labels if isinstance(label, dict) and "name" in label]
    else:
        label_names = raw_labels if raw_labels else []
    last = {
        **last,
        "title": issue_data.get("title", ""),
        "body": issue_data.get("body", ""),
        "labels": label_names,
    }

    current_title = last.get("title", "")
    current_body = last.get("body", "")
    current_labels = last.get("labels", [])

    print(f"\n{'=' * 40}")
    print("\n✏️  Editar Issue")
    print(f"📌 Título atual: {current_title}")
    print(f"🏷️  Labels: {', '.join(current_labels) if current_labels else 'nenhuma'}")
    print(f"\n📄 Descrição atual:\n{current_body}")
    print(f"{'=' * 40}")

    new_description = _input_multiline("Nova descrição resumida (Enter para manter a atual):", allow_empty=True)
    if not new_description:
        return last

    system_prompt = """Analise a nova descrição e retorne APENAS um JSON válido.

Schema:
{
  "title": "título claro",
  "labels": ["label1", "label2"],
  "body": "## Descrição\\n\\nDescrição detalhada...\\n\\n## Critérios de Aceitação\\n- [ ] Critério 1\\n- [ ] Critério 2"
}

REGRAS:
- Título: máximo 72 caracteres, claro e descritivo, em português correto
- Labels: escolha APENAS entre fix/bug, feature, infra, backend, frontend, docs. Máximo 3
- Body deve conter:
  * Descrição detalhada (contexto, motivo, comportamento esperado)
  * Critérios de aceitação (mínimo 3, máximo 10) - inclua:
    - Funcionais (o que deve fazer)
    - Validações (limites, formatos, campos obrigatórios)
    - UX (mensagens, estados, loading)
    - Borda (casos limites, erros)
- Use \\n para quebras de linha no JSON
- Seja específico e detalhado nos critérios"""

    try:
        response = _ollama_chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Título atual: {current_title}\n\nNova descrição resumida: {new_description}"}
            ],
            options={"temperature": 0.1, "num_predict": 1024}
        )

        response_text = response["message"]["content"]

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Try to extract JSON from the response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}")
        if json_start != -1 and json_end != -1 and json_start <= json_end:
            response_text = response_text[json_start:json_end + 1]
        else:
            raise ValueError(f"Resposta do LLM não contém JSON válido: {response_text[:200]}")

        # Fix YAML-style multiline strings (body: | ...)
        def fix_yaml_strings(text):
            pattern = r':\s*\|\s*\n((?:\s+.+\n?)+)'

            def replace_match(m):
                content = m.group(1)
                lines = content.split('\n')
                cleaned = []
                for line in lines:
                    stripped = line.strip()
                    if stripped:
                        cleaned.append(stripped)
                return ': "' + '\\n'.join(cleaned) + '"'
            return re.sub(pattern, replace_match, text)

        response_text = fix_yaml_strings(response_text)

        parsed_data = json.loads(response_text, strict=False)
        suggested_title = parsed_data.get("title", current_title)
        suggested_labels = parsed_data.get("labels", current_labels)
        suggested_body = parsed_data.get("body", new_description)

        print("\n🤖 Sugestões do agente:")
        print(f"   📌 Título sugerido: {suggested_title}")
        print(f"   🏷️  Labels sugeridas: {', '.join(suggested_labels) if suggested_labels else 'nenhuma'}")
        print("   📄 Descrição sugerida:")
        print(f"   {suggested_body[:200]}{'...' if len(suggested_body) > 200 else ''}")

        last = {**last, "title": suggested_title, "labels": suggested_labels, "body": suggested_body}
        return last

    except Exception as e:
        print(f"\n⚠️  Ollama indisponível: {e}")
        print("   Edição manual.")
        return _prompt_edit(last)


def _handle_close_issue(last: Dict[str, Any], issue_data: Dict, issue_titles: Dict[int, str]) -> Dict[str, Any]:
    """Lida com o fechamento de uma issue, incluindo marcação de checklists."""
    issue_number = last.get("issue_number")
    if issue_data.get("state") == "closed":
        raise RuntimeError(f"Issue #{issue_number} já está fechada.")

    title = issue_titles.get(issue_number, issue_data.get("title", "Sem título"))
    last = {**last, "title": title}

    body = issue_data.get("body", "")
    if _has_checklists(body):
        resp = input(
            "\n📋 Esta issue possui critérios de aceitação."
            " Deseja marcar como concluídos?"
            "\n  1-Sim\n  2-Não\n→ "
        ).strip()
        if resp == "1":
            body = _mark_checklists(body)
            last = {**last, "body": body}

    return last


def _fetch_issue_data(last: Dict[str, Any], issue_titles: Dict[int, str] = None) -> Dict[str, Any]:
    """Busca dados da issue no GitHub para edição ou fechamento."""
    repo = last.get("repo")
    issue_number = last.get("issue_number")
    action = last.get("action")

    if action not in ("edit_issue", "close_issue") or not repo or not issue_number:
        return last

    try:
        result = get_issue(repo, issue_number)
        issue_data = result.get("issue", {})
    except Exception as e:
        raise RuntimeError(
            f"Issue #{issue_number} não encontrada no repositório {repo}: {e}"
        )

    if action == "edit_issue":
        return _handle_edit_issue(last, issue_data)
    if action == "close_issue":
        return _handle_close_issue(last, issue_data, issue_titles or {})

    return last


def confirmator_node(state: AgentState) -> Dict[str, Any]:
    """Nó de confirmação: exibe preview e oferece opções de confirmação."""
    last = state.get("last_action", {})
    default_repo = state.get("default_repo")
    issue_titles = state.get("issue_titles", {})

    if not last.get("repo") and default_repo:
        last = {**last, "repo": default_repo}

    last = _fetch_issue_data(last, issue_titles)

    preview = _format_issue_preview(last)
    print(f"\n{'=' * 40}\n{preview}\n{'=' * 40}")

    if last.get("action") == "close_issue":
        resp = input(
            "\nConfirma o fechamento desta issue?"
            "\n  1-Sim\n  2-Não\n→ "
        ).strip()
        if resp == "1":
            return {"last_action": last, "user_confirmation": True}
        print("❌ Operação cancelada pelo usuário.")
        return {"user_confirmation": False, "last_action": last}

    return _prompt_create_or_edit(last)


def _prompt_create_or_edit(last: Dict[str, Any]) -> Dict[str, Any]:
    """Loop de confirmação para criação ou edição de issues."""
    while True:
        resp = input(
            "\nConfirma a operação?"
            "\n  1-Confirmar\n  2-Editar\n  3-Cancelar\n→ "
        ).strip()

        if resp == "1":
            return {"last_action": last, "user_confirmation": True}
        elif resp == "2":
            last = _prompt_edit(last)
            print(
                f"\n{'=' * 40}"
                f"\n{_format_issue_preview(last)}"
                f"\n{'=' * 40}"
            )
        elif resp == "3":
            print("❌ Operação cancelada pelo usuário.")
            return {"user_confirmation": False, "last_action": last}
        else:
            print("Opção inválida. Digite 1, 2 ou 3.")


def executor_node(state: AgentState) -> Dict[str, Any]:
    """Nó executor: executa a ação do GitHub via API REST."""
    last = state.get("last_action", {})
    default_repo = state.get("default_repo")
    history = state.get("history", [])
    issue_titles = state.get("issue_titles", {})

    if not state.get("user_confirmation"):
        raise RuntimeError("operação abortada pelo usuário")

    if not last.get("repo") and default_repo:
        last = {**last, "repo": default_repo}

    try:
        result = execute_github_action(last)
        updated_action = {**last, "executed": True, "result": result}

        issue_number = last.get("issue_number")
        if not issue_number and result.get("issue"):
            issue_number = result["issue"].get("number")

        title = last.get("title")
        if issue_number and title:
            issue_titles = {**issue_titles, issue_number: title}

        history_entry = {
            "action": last.get("action"),
            "title": title or "Sem título",
            "issue_number": issue_number,
            "repo": last.get("repo"),
        }
        return {"last_action": updated_action, "history": history + [history_entry], "issue_titles": issue_titles}
    except RuntimeError as e:
        if default_repo and "Repositório não encontrado" in str(e):
            last = {**last, "repo": default_repo}
            result = execute_github_action(last)
            updated_action = {**last, "executed": True, "result": result}

            issue_number = last.get("issue_number")
            if not issue_number and result.get("issue"):
                issue_number = result["issue"].get("number")

            title = last.get("title")
            if issue_number and title:
                issue_titles = {**issue_titles, issue_number: title}

            history_entry = {
                "action": last.get("action"),
                "title": title or "Sem título",
                "issue_number": issue_number,
                "repo": last.get("repo"),
            }
            return {"last_action": updated_action, "history": history + [history_entry], "issue_titles": issue_titles}
        raise RuntimeError(f"Falha na execução da ação GitHub: {e}")


def historico_node(state: AgentState) -> Dict[str, Any]:
    """Nó que exibe o histórico de ações realizadas."""
    history = state.get("history", [])

    if not history:
        print("\n📋 Nenhuma ação registrada no histórico.")
        return {}

    action_labels = {
        "create_issue": "Criada",
        "edit_issue": "Editada",
        "close_issue": "Fechada",
    }

    repo = history[-1].get("repo", "")

    print("\n" + "=" * 50)
    print(f"📋 Histórico de Issues ({repo})")
    print("=" * 50)

    for i, entry in enumerate(reversed(history), 1):
        action = entry.get("action", "unknown")
        label = action_labels.get(action, action)
        title = entry.get("title", "Sem título")
        number = entry.get("issue_number", "?")
        print(f"  {i}. {label} - #{number} {title}")

    print("=" * 50)
    return {}


def route_after_router(state: AgentState) -> str:
    """Decide se o fluxo vai para confirmação, enhancer, historico ou direto para execução."""
    action = state.get("last_action", {}).get("action")
    if action == "historico":
        return "historico"
    if action == "create_issue":
        return "enhancer"
    return "confirmator"


def route_after_enhancer(state: AgentState) -> str:
    """Após melhorar a descrição, vai para confirmação."""
    return "confirmator"


def build_graph() -> Any:
    """Constrói e compila o grafo do LangGraph."""
    g = LGStateGraph(AgentState)

    g.add_node("router", router_node)
    g.add_node("enhancer", enhancer_node)
    g.add_node("confirmator", confirmator_node)
    g.add_node("executor", executor_node)
    g.add_node("historico", historico_node)

    g.add_edge(START, "router")

    g.add_conditional_edges(
        "router",
        route_after_router,
        {
            "confirmator": "confirmator",
            "enhancer": "enhancer",
            "executor": "executor",
            "historico": "historico"
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
    g.add_edge("historico", END)

    memory = MemorySaver()
    app = g.compile(checkpointer=memory)

    return app


__all__ = [
    "AgentState",
    "GitActionSchema",
    "router_node",
    "enhancer_node",
    "confirmator_node",
    "executor_node",
    "historico_node",
    "build_graph",
    "execute_github_action",
    "_format_issue_preview",
    "_prompt_edit",
    "_has_checklists",
    "_mark_checklists",
    "_validate_repo",
    "_prompt_repo",
]
