import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.agent.graph import build_graph, AgentState


def run_terminal_loop(default_repo: Optional[str] = None):
    """Executa o loop contínuo de interação com o usuário via terminal."""
    app = build_graph(default_repo=default_repo)

    print("=" * 60)
    print("🤖 GitHub Manager Agent - Terminal Interativo")
    print("=" * 60)
    print("Comandos disponíveis:")
    print("  - 'criar' - Cria uma nova issue (será solicitado título e descrição)")
    print("  - 'editar <número>' - Edita uma issue existente")
    print("  - 'fechar <número>' - Fecha uma issue")
    print("  - 'sair' - Encerra o programa")
    print("=" * 60)
    print()

    while True:
        try:
            command = input("💬 Digite seu comando: ").strip()

            if not command:
                continue

            if command.lower() in {"sair", "exit", "quit"}:
                print("Encerrando...")
                break

            initial_state: AgentState = {
                "current_command": command,
                "last_action": {},
                "user_confirmation": False,
            }

            result = app.invoke(initial_state, config={"configurable": {"thread_id": "default", "default_repo": default_repo}})

            last_action = result.get("last_action", {})
            if last_action.get("executed"):
                print(f"✅ Ação executada com sucesso: {last_action.get('action')}")
                if "result" in last_action:
                    print(f"   Resultado: {last_action['result']}")
            else:
                print("⚠️  Ação não executada.")

            print()

        except KeyboardInterrupt:
            print("\nEncerrando...")
            break
        except EOFError:
            print("\nEncerrando...")
            break
        except Exception as e:
            print(f"❌ Erro: {e}")
            print()


if __name__ == "__main__":
    default_repo = os.getenv("GITHUB_REPO")
    run_terminal_loop(default_repo=default_repo)
