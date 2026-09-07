# Prompt de continuidade — Fechamento da Auditoria V3 (sessão 2026-08-13)

> **ESTADO ATUAL (2026-08-14):** os 4 itens restantes (P0-1, P1-2, P1-3, P2-4)
> foram **fechados** nesta sessão. Este documento fica arquivado como registro
> do plano; para retomar qualquer pendência, ler
> `docs/historico/RELATORIO_CORRECAO_AUDITORIA_V3.md`. As pendências que seguem
> de pé são transversais e exigem decisão do usuário: run secular (P0-1 opção B),
> `runs/`/`.gitignore` antes do commit, e o cruzamento externo dos ETNOs.

Este arquivo é o contexto de continuidade para uma nova sessão de chat cujo
**único objetivo é fechar os 4 itens restantes da Auditoria V3** (P0-1, P1-2,
P1-3, P2-4). Leia este documento por completo e assuma que TODO o estado
descrito aqui é verdadeiro. NÃO repita trabalho já feito, NÃO invente dado,
NÃO decida escopo científico sozinho.

Referências: `docs/AUDITORIA_V3_PLANET9_SCREENING_LAB.md` (fonte dos achados),
`docs/Artigo_FEBRACE_revisado.docx` (alvo de P0-1 e P1-2),
`docs/historico/PLANO_CORRECAO_POS_AUDITORIA_V2.md` e
`docs/historico/RELATORIO_EVOLUCAO_POS_V2.md` (padrão histórico de como as
correções anteriores foram documentadas e reportadas).

---

## 1. Estado do repositório (verificar antes de tudo)

- Working dir: `/workspace`, branch `master`, remote inexistente, único
  commit: `3f2f237 Initial commit`.
- **NADA do trabalho da sessão anterior está commitado.** 20 arquivos
  modificados + 1 novo (`tests/test_audit_v3_code_fixes.py`) no working tree.
  O usuário disse que o commit é feito por ele ao final — NÃO commitar sem
  pedido explícito.
- **NÃO existe `.gitignore`** no repositório. Os artefatos
  `__pycache__/` (planet9lab, scripts, tests) aparecem como untracked e
  `runs/` está **parcialmente trackeado** (70 arquivos, incluindo as duas
  runs reais de 1 Myr e `runs/latest_run.txt` apontando para
  `/workspace/runs/experiment_i_boundary_scan_...`). Se o usuário pedir
  commit, decidir antes com ele o que versionar em `runs/` (e se criar um
  `.gitignore` — proponha, mas não crie sem confirmação).
- Ambiente: `python3` (não `python`). Dependências instaladas globalmente:
  numpy pandas pydantic pyyaml typer rich matplotlib pytest ruff rebound
  (ruff 0.16.2, rebound 5.1.1). REBOUND real disponível, sem fallback.
- **`python-docx` NÃO está instalado** — necessário para editar
  `docs/Artigo_FEBRACE_revisado.docx` (P0-1/P1-2). Instalar só se/quando o
  usuário autorizar o caminho de reescrita do artigo:
  `python3 -m pip install --break-system-packages python-docx`.
- Gate de verificação (sempre rodar no fim de cada etapa):
  `python3 -m pytest -q` (110 testes), `python3 -m ruff check . --no-cache`
  (limpo), `python3 main.py doctor` (tudo OK).

## 2. Regras de execução (não negociáveis, definidas pelo usuário)

1. **Não inventar dado científico.** Número que não vier do artigo, do código
   ou de fonte citável = marcado explicitamente como suposição + motivo.
2. **Nenhuma decisão de escopo científico/metodológico é sua.** Apresentar as
   opções reais (com custo/impacto de cada uma) e esperar confirmação
   explícita do usuário antes de codificar ou editar o artigo.
3. **Nenhuma execução silenciosa.** Mudança de arquivo, run real, instalação
   de pacote, edição do docx: sinalizar o quê/por quê/efeito antes.
4. **Mudança mínima.** Não refatorar/reformatar código adjacente sem pedido.
5. **Toda alegação do artigo precisa de lastro real** (código, run, citação).
   Sem lastro = marcada como pendente, nunca preenchida com número plausível.
6. Proibido `rm`/delete sem confirmação; preferir mover para backup.
7. **Run secular (≥1e8 anos) não é executada sem autorização explícita do
   usuário** — cada run canônica secular é cara (horas–dias por candidato) e
   depende da decisão de P0-1.

## 3. O que JÁ foi feito na sessão anterior (NÃO refazer)

Todos os achados de **código** da Auditoria V3 foram corrigidos e verificados
(110 testes, ruff limpo, doctor OK):

| ID | Correção aplicada |
|---|---|
| P0-2 | `load_candidates` ordena por `candidate_id` antes de truncar; nova `load_candidates_with_excluded`; excluídos registrados como `not_evaluated_capacity_limit` em `data_manifest.json` e `audit/run_manifest.json`; propagado via `plan_run`/`run_smoke`/`run_screen`/`execute_run` |
| P1-1 | `--seed` documentado como inerte no `--help` (`cli.py`) e no relatório; campo `seed_effect: "inert_for_screen_compare_fixed_catalog"` no manifest |
| P1-4 | `weak_delta_floor` removido de `configs/scoring/v2_weights.yaml` e `default_weights.yaml` (campo morto) |
| P1-5 | Divisores `1e-4`/`1e-3` extraídos para `DRIFT_PENALTY_DIVISOR_NUMERICAL_HEALTH`/`DRIFT_PENALTY_DIVISOR_STABILITY` (`metrics.py`) com 16 linhas de justificativa documentada (padrão-ouro do `DELTA_POMEGA_LIBRATION_R_THRESHOLD`) |
| P1-6 | `doctor.py` agora verifica `Path(conteúdo de latest_run.txt).exists()` em vez de só o arquivo-ponteiro |
| P2-1 | `[tool.ruff.lint] select` pinado no `pyproject.toml` (11 regras); 6 erros da auditoria corrigidos (TRY004, RUF059, FLY002×2, BLE001, PLR0124) + W293 + E402×6 com `# noqa: E402` justificado (padrão `sys.path.insert`) |
| P2-2 | `docs/LIMITACOES.md` atualizado: item "candidatos de exemplo não substituídos" corrigido para apontar `data/candidates_quadro2.csv` + `CANDIDATOS_QUADRO2.md` |
| P2-3 | `--run-root` exposto no CLI (`screen`, `compare`, `smoke`, `montecarlo-scan`) e repassado às funções de `run.py` |
| P2-5 | `tests/test_audit_v3_code_fixes.py` — 9 testes: ordem determinística de `load_candidates`, `not_evaluated_capacity_limit` nos manifests, ranking byte-idêntico entre seeds, `seed_effect` inerte |

Arquivos tocados (todos verificados): `planet9lab/{cli,config,doctor,explain,
loaders,metrics,report,robustness,run,sample_data}.py`,
`configs/scoring/{v2_weights,default_weights}.yaml`, `pyproject.toml`,
`scripts/{archived/paramscan,experiments/run_grid_experiment,run_artigo,
offline_pytest_shim/__main__,watch_progress}.py`,
`tests/{test_audit_v3_code_fixes,test_post_v2_evolution}.py`,
`docs/LIMITACOES.md`.

## 4. Os 4 itens restantes — fechar um por um, com decisão do usuário

### P0-1 (P0) — Artigo apresenta 7 resultados dinâmicos sem run correspondente

**Fato:** `docs/Artigo_FEBRACE_revisado.docx` (Seção 4, Tabela 2, Seção 8.2)
afirma: integração "1 a 4 Gyr"; Tabela 2 com tempos de ejeção ("< 500 Myr"),
% de alinhamento ("80% dos ETNOs"), objeto "Ammonite" desalinhado,
desestabilização da nuvem de Oort, "excesso de órbitas polares", e
"Δϖ estável > 4 Gyr; sem ejeções" para M=6,a=500,e=0,35,i=20°. **Nenhuma
dessas alegações tem run no repositório**: as únicas 2 runs reais
(`runs/experiment_angle_robustness_...` e `runs/experiment_i_boundary_scan_...`)
são de 1 Myr, cobrem só 1 candidato cada, e não tocam as outras 6 linhas da
Tabela 2. `secular.yaml` (1e8 yr, `max_candidates: 7`) nunca foi executado.

**Duas opções (decisão do usuário):**
- **A. Reescrita do artigo (texto):** reescrever Seção 4/Tabela 2 e Seção 8.2
  para refletir só o que foi executado (1 Myr, `row4`/`row6`, 2 experimentos
  de sensibilidade), classificando os outros 5 resultados como "não executado
  nesta versão". Rápido; não muda física. Requer `python-docx` (instalar com
  permissão) ou edição manual do usuário no Word.
- **B. Executar o canônico secular:** rodar as 7 configurações do Quadro 2 em
  escala secular via `python3 scripts/run_artigo.py` (usa `secular.yaml`,
  `candidates_quadro2.csv`, `catalog_validated.csv`). **Custo:** o único
  benchmark disponível (`results/hardware_benchmark.json`) foi medido num
  sandbox (não é o E3-1230 v2 citado no script) e projeta ~0,35 h/par para
  1e8 yr e ~14 h/par para 4e9 yr — são projeções não validadas em hardware
  real. Antes de rodar, decidir com o usuário: (i) tratar o benchmark do
  sandbox como válido ou remedir na máquina real
  (`python3 scripts/benchmark_integration_cost.py`); (ii) qual horizonte usar
  (1e8 é o valor atual de `secular.yaml`, não 4e9); (iii) se usa
  `--budget configs/budgets/low.yaml` para um smoke de wiring primeiro.

**Critério de aceite:** ou o artigo passa a conter apenas alegações com lastro
(comitável e verificável via `grep` das strings antigas), ou existe uma run
secular real cujo `audit/run_manifest.json` lastreia o que a Tabela 2 afirma.
Em nenhum caso inventar um número.

### P1-2 (P1) — `write_seed_stability` é no-op com seed única

**Fato:** `planet9lab/run.py:866` `write_seed_stability` — com
`len(budget.seeds) <= 1` (todos os budgets atuais) escreve
`{"enabled": false, "candidates": []}` e sai. É limitação já documentada em
`docs/LIMITACOES.md` (item 5, "write_seed_stability hoje registra o mesmo
rank/delta... medida de estabilidade parcial"). A recomendação da auditoria:
**manter como PENDENTE explícito no artigo, não elevar "robustez validada"**
em nenhuma seção.

**Ação (baixa complexidade):** garantir que o artigo (Seção que cite
estabilidade entre seeds, se houver) e `docs/LIMITACOES.md` deixem explícito
que estabilidade entre seeds NÃO foi validada (nenhuma run real com
`seeds` com múltiplos valores). Verificar se o texto do artigo menciona
"robustez entre seeds"/"estabilidade de ranking" em algum ponto — se sim,
marcar como pendente. Não há mudança de código esperada. Confirmar com o
usuário se quer edição do docx ou só a nota em LIMITACOES.md (já existe).

**Critério de aceite:** nenhuma seção do repositório ou do artigo alega
robustez entre seeds validada; a limitação está explícita onde o tema aparecer.

### P1-3 (P1) — `anti_alignment_score` não é "circular resultant"

**Fato:** `planet9lab/metrics.py:47-53` — a métrica usa a **média aritmética**
das distâncias angulares até o alvo anti-alinhado (`1 - mean(distances)/180`),
não o comprimento do vetor resultante circular (que é o que
`apsidal_clustering_R` usa). A distância angular em si está correta (wrap de
360°), então não é bug de física — é nomenclatura/documentação.
`docs/METRICAS.md` só lista o nome do campo, não a fórmula.

**Duas opções (decisão do usuário):**
- **A. Renomear/documentar (recomendado, sem mudar valores):** renomear para
  algo como `mean_angular_alignment_score` (ou documentar explicitamente
  "distância angular média normalizada") no código, em `docs/METRICAS.md` e
  nos nomes de coluna/relatório, mantendo os valores publicados intactos.
  Implica `anti_alignment_score` → novo nome em `metrics.py`, `run.py`
  (build_metrics_row), `explain.py` (lista de métricas), `report.py` e
  qualquer teste que referencie o nome; preservar alias/deprecation se o
  usuário preferir compatibilidade.
- **B. Trocar pela circular-resultant formal:** mudar a implementação (muda
  valores já publicados nas runs reais — decisão científica, só o usuário
  autoriza; invalidaria comparações com as runs de 1 Myr existentes).

**Critério de aceite:** nome/documentação da métrica refletem exatamente a
fórmula usada; `docs/METRICAS.md` documenta a fórmula; testes passam; ruff
limpo. Se opção B, o usuário foi explicitamente avisado sobre a quebra de
valores publicados.

### P2-4 (P2) — Schema aceita `i_deg ∈ [0,180]` sem aviso de regime

**Fato:** `planet9lab/schemas.py:27` (`i_deg: float = Field(ge=0, le=180)`) —
aceita retrógrado e `i` próximo de 90° sem nenhum aviso de que o modelo
secular/apsidal (`anti_alignment_score`, `delta_pomega_stability`) foi
pensado para regime prógrado/moderado (literatura Planeta 9). Nenhuma
checagem de regime existe em `planet9lab/*.py`. O corte `i > 30°` do Quadro 2
é decisão de escopo, não validação de regime Kozai-Lidov.

**Duas opções (decisão do usuário):**
- **A. Blocker/aviso no código (recomendado):** adicionar um `blocker`
  consultivo (não bloqueante) quando um candidato tiver `i_deg > ~90°` ou
  próximo de 90° (ex. `i_deg >= 80`?), registrado em `audit/blockers.json` e
  na linha do candidato em `candidates_status.csv`, sem invalidar a run.
  Documentar no código e em `docs/LIMITACOES.md` que o modelo não foi
  validado para regime Kozai-Lidov/retrógrado.
- **B. Só nota em `docs/LIMITACOES.md`:** sem mudança de código; adicionar a
  ressalva de regime ao documento de limitações.

**Critério de aceite:** ou existe checagem visível (blocker/aviso) para
`i` fora do regime prógrado moderado, ou a limitação está explícita em
`LIMITACOES.md`; testes passam; ruff limpo.

## 5. Pendências transversais (não são itens da tabela, mas afetam o fechamento)

- **Decidir sobre `runs/` e `.gitignore`** antes de qualquer commit (ver
  Seção 1). As duas runs reais + `runs/latest_run.txt` estão trackeadas.
- **`results/hardware_benchmark.json` é de sandbox**, não da máquina real —
  não usar para justificar 4e9 yr no artigo (só para decidir ordem de
  grandeza do custo). Remedir na máquina real se a decisão P0-1 for "rodar".
- **Cruzamento externo dos 13 ETNOs** com a Tabela A1 de arXiv:1406.0715
  (De la Fuente Marcos & De la Fuente Marcos 2014) nunca foi feito campo a
  campo — perguntar ao usuário se quer incluir esse passo.
- Ao final do fechamento, atualizar `docs/historico/` com um relatório de
  correção V3 seguindo o padrão dos existentes, e/ou gerar um
  `PROMPT_CONTINUIDADE` atualizado se ainda houver pendências para nova sessão.

## 6. Ordem sugerida de trabalho (confirmar com o usuário)

1. **P1-2** (mais simples, sem decisão científica) — documentar/verificar.
2. **P1-3 e P2-4** (ambas dependem de decisão A/B do usuário; apresentar as
   opções e implementar a escolhida).
3. **P0-1** (a mais cara e dependente de decisão A/B + benchmark) — por
   último.
4. Relatório V3 em `docs/historico/` e checagem final do gate.

## 7. Comandos úteis

- Gate: `python3 -m pytest -q` · `python3 -m ruff check . --no-cache` ·
  `python3 main.py doctor`.
- Canônico secular (somente com autorização explícita):
  `python3 scripts/run_artigo.py` (default `secular.yaml`); smoke barato:
  `python3 scripts/run_artigo.py --budget configs/budgets/low.yaml`.
- Benchmark de hardware (máquina real do usuário):
  `python3 scripts/benchmark_integration_cost.py`.
- Instalar python-docx (só para edição do artigo, com permissão):
  `python3 -m pip install --break-system-packages python-docx`.
- Screen manual: `python3 main.py screen --budget configs/budgets/<b>.yaml
  --candidates data/candidates_quadro2.csv --etnos
  data/etnos/catalog_validated.csv --run-root /tmp/xxx`.

## 8. Referências externas

- Drive "PROJETO PLANETA 9" (documentos do artigo):
  https://drive.google.com/drive/folders/1znTIGi8rADgKK9e60FzwvYNG5saI30P_?usp=sharing
- Artigo: `docs/Artigo_FEBRACE_revisado.docx` (Seções 4, 8.2, Tabelas 2 e 3).
- Auditoria V3: `docs/AUDITORIA_V3_PLANET9_SCREENING_LAB.md`.
- Histórico: `docs/historico/` (CHANGELOG_V2, PLANO_CORRECAO_POS_AUDITORIA_V2,
  RELATORIO_EVOLUCAO_POS_V2, RELATORIO_V2_ROBUSTEZ_MINIMA,
  PROMPT_CONTINUIDADE_2026-08-12).
