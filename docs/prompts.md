**Principais prompts utilizados nos agentes de IDE para o desenvolvimento desse miniprojeto:**

## PROMPT 1:

Eu preciso que crie issues no arquivo tasks.md para o desenvolvimento do seguinte agente:

Um agente que utiliza o LangGraph com nós que gerencia issues no github, podendo criar, editar e até exclui-las, e no final enviar uma notificação para o telegram, utilizando token e chat ID do bot da plataforma, utilizando apenas MemorySaver para memorizar repositórios e outras informações.

A linguagem utilizada no desenvolvimento será python.

A LLM desse agente será o gemini, e tanto o a api key como também os tokens do github e telegram será extraída através das variáveis do arquivo .env

As issues no arquivo tasks.md para o desenvolvimento desse agente deverá ter código no título começando por T-001, com descrição detalhada e critérios de aceitação.

## PROMPT 2:

Analise a issue T-001 no arquivo tasks.md do projeto e implemente ela.

## PROMPT 3 (optei por usar llm local ao invés do gemini):

Crie a issue T-007 no arquivo tasks.md, com o objetivo de remover o uso da llm gemini para para ser usado a llm local pelo ollama. O modelo da llm local deverá ser informado na variável chamado OLLAMA_MODEL no arquivo .env.example