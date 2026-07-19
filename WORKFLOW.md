# Instruções do Projeto

## Commits

- Commits devem ser sempre bem detalhados, descrevendo claramente as alterações realizadas
- Formato recomendado: `<tipo>(<escopo>): <descrição>` (ex: `feat(T-010): Implementar solicitação interativa do repositório`)

## Simulação de CI antes de Commit

- **SEMPRE** executar os comandos de linting e testes antes de fazer commit
- Verificar o arquivo `.github/workflows/ci.yml` para entender os passos do CI
- Executar localmente os mesmos comandos que o CI executaria:
  - `python -m flake8 src/ tests/ --count --statistics` (ou conforme configurado no .flake8)
  - `python -m pytest tests/ -v`
- Somente prosseguir com o commit se todos os testes passarem e não houver erros de linting

## Regra de Commit

- **NÃO** fazer commit automaticamente
- Fazer commit **SOMENTE** quando o usuário solicitar explicitamente (ex: "faça commit", "commit", "faça o commit")
- Aguardar confirmação do usuário antes de executar `git commit`

## Confirmação da Descrição do Commit

- **ANTES** de executar `git commit`, exibir ao usuário:
  - Mensagem de commit formatada
  - Lista de arquivos que serão incluídos
- Aguardar confirmação explícita do usuário ("sim", "pode commitar", etc.)
- Se o usuário solicitar alteração na mensagem, ajustar antes de prosseguir

## Fluxo Pós-Commit

Após o commit e push, seguir este fluxo quando solicitado:

1. Criar Pull Request (PR) no GitHub
2. Adicionar checklist dos critérios de aceitação da issue referente
3. Fazer merge do PR
4. **NUNCA** deletar branches automaticamente — somente se o usuário solicitar explicitamente
5. Marcar a issue como concluída (atualizar checklist se necessário)
6. Fechar a issue

## Exemplo de Fluxo Completo

```
Usuário: "faça commit e push na branch feature/T-010"

1. Verificar alterações: git status
2. Simular CI: flake8 + pytest
3. Criar branch (se necessário): git checkout -b feature/T-010
4. Adicionar arquivos: git add <arquivos>
5. Exibir mensagem de commit e aguardar confirmação do usuário
6. Commit com mensagem detalhada
7. Push: git push origin feature/T-010
8. Criar PR com descrição e checklist
9. Fazer merge (sem --delete-branch)
10. Atualizar issue com checklist
11. Fechar issue
```
