import ollama

from src.agent.graph import build_graph, AgentState, _prompt_repo, DEFAULT_OLLAMA_MODEL


def _check_ollama_connection() -> bool:
    """Verifica se o Ollama está acessível. Retorna True se conectado."""
    try:
        ollama.chat(
            model=DEFAULT_OLLAMA_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            options={"temperature": 0.1, "num_predict": 1},
        )
        return True
    except Exception:
        return False


def run_terminal_loop():
    """Executa o loop contínuo de interação com o usuário via terminal."""
    print("=" * 60)
    print("🤖 GitHub Manager Agent - Terminal Interativo")
    print("=" * 60)

    if not _check_ollama_connection():
        print("\n⚠️  Ollama não está acessible. Verifique se o servidor está rodando.")
        print("   O agente funcionará com funcionalidade limitada (sem melhoria de descrições).")
        print("   Para iniciar o Ollama: ollama serve")
        print()

    app = build_graph()

    default_repo = _prompt_repo()
    print(f"📦 Repositório selecionado: {default_repo}")

    print("\nComandos disponíveis:")
    print("  - 'criar' - Cria uma nova issue (será solicitado título e descrição)")
    print("  - 'editar <número>' - Edita uma issue existente")
    print("  - 'fechar <número>' - Fecha uma issue")
    print("  - 'histórico' - Exibe o histórico de issues gerenciadas")
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
                "default_repo": default_repo,
            }

            result = app.invoke(initial_state, config={"configurable": {"thread_id": "default"}})

            last_action = result.get("last_action", {})
            action = last_action.get("action")
            if last_action.get("executed"):
                print(f"✅ Ação executada com sucesso: {action}")
                if "result" in last_action:
                    print(f"   Resultado: {last_action['result']}")
            elif action != "historico":
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
    run_terminal_loop()
