# CC·Replan · Replanejamento da programação cirúrgica

Trabalho da disciplina INF 323 Engenharia de Software II (UFV), Grupo 4: Hícaro Vitor, Gabriel Moreira e
Yasmim Chassin.

Este repositório implementa **um módulo** do sistema de gestão e replanejamento de centro cirúrgico: o
caso de uso **Replanejar programação**. Quando acontece um imprevisto (falta de
profissional, sala ou instrumento indisponível, paciente indisponível ou atraso de cirurgia), o sistema:

1. identifica as cirurgias afetadas.
2. gera opções de realocação válidas, ordenadas pelo impacto: tempo de sala perdido, pacientes afetados e
   restrições no limite.
3. deixa o funcionário escolher uma opção ou rejeitar todas, com justificativa obrigatória.
4. registra a decisão de forma imutável para auditoria.

Os cadastros são de uma clínica simulada no plano Básico (3 salas). A programação do dia e o registro de
auditoria são salvos em SQLite.

## Como rodar

Requer Python 3.11 ou mais novo.

```bash
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
flask --app ccreplan.web.app:create_app run
```

Depois abra http://localhost:5000. Exemplo: registre "Ausência de profissional" para o Dr. Paulo Mendes
hoje, das 11:30 às 13:30, e veja as opções para a Artroplastia das 13:00. Passe o mouse sobre uma
cirurgia da programação para ver o nome completo do paciente e a equipe.

A tela mostra a programação dos próximos 3 dias (hoje, amanhã e depois de amanhã), e o replanejamento
funciona para qualquer um deles. A situação de cada cirurgia segue o relógio do computador: já terminou,
concluída; está acontecendo, em andamento; ainda vai acontecer, agendada.

## Onde os dados ficam

Num arquivo SQLite em `instance/ccreplan.sqlite3` (ou no caminho da variável `CCREPLAN_BANCO`), criado na
primeira execução:

- `cirurgias`, `indisponibilidades` e `adiamentos`: a programação atual, gravada a cada decisão (os
  adiamentos guardam o horário original, que aparece riscado na tela, assim como as canceladas);
- `decisoes`: o registro de auditoria, com ocorrência, opções geradas, opção adotada, responsável,
  justificativa, data e hora. Gatilhos do banco impedem alterar ou excluir decisões.

Se o banco não tiver a programação que começa hoje, a de exemplo é montada e a auditoria é mantida. Para
começar do zero (ou recarregar os dados de exemplo depois de atualizar o código), apague o arquivo.

## Testes e verificações

```bash
pytest --cov=ccreplan       
ruff check . && ruff format --check .
pylint ccreplan tests       
```
## Processo usado (Fase 3)

Este módulo é o **Sprint 1** do processo customizado (Scrum + XP + RUP + MPS.BR nível G):

## Estrutura

```
ccreplan/
  dominio/          intervalo de tempo, entidades e regras de validação.
  replanejamento/   ocorrências, geração de opções, decisão e auditoria.
  web/              telas em Flask
  dados_exemplo.py  programação simulada da Clínica São Lucas
tests/              testes unitários e construtor de cenários
docs/               artefatos do Sprint 1 e medidas contra code smells
```
## Declaração de Uso de IA

A ferramenta Claude Code auxiliou na geração de código e documentação.