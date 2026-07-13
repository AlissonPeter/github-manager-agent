# 📋 Quadro de Tarefas do Projeto (Backlog)

Este arquivo centraliza o gerenciamento de escopo do agente GitOps. Os IDs abaixo servem como rastreabilidade para commits e instruções de contexto para agentes de IDE.

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Última atualização | 2026-07-13 |
| Total de tarefas | 5 |

---

## T-001: Configuração do Ambiente, Estrutura Base e Segurança
**Descrição:** Inicialização do repositório, isolamento de credenciais sensíveis e montagem da estrutura de pastas do projeto.
**Labels:** `infra`
**Estimativa:** 1h
**Depende de:** Nenhuma

### Checklist de Entrega:
- [ ] Criar o arquivo `.gitignore` garantindo o bloqueio estrito do arquivo `.env` antes do primeiro commit.
- [ ] Criar o arquivo `.env.example` dentro da pasta `/infra` mapeando as variáveis: `GITHUB_TOKEN`, `TELEGRAM_TOKEN`, e `TELEGRAM_CHAT_ID` (sem expor os valores reais).
- [ ] Configurar o arquivo `requirements.txt` com as dependências do projeto (ex: `langgraph`, `pydantic`, `python-dotenv`, `requests`, `langchain-core`).
- [ ] Criar a estrutura básica de pastas do projeto: `/src/agent` e `/docs`.
- [ ] Realizar o commit inicial seguindo o padrão de commits semânticos.

---

## T-002: Modelagem do Estado e Core do Grafo com LangGraph
**Descrição:** Implementação do motor principal do agente utilizando o framework LangGraph. O objetivo é desenhar o fluxo de controle, a extração de intenções do usuário em dados estruturados via terminal e os nós de validação lógica.
**Estimativa:** 4h
**Depende de:** T-001

### Checklist de Entrega:
- [ ] Criar o arquivo `agent/graph.py` utilizando a classe `StateGraph` do LangGraph.
- [ ] Definir o esquema de estado compartilhado (`AgentState`) usando `TypedDict`, incluindo um campo para armazenar a resposta de confirmação (`user_confirmation`).
- [ ] Criar o modelo de saída estruturada `GitActionSchema` usando `Pydantic` com suporte para ações como: `create_issue`, `edit_issue`, e `delete_issue`.
- [ ] Implementar o `router_node` configurado para interagir com a LLM e preencher o JSON do Pydantic a partir do comando recebido no terminal.
- [ ] Implementar o `confirmator_node` que intercepta o fluxo: se a ação extraída for `delete_issue`, o nó deve travar a execução e solicitar uma confirmação manual (`sim`/`não`) via prompt de comando do terminal.
- [ ] Configurar o roteamento condicional no grafo (`add_conditional_edges`) para seguir para a execução apenas se a flag de validação/confirmação for verdadeira, abortando o fluxo caso contrário.
- [ ] Realizar commits semânticos incrementais durante o desenvolvimento.

---

## T-003: Loop do Terminal e Integração com a API do GitHub
**Descrição:** Implementação do loop contínuo de leitura no terminal para o usuário interagir com o agente e da ferramenta real de integração com a API REST do GitHub para criação, edição e exclusão de issues.
**Estimativa:** 3h
**Depende de:** T-001, T-002

### Checklist de Entrega:
- [ ] Implementar um loop de execução contínuo (`while True`) no arquivo principal (`main.py`) para capturar os comandos de texto informados pelo usuário até que ele digite 'sair'.
- [ ] Implementar a ferramenta real de integração com o GitHub para criação, edição e tratamento de issues usando a biblioteca `requests`.
- [ ] Amarrar a ferramenta do GitHub ao nó `executor` dentro do fluxo do LangGraph.
- [ ] Garantir que a exclusão de uma issue via API só aconteça se a resposta do nó de confirmação no terminal (`T-002`) tiver sido estritamente positiva.
- [ ] Validar o tratamento de erros básicos (ex: erro 404 de repositório ou token inválido do GitHub) para evitar o travamento do loop do terminal.
- [ ] Commit semântico da funcionalidade.

---

## T-004: Integração da Ferramenta de Notificação via Telegram
**Descrição:** Implementação da ferramenta de notificação ativa (*Push*) utilizando a API de bots do Telegram, disparando alertas formatados em Markdown sempre que uma operação no GitHub for concluída com sucesso pelo grafo.
**Estimativa:** 2h
**Depende de:** T-001, T-003

### Checklist de Entrega:
- [ ] Criar e configurar o bot no Telegram via `@BotFather` para obter o Token de acesso.
- [ ] Capturar o `chat_id` do usuário para direcionamento correto dos alertas.
- [ ] Implementar a função de notificação usando `requests.post` apontando para os endpoints oficiais do Telegram.
- [ ] Amarrar a ferramenta criada ao nó `notifier` na saída do grafo do LangGraph.
- [ ] Testar o recebimento das mensagens Markdown no celular de forma integrada ao fluxo do terminal.
- [ ] Commit semântico da funcionalidade.

---

## T-005: Documentação Final, Engenharia de Prompts e Slides
**Descrição:** Elaboração e consolidação de todos os artefatos textuais, de segurança e de apresentação necessários para a submissão e avaliação final no AVA.
**Estimativa:** 3h
**Depende de:** T-001, T-002, T-003, T-004

### Checklist de Entrega:
- [ ] Escrever o arquivo `README.md` completo contendo: objetivo do agente, explicação do grafo, instruções detalhadas de execução e exemplos reais de entrada e saída.
- [ ] Criar o documento `docs/prompts.md` isolando e documentando o System Prompt e as estratégias de engenharia de prompt aplicadas no agente.
- [ ] Desenvolver a apresentação de até 2 slides resumindo o problema, o agente construído, suas ferramentas e a visão geral do fluxo.
- [ ] Testar a visibilidade pública do repositório do GitHub em uma janela anônima antes da submissão final no AVA.
- [ ] Commit final de documentação.