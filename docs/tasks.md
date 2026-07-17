# 📋 Quadro de Tarefas do Projeto (Backlog)

Este arquivo centraliza o gerenciamento de escopo do agente GitOps. Os IDs abaixo servem como rastreabilidade para commits e instruções de contexto para agentes de IDE.

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Última atualização | 2026-07-17 |
| Total de tarefas | 10 |

---

## T-001: Configuração do Ambiente, Estrutura Base e Segurança
## Descrição
Inicialização do repositório, isolamento de credenciais sensíveis e montagem da estrutura de pastas do projeto.
**Labels:** `infra`
**Estimativa:** 1h
**Depende de:** Nenhuma

## Critérios de Aceitação
- [x] Criar o arquivo `.gitignore` garantindo o bloqueio estrito do arquivo `.env` antes do primeiro commit.
- [x] Criar o arquivo `.env.example` na raiz do projeto mapeando as variáveis: `GITHUB_TOKEN`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY` e `BACKEND_HOST_PORT` (sem expor os valores reais).
- [x] Configurar o arquivo `requirements.txt` com as dependências do projeto (ex: `langgraph`, `pydantic`, `python-dotenv`, `requests`, `langchain-core`).
- [x] Criar a estrutura básica de pastas do projeto: `/src/agent` e `/docs`.

---

## T-002: Modelagem do Estado e Core do Grafo com LangGraph
## Descrição 
Implementação do motor principal do agente utilizando o framework LangGraph, carregando a chave `GEMINI_API_KEY` a partir do arquivo `.env` para a integração com a LLM. O objetivo é desenhar o fluxo de controle, a extração de intenções do usuário em dados estruturados via terminal e os nós de validação lógica.
**Estimativa:** 4h
**Depende de:** T-001

## Critérios de Aceitação
- [x] Criar o arquivo `agent/graph.py` utilizando a classe `StateGraph` do LangGraph.
- [x] Definir o esquema de estado compartilhado (`AgentState`) usando `TypedDict`, incluindo um campo para armazenar a resposta de confirmação (`user_confirmation`).
- [x] Criar o modelo de saída estruturada `GitActionSchema` usando `Pydantic` com suporte para ações como: `create_issue`, `edit_issue`, e `close_issue`.
- [x] Implementar o `router_node` configurado para interagir com a LLM (carregando a chave `GEMINI_API_KEY` a partir do arquivo `.env`) e preencher o JSON do Pydantic a partir do comando recebido no terminal.
- [x] Implementar o `confirmator_node` que intercepta o fluxo: se a ação extraída for `close_issue`, o nó deve travar a execução e solicitar uma confirmação manual (`sim`/`não`) via prompt de comando do terminal.
- [x] Configurar o roteamento condicional no grafo (`add_conditional_edges`) para seguir para a execução apenas se a flag de validação/confirmação for verdadeira, abortando o fluxo caso contrário.
- [x] Criar testes unitários para validar o comportamento dos nós e transições do grafo.

---

## T-003: Loop do Terminal e Integração com a API do GitHub
## Descrição
Implementação do loop contínuo de leitura no terminal para o usuário interagir com o agente e da ferramenta real de integração com a API REST do GitHub para criação, edição e exclusão de issues, utilizando o `GITHUB_TOKEN` e o `GITHUB_REPO` definidos no arquivo `.env.example`.
- **Repositório padrão via .env:** Adicionar a variável `GITHUB_REPO` para definir o repositório padrão, evitando necessidade de informar em cada comando.
- **Descrição inteligente de issues:** Implementado nó `enhancer_node` que utiliza o Ollama para melhorar a descrição fornecida pelo usuário e gerar automaticamente uma seção de checklist em Markdown.

**Estimativa:** 3h
**Depende de:** T-001, T-002

## Critérios de Aceitação
- [x] Implementar um loop de execução contínuo (`while True`) no arquivo principal (`main.py`) para capturar os comandos de texto informados pelo usuário até que ele digite 'sair'.
- [x] Implementar a ferramenta real de integração com o GitHub para criação, edição e tratamento de issues usando a biblioteca `requests`, carregando o `GITHUB_TOKEN` do arquivo `.env` para autenticação.
- [x] Amarrar a ferramenta do GitHub ao nó `executor` dentro do fluxo do LangGraph.
- [x] Garantir que a exclusão de uma issue via API só aconteça se a resposta do nó de confirmação no terminal (`T-002`) tiver sido estritamente positiva.
- [x] Validar o tratamento de erros básicos (ex: erro 404 de repositório ou token inválido do GitHub) para evitar o travamento do loop do terminal.
- [x] Criar testes unitários para validar a integração com a API do GitHub e a lógica do executor.
- [x] Configurar `GITHUB_REPO` no `.env` como repositório padrão e implementar fallback automático no `executor_node`.
- [x] Implementar `enhancer_node` que melhora descrições e cria checklists via Ollama antes da criação da issue.

---

## T-004: Integração da Ferramenta de Notificação via Telegram
## Descrição
Implementação da ferramenta de notificação ativa (*Push*) utilizando a API de bots do Telegram, disparando alertas formatados em Markdown sempre que uma operação no GitHub for concluída com sucesso pelo grafo, carregando as configurações `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` a partir do arquivo `.env`.
**Estimativa:** 2h
**Depende de:** T-001, T-003

## Critérios de Aceitação
- [ ] Criar e configurar o bot no Telegram via `@BotFather` para obter o Token de acesso.
- [ ] Capturar o `chat_id` do usuário para direcionamento correto dos alertas.
- [ ] Implementar a função de notificação usando `requests.post` apontando para os endpoints oficiais do Telegram, carregando os dados do bot (`TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`) a partir do arquivo `.env`.
- [ ] Amarrar a ferramenta criada ao nó `notifier` na saída do grafo do LangGraph.
- [ ] Testar o recebimento das mensagens Markdown no celular de forma integrada ao fluxo do terminal.
- [ ] Criar testes unitários para validar a integração e disparo de notificações da API do Telegram.

---

## T-005: Documentação Final, Engenharia de Prompts e Slides
## Descrição Elaboração e consolidação de todos os artefatos textuais, de segurança e de apresentação necessários para a submissão e avaliação final no AVA.
**Estimativa:** 3h
**Depende de:** T-001, T-002, T-003, T-004

## Critérios de Aceitação
- [ ] Escrever o arquivo `README.md` completo contendo: objetivo do agente, explicação do grafo, instruções detalhadas de execução (incluindo instruções para configurar as variáveis no arquivo `.env` a partir do `.env.example`), e exemplos reais de entrada e saída.
- [ ] Criar o documento `docs/prompts.md` isolando e documentando o System Prompt e as estratégias de engenharia de prompt aplicadas no agente.
- [ ] Desenvolver a apresentação de até 2 slides resumindo o problema, o agente construído, suas ferramentas e a visão geral do fluxo.
- [ ] Testar a visibilidade pública do repositório do GitHub em uma janela anônima antes da submissão final no AVA.

---

## T-006: Configuração de Integração Contínua (CI) com GitHub Actions
## Descrição 
Criação do pipeline automatizado no GitHub Actions para garantir que o código do agente siga as boas práticas do Python e não quebre a execução a cada novo commit.
**Estimativa:** 2h
**Depende de:** T-001

## Critérios de Aceitação:
- [x] Criar a pasta `.github/workflows/` na raiz do repositório.
- [x] Criar o arquivo `.github/workflows/ci.yml` configurado para rodar a cada `push` ou `pull_request` na branch principal.
- [x] Configurar o workflow para instalar as dependências do `requirements.txt` em um ambiente virtual Python.
- [x] Adicionar um passo de validação estática de código (Linter usando `flake8` ou `black`) para garantir a formatação limpa e organizada exigida no Critério 3.
- [x] Garantir que o pipeline rode com sucesso e exiba o "check" verde na interface do GitHub.

---

## T-007: Substituição do Gemini pela LLM local com Ollama
## Descrição 
Remover dependência da API do Google Gemini (`google-genai`) em favor do Ollama local (`ollama`), eliminando custos de API e problemas de quota.
- **Variáveis de ambiente para ser atualizadas:** substituir `GEMINI_API_KEY` por `OLLAMA_MODEL` (padrão: `llama3.2:3b`).
Remover `BACKEND_HOST_PORT` (não utilizada).

**Estimativa:** 3h
**Depende de:** T-001, T-002

## Critérios de Aceitação
- [x] Substituir dependência `google-genai` por `ollama` no `requirements.txt`.
- [x] Atualizar `router_node` para usar `ollama.chat()` em vez do cliente Gemini.
- [x] Remover variável `GEMINI_API_KEY` do `.env` e `.env.example`.
- [x] Adicionar variável `OLLAMA_MODEL` no `.env` e `.env.example`.
- [x] Remover variável `BACKEND_HOST_PORT` do `.env`, `.env.example` e `main.py`.
- [x] Atualizar system prompt do `router_node` para formato compatível com Ollama.
- [x] Testar extração de ações com o modelo `llama3.2:3b`.

---

## T-008: Confirmação ou edição do título e descrição das issues novas ou já existentes
**Descrição:** Implementar fluxo interativo com validação de comandos, preview formatado da issue, edição de título e descrição, e confirmação antes de executar ações (criar, editar, fechar). Validação de IDs inválidos com mensagem de erro.
**Labels:** `backend`
**Estimativa:** 2h
**Depende de:** T-002, T-003

### Critérios de Aceitação:
- [ ] Validar comandos: aceitar apenas `criar`, `editar <número>` ou `fechar <número>`; exibir erro para comandos inválidos.
- [ ] Ao criar issue: solicitar título e descrição interativamente via prompt.
- [ ] Ao editar issue: buscar dados atuais no GitHub e exibir preview formatado antes de permitir edição.
- [ ] Ao fechar issue: validar se o ID existe no GitHub antes de solicitar confirmação.
- [ ] Exibir preview da issue (📌 Título, 📄 Descrição, 📦 Repositório) antes da confirmação.
- [ ] Oferecer opções de confirmação: `1-Confirmar`, `2-Editar`, `3-Cancelar`.
- [ ] Permitir edição de título e/ou descrição antes de confirmar.
- [ ] Exibir descrição completa (sem truncamento).
- [ ] Abortar operação de forma limpa caso o usuário selecione cancelar.
- [ ] Criar testes unitários para validação de comandos, confirmação, edição e cancelamento.

---

## T-009: Marcação de checklists ao fechar uma issue
**Descrição:** Permitir que, ao fechar uma issue, o usuário possa optar por marcar automaticamente todos os itens de checklist (`- [ ]`) como concluídos (`- [x]`) na descrição antes de confirmar o fechamento.
**Labels:** `backend`
**Estimativa:** 1h
**Depende de:** T-002, T-003

### Critérios de Aceitação:
- [ ] Detectar a presença de itens de checklist (`- [ ]`) na descrição da issue ao solicitar fechamento.
- [ ] Exibir prompt ao usuário perguntando se deseja marcar as checklists como concluídas antes de fechar (`1-Sim`, `2-Não`).
- [ ] Implementar função que substitui `- [ ]` por `- [x]` em todos os itens da descrição quando o usuário confirmar.
- [ ] Garantir que a edição da descrição via API do GitHub seja feita antes da ação de fechamento.
- [ ] Integrar o fluxo no nó `executor` do grafo para a ação `close_issue`.
- [ ] Mudar a confirmação do fechamento de issues de `s/n` para `1-Sim`, `2-Não` para manter consistência com os demais prompts do agente.
- [ ] Criar testes unitários para validar os cenários com e sem checklists.

---

## T-010: Solicitação interativa do repositório ao iniciar o agente
## Descrição
Ao iniciar o agente, solicitar ao usuário que informe o repositório alvo (formato `owner/repo`) e armazenar em memória, removendo a dependência da variável `GITHUB_REPO` do arquivo `.env`.
**Labels:** `backend`
**Estimativa:** 1h
**Depende de:** T-002, T-003

## Critérios de Aceitação
- [ ] Adicionar prompt de entrada ao iniciar o agente solicitando o repositório no formato `owner/repo`.
- [ ] Validar o formato informado (deve conter exatamente um `/` com `owner` e `repo` preenchidos).
- [ ] Armazenar o repositório informado em memória utilizando `MemorySaver` do LangGraph para persistência entre chamadas do grafo.
- [ ] Remover a variável `GITHUB_REPO` do `.env`, `.env.example` e de todo o código que a utiliza.
- [ ] Atualizar o `executor` para utilizar o repositório armazenado em memória.
- [ ] Criar testes unitários para validar a entrada, validação e armazenamento do repositório.
