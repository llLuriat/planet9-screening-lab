# Changelog V1 -> V2

Registro do que foi implementado em cada bloco do plano de evolução (ver o
prompt original em `docs/historico/` ou no histórico de conversas). Isto existe
para que qualquer pessoa auditando o repositório entenda o estado atual sem
precisar de acesso ao histórico de chat que produziu essas mudanças.

## Bloco 1 - Horizonte de integração secular

- `configs/budgets/secular.yaml`: `integration_years` em escala Myr (1e8, ponto
  de partida conservador - ver `docs/LIMITACOES.md`), `timestep_years` derivado
  fisicamente do período de Júpiter (`planet9lab.physics.recommended_timestep_years`).
- Checkpointing real (`ReboundEngine.run_branch_checkpointed`): salva estado via
  REBOUND `Simulationarchive` e séries de ΔE/E0, ΔL/L0, Δϖ em CSV a cada
  `checkpoint_interval_years`; retoma do último checkpoint em vez de reiniciar.
- `resume_run` deixou de ser stub: recomputa apenas candidatos pendentes,
  usando cache em disco (`candidates_results_cache.json`) por candidato e os
  checkpoints de engine já salvos.
- Critério quantitativo de "Δϖ estável" (`planet9lab.metrics.delta_pomega_stability`):
  estatística circular sobre a segunda metade da série temporal.
- `scripts/benchmark_integration_cost.py`: mede custo real de integração no
  hardware onde for executado (não pode ser medido em ambiente sem REBOUND).

## Bloco 2 - Monte Carlo / QMC do espaço de parâmetros

- `planet9lab/montecarlo.py`: amostragem via sequência de Halton (QMC) ou
  uniforme sobre `[M9, a9, e9, i9]`, com limites documentados a partir da
  literatura (`configs/montecarlo/parameter_space.yaml`).
- Funil de 4 estágios computados (não hardcoded): 2 analíticos e gratuitos
  (bounds físicos, proxy de separação de Hill vs. Netuno) sobre todos os
  pontos amostrados; 2 via REBOUND real (estabilidade curta, depois
  alinhamento apsidal em escala secular), limitados por
  `max_stage2_samples`/`max_stage3_samples` por custo computacional.
- Os 2 filtros que o plano original pede e que não têm implementação
  numérica neste código (Hamiltoniano secular, detectabilidade IR/óptico)
  ficam marcados `not_implemented` em `results/reduction_funnel_summary.json`.
- Comando: `python main.py montecarlo-scan`.

## Faxina de organização (pós-bloco 2)

- Runs de desenvolvimento/teste antigas (pré-secular, incluindo uma leftover
  de teste interno com REBOUND simulado) removidas de `runs/`.
- `AUDITORIA_V1_PLANET9_SCREENING_LAB.md` e `RELATORIO_CORRECAO_V1_POS_AUDITORIA.md`
  movidos da raiz para `docs/historico/` (histórico, não estado atual).
- Corrigido um pacote local `pytest/` na raiz que sombreava qualquer pytest
  real instalado (`python -m pytest` rodava um shim de 40 linhas sem
  fixtures/monkeypatch em vez do pytest de verdade, mesmo depois de
  `pip install pytest`). Movido para `scripts/offline_pytest_shim/`,
  alcançável só por invocação explícita.
- Novo `python main.py doctor`: diagnóstico de ambiente que funciona mesmo
  se pydantic/rebound estiverem ausentes ou quebrados (não depende deles).
  `main.py` agora trata esse comando como caso especial antes de importar o
  resto do pipeline, para nunca morrer com um traceback cru.
- Novos `python main.py status` / `python main.py watch`: leem
  `status.json`/`heartbeat.json`/os CSVs de checkpoint da run mais recente
  (ou de uma run específica) e mostram progresso, incluindo ETA estimado por
  candidato/branch para runs em escala secular. Implementados em
  `scripts/watch_progress.py` (dependência leve, só `pyyaml` - continua
  funcionando mesmo se pydantic/rebound estiverem quebrados).
- `README.md` reescrito como guia organizado por fluxo de trabalho em vez de
  lista plana de comandos.

## Pendente (blocos 3, 4, 5 do plano original)

- Bloco 3+4: candidatos alinhados ao Quadro 2 do artigo, `article_section_ref`
  no manifest, `scripts/export_to_article.py`.
- Bloco 5 (parcial - ver seção de fusão abaixo): propagação de incerteza,
  modelo de detectabilidade real, modelo de viés observacional.

## Fusão com a branch de robustez (leave-one-out, modelos nulos)

Uma sessão paralela implementou boa parte do item 5 do plano original
(`leave-one-out`, `convergence`, `validate-top`, `null-models`, diagnósticos,
famílias de candidatos, catálogo V2) enquanto esta trabalhava nos blocos 1-2.
As duas linhas de trabalho divergiram sem que nenhuma soubesse da outra até o
usuário fornecer o estado real do projeto para comparação.

Auditoria revelou:

- `paramscan.py`, criado antes de qualquer bloco desta sessão, já existia
  órfão (nunca importado/wireado) desde o upload inicial do projeto - e esta
  sessão criou `montecarlo.py` do zero, duplicando o mesmo objetivo (item 2),
  sem perceber que `paramscan.py` já existia. Os dois arquivos foram mantidos
  separados (não fundidos); `montecarlo.py` é o wireado no CLI
  (`montecarlo-scan`). `paramscan.py` permanece órfão - decisão futura
  pendente sobre unificá-los ou remover um dos dois. **DECIDIDO em 2026-08-11
  (correções pós-auditoria `simulador_v2_doctor_fix`): arquivado em
  `scripts/archived/paramscan.py` com nota de descontinuação.** `montecarlo.py`
  é a implementação oficial do item 2 (ver seção "Correções pós-auditoria"
  abaixo).
- Em algum ponto anterior a esta fusão, `cli.py` da branch de robustez foi
  sobrescrito (provavelmente por uma cópia de `run.py`/`cli.py` desta sessão),
  perdendo a wiring dos comandos `leave-one-out`/`convergence`/`validate-top`/
  `null-models`/`diagnose-*`/`candidate-families` - as funções em
  `robustness.py`/`diagnostics.py`/`families.py` continuavam corretas e
  intactas, só não eram mais alcançáveis via `python main.py`. A mesma
  sobrescrita perdeu a correção de `timestamp_id()` com microssegundos
  (mencionada em `RELATORIO_EVOLUCAO_POS_V2.md`).
- `robustness.py` tinha duas definições da função `null_models` (a segunda,
  mais otimizada, sobrescrevia a primeira silenciosamente - código morto).

Correções aplicadas durante a fusão:

- `cli.py`: reconectados todos os comandos de robustez, mantendo
  `montecarlo-scan`/`status`/`watch`/`doctor` desta sessão.
- `timestamp_id()` e a subpasta de `rescore`: microssegundos restaurados.
- `robustness.py`: definição morta de `null_models` removida (a versão
  otimizada, que reusa a integração do ramo sem P9 entre candidatos, é a que
  fica). `build_null_etnos` foi acidentalmente removida junto na primeira
  tentativa de limpeza e restaurada.
- `schemas.py`: `null_model_integration_years` e o validador de aliases
  legados (`screen_t_myr`, `candidates`, etc.) mesclados.
- `loaders.py`: `selected_etnos()` (seleção auditável por `min_a_au`/`min_q_au`/
  validação) mesclada.
- `audit.py`: checagem de artefatos V2 ausentes mesclada.
- `report.py`: `build_report()` ganhou o parâmetro `v2` opcional e a seção
  "Robustez V2"; corrigido mojibake (texto duplicado com encoding corrompido,
  ex. "nÃ£o" ao lado de "não") que existia no texto original da branch de
  robustez.
- `run.py`: `etno_catalog_v2`/`etno_selection_config` em `default_paths()`,
  `etno_catalog_blockers()`, `write_seed_stability()` mesclados; `resume_run`
  ganhou fallback defensivo para `completed_now` quando o cache de resultados
  está mais atualizado que `candidates_status.csv`.
- Copiados de volta: `diagnostics.py`, `families.py`, `robustness.py`,
  `data/etnos/catalog_v2.csv` (+ `catalog_sources.md` +
  `catalog_validation_report.md`), `configs/science/etno_selection.yaml`,
  `configs/scoring/v2_weights.yaml`, `configs/budgets/serious.yaml`,
  `tests/test_v2_robustness.py`, `tests/test_post_v2_evolution.py`.

Validação: todos os comandos de robustez testados de ponta a ponta (com um
stub local de REBOUND/pydantic, já que este ambiente de desenvolvimento não
tem rede para instalar as dependências reais); 44 testes unitários/lógicos
passando sem fixtures do pytest real. **Recomenda-se fortemente rodar
`python -m pytest` completo no ambiente real (com pydantic e REBOUND de
verdade) antes de confiar cegamente nesta fusão** - o stub local já revelou
e escondeu bugs reais (ex. o de `build_null_etnos` só apareceu ao testar com
REBOUND simulado; um bug de introspecção do próprio stub por outro lado quase
me fez reportar um falso positivo em `test_serious_budget_loads_aliases`).

## Correções pós-auditoria (simulador_v2_doctor_fix, 2026-08-11)

Executadas conforme `docs/historico/PLANO_CORRECAO_POS_AUDITORIA_V2.md`:

- `paramscan.py` arquivado em `scripts/archived/paramscan.py` com nota de
  descontinuação; `montecarlo.py` é a implementação oficial do item 2
  (fecha a decisão pendente registrada acima). Typo de docstring
  (`seeAssistant`) corrigido no arquivo movido.
- Testes isolados de `runs/` real: `RUNS_DIR` + parâmetro `run_root` opcional
  em `run_screen`/`run_smoke`/`run_compare`/`execute_run`/
  `run_montecarlo_scan`, com fixture autouse em `tests/conftest.py` apontando
  para `tmp_path`. Rodar `pytest` não cria mais pastas nem sobrescreve
  `runs/latest_run.txt` do projeto.
- Duplicação de artefatos na raiz da run unificada em `sync_root_copy()` /
  `write_root_copies()`; `robustness.py` (`refresh_v2_report`, `merge_blocker`)
  passou a usar o helper em vez de escrever à mão; teste de paridade
  byte-a-byte das 9 cópias.
- Observabilidade: `logging` configurado na CLI; `run.py`/`engine.py` com
  loggers; falha de candidato grava `audit/crash_log.jsonl` (tipo, `str(exc)`
  e traceback). `print()` de saída ao usuário intacto.
- `git_commit` (HEAD do repo) registrado em `audit/run_manifest.json` e
  `environment.json` para reprodutibilidade.
- `ruff check . --fix`: 30 avisos corrigidos; restam 6, todos pré-existentes
  ou justificados no código (idiom de NaN, shim offline, estilo).

Validação: 94 testes passando (89 originais + 5 novos), `python main.py doctor`
OK, `ruff check .` com 6 avisos justificados, `screen` real + `audit-run`
=> `AUDIT OK`.
