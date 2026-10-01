---
name: planet9-screening-lab
description: Use when a task touches the planet9-screening-lab repo.
version: 1.0.0
author: Luriat (Auditor) + Hermes (Executor)
license: proprietary
metadata:
  hermes:
    tags: [planet9, scientific-pipeline, audit, clinerules, task-md]
    related_skills: [grounded-citations]
---

# Skill: Planet9 Screening Lab — Auditoria Científica

## When to Use (Quando usar)
Ative sempre que a tarefa envolver o repositório planet9-screening-lab
(pipeline de triagem de candidatos ao Planeta Nove, REBOUND + Python,
dashboard NiceGUI, artigo científico para FENIC/FEBRACE).

## Fonte de autoridade — NUNCA duplicar, sempre reler
As regras operacionais completas deste projeto vivem em dois arquivos
DENTRO do repositório, não nesta skill:
- `.clinerules` (raiz do repo) — regras de ambiente, gate, disciplina
  científica e de código, protocolo de comunicação, continuidade.
- `TASK.md` (raiz do repo) — estado vigente do projeto: plano atual,
  bloqueios, e log de execução (histórico append-only).

**Primeira ação de toda sessão, sem exceção:** leia `.clinerules` e as
últimas entradas de `TASK.md` inteiros antes de agir. Nunca assuma que
memória de conversa anterior (sua ou de outra ferramenta) reflete o
estado atual — o repositório circula entre várias máquinas, e o disco é
a única fonte confiável.

Se algo nesta skill parecer contradizer o `.clinerules` do repositório
no momento, **o `.clinerules` sempre vence** — esta skill pode estar
desatualizada, o arquivo do repo não.

## O essencial, em uma frase
Precisão, rastreabilidade e honestidade epistêmica pesam mais que
velocidade. Trate qualquer relatório de auditoria (seu ou de outra
sessão/ferramenta) como alegação até confirmar contra código real e
execução real — nunca aceite "deve estar certo".

## Comportamentos não-negociáveis (resumo operacional do .clinerules — releia o original para o texto completo)
- Nunca decida sozinho conteúdo científico (integrador, sistema de
  referência, se um resultado é suficiente) — pare e pergunte.
- Nunca "conserte" um teste falho sem reportar e pedir autorização,
  especialmente se envolver mudar o critério do teste.
- Gate obrigatório no início e no fim de toda tarefa: `python -m pytest
  -q` (confira o baseline esperado no TASK.md antes) + `python -m ruff
  check .`. Reporte a saída literal, nunca resuma.
- Levantamento read-only antes de editar, sempre que possível.
- Achado inesperado (número não bate, arquivo sumiu, comportamento
  estranho) = parar, investigar com evidência concreta (grep, traceback
  completo, teste de controle em worktree isolada quando aplicável),
  reportar — nunca contornar ou assumir.
- Toda claim científica no artigo/código deve corresponder a algo de
  fato executado; pendências reais ficam declaradas, nunca escondidas
  ou infladas. Vocabulário proibido: "confirmado", "descoberta", "órbita
  determinada". Vocabulário permitido: "triagem exploratória",
  "candidato de interesse dentro do protocolo", "inconclusivo".
- Toda constante física/orbital nova precisa de atribuição de fonte
  (arquivo original + linha, ou referência bibliográfica) — nunca
  inventar ou arredondar de memória.
- Nunca copiar dados de terceiros na íntegra — extrair só o necessário,
  com atribuição.
- Commit ao final de cada tarefa concluída (não só ao fim da sessão),
  com relatório: gate antes/depois, arquivos alterados, ambiguidades e
  como foram resolvidas, hash do commit.
- Ao trocar de modelo/ferramenta por limite de tokens: registrar
  checkpoint em TASK.md e commitar trabalho parcial ANTES de trocar; ao
  assumir, reler TASK.md + `git log -5 --oneline` antes de continuar.

## Protocolo Auditor/Executor
O usuário (Luriat) é o Auditor: só ele decide conteúdo científico e
autoriza execuções caras/longas (ex: integrações de horas). Você
(agente executor) escreve em `TASK.md` apenas nas seções "Bloqueios" e
"Log de execução", sempre por append — nunca reescreve entradas antigas.
Toda entrada de log leva cabeçalho com hostname real da máquina
($env:COMPUTERNAME) e timestamp.

## Ceticismo com evidência, não com objeção genérica
Quando confirmar ou refutar uma alegação (sua ou de outra sessão), cite
arquivo:linha e trecho de código literal — nunca "parece correto" sem
mostrar o porquê. Se a alegação envolver contagem de testes, números
científicos, ou comportamento específico, prefira verificação executável
(rodar o teste, grep, comparar contra um commit anterior via
`git worktree`) a leitura estática quando a leitura estática for
ambígua ou contestável.

## O que esta skill NÃO cobre
Detalhes de arquitetura do pipeline (engine.py, selection_bias.py,
sky_projection.py, dashboard/), estado atual das tarefas científicas, e
histórico de decisões — tudo isso está em `TASK.md` e muda com
frequência. Releia lá, não confie em memória desta skill para isso.
Nota de proveniência: esta cópia versionada (repo) é a fonte de referência para revisão; a cópia runtime desta máquina vive em C:\Users\Luriat\AppData\Local\hermes\skills\research\planet9-screening-lab\SKILL.md.
