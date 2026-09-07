# Prompt de continuidade — Simulador Planeta 9 (sessão 2026-08-12)

Este arquivo é o contexto de continuidade para uma nova sessão de chat.
Leia este documento por completo e assuma que TODO o estado descrito aqui é
verdadeiro — não repita trabalho já feito, não invente dado, não decida
escopo científico sozinho. Arquivos de referência externa: pasta Drive
`PROJETO PLANETA 9` (link no fim), `docs/Artigo_FEBRACE_revisado.docx`,
`docs/historico/CHANGELOG_V2.md`, `docs/historico/PLANO_CORRECAO_POS_AUDITORIA_V2.md`.

## Estado do repositório (IMPORTANTE)

- Working dir: `/workspace`, branch `master`, remote inexistente, único
  commit: `a207b6d Initial commit`.
- **NADA está commitado além do Initial commit.** 33 itens modificados/novos
  no working tree (todo o trabalho abaixo). O usuário disse: **"o commit eu
  faço ao final dessas etapas"** — NÃO commitar sem pedido explícito; quando
  o usuário pedir, `git add -A` + commit em `master` (sem push, sem remote).
- `.gitignore` cobre `__pycache__/`, `*.py[cod]`, `.pytest_cache/`,
  `.ruff_cache/`, `*.egg-info/`, `build/`, `dist/`, `runs/*/`,
  `runs/latest_run.txt`. `runs/README.md` é trackeado.
- Ambiente: `python3` (não `python`). Dependências instaladas globalmente:
  numpy pandas pydantic pyyaml typer rich matplotlib pytest ruff rebound
  (rebound 5.1.1). REBOUND real disponível, sem fallback analítico.
- Gate padrão: `python3 -m pytest -q` (101 testes) + `python3 -m ruff check .`
  (6 avisos pré-existentes justificados) + `python3 main.py doctor` (tudo OK).

## Regras de execução (não negociáveis, definidas pelo usuário)

1. **Não inventar dado científico.** Número que não vier do artigo, do código
   ou de fonte citável = marcado explicitamente como suposição + motivo.
2. **Nenhuma decisão de escopo científico/metodológico é minha.** Parar,
   explicar as opções reais e esperar confirmação explícita antes de codificar.
3. **Nenhuma execução silenciosa.** Mudança de arquivo, run real, commit:
   sinalizar o quê/por quê/efeito antes.
4. **Mudança mínima.** Não refatorar/reformatar código adjacente sem pedido.
   `data/candidates_example.csv` e `data/etnos/catalog.csv` (placeholder,
   usados pelos testes) NÃO são sobrescritos — usar overrides/novos arquivos.
5. **Toda alegação do artigo precisa de lastro real** (código, run, citação).
   Sem lastro = marcada como pendente, nunca preenchida com número plausível.
6. Proibido `rm`/delete sem confirmação; preferir mover para backup.

## O que já foi feito (não refazer)

### Fase V1→V2 (histórico)
Funil Monte Carlo/QMC em 3 estágios (`configs/montecarlo/parameter_space.yaml`),
budget secular (`configs/budgets/secular.yaml`, hoje `integration_years: 1e8`),
robustez V2 (leave-one-out, convergence, validate-top, null-models). Ver
`docs/historico/RELATORIO_EVOLUCAO_POS_V2.md`.

### Auditoria / doctor_fix (aplicado, 19 arquivos tocados)
- P0: `RUNS_DIR = ROOT / "runs"` + `_runs_dir()` + `run_root` opcional nos 5
  entry points (`run_screen/run_smoke/run_compare/execute_run/run_montecarlo_scan`).
  Fixture autouse `tests/conftest.py` isola testes de `runs/` real. `doctor.py`
  lê `runs/latest_run.txt` só para diagnóstico (intencional).
- P1: `sync_root_copy()`/`write_root_copies()` + `ROOT_COPY_MAP` (module level,
  `planet9lab/run.py`); 2 testes de paridade byte-a-byte iterando o mapa.
- P1 obs: `append_crash()` grava `audit/crash_log.jsonl` no laço de candidatos;
  `logger.exception` nos catches; `logging.basicConfig` em `cli.main()`.
- P2: `git_commit()` no `environment_info()`/manifest (fallback not-a-git-repo).
- P8: `planet9lab/paramscan.py` arquivado em `scripts/archived/paramscan.py`
  (cabeçalho DISCONTINUED; sucessor = `montecarlo.py`).
- ruff: `ruff check . --fix` + fixes manuais; restam 6 avisos justificados
  (TRY004 config.py:13, RUF059 explain.py:19, FLY002 sample_data.py:114 e
  test_post_v2_evolution.py:42, BLE001 offline_pytest_shim:36, PLR0124
  watch_progress.py:67).

### Quadro 2 integrado (dados reais do artigo — workspace é o simulador principal)
- `data/candidates_quadro2.csv` — 7 candidatos reais (Q2, Seção 4):
  row1_lowmass_close (4,300,0.20), row2_highmass_close (10,300,0.50),
  row3_far_eccentric (6,800,0.60), row4_incl_boundary (6,500,0.35,i=32),
  row5_partial_alignment (5,400,0.30), row6_preferred (6,500,0.35,i=20),
  row7_highmass_viable (7,600,0.45,i=18). Todos com ω9=200°/Ω9=270°/M0=180°.
  Baseline (linhas 1,2,3,5 sem i9; linha 3 sem M9) = Cenário 6:
  M=6,a=500,e=0.35,i=20.
- `data/etnos/catalog_validated.csv` — 13 ETNOs reais (a>150,q>30), De la
  Fuente Marcos & De la Fuente Marcos 2014 (arXiv:1406.0715, Tabela A1).
- `planet9lab/cli.py` + `planet9lab/run.py` — flags `--candidates`/`--etnos`
  no comando `screen` (byte-idênticos ao deliverable `simulador_v2_quadro2.zip`).
- `configs/grids/p9_target_region.yaml` — ranges do Quadro 1:
  mass [4.5,8], a [380,680], e [0.28,0.56], i [12,28].
- `docs/CANDIDATOS_QUADRO2.md`, `docs/Artigo_FEBRACE_revisado.docx`,
  `results/hardware_benchmark.json` (benchmark de SANDBOX — não é o benchmark
  real; NÃO serve para validar secular.yaml).

### Experimentos de sensibilidade (separados do canônico, P0/P2)
Infra:
- `configs/experiments/robustness_screen.yaml` — budget 1 Myr (`dt=P_J/20`),
  screen barato-but-meaningful (mesma filosofia do stage-2 do funil). NÃO é
  secular; NÃO resolve alinhamento Gyr.
- `scripts/experiments/run_grid_experiment.py` — driver: base_catalog × eixos →
  variantes → `execute_run` (sem nova física). Flags: `--seed`, `--run-root`,
  `--budget-override` (test-only).
- `tests/test_experiments.py` — 5 gates (configs bem-formados, formato do grid,
  elementos não-varridos preservados, IDs únicos).
- Configs: `angle_robustness.yaml` (base = cenario6_base_candidate.csv
  [row6_preferred], grid ω9 {0,90,180,200,270}, inclui nominal 200) e
  `i_boundary_scan.yaml` (base = line4_base_candidate.csv [row4_incl_boundary,
  i=32], grid i {31,32,33,34,35}). Ambos `etno_catalog:
  data/etnos/catalog_validated.csv`.
- `scripts/run_artigo.py` — wrapper do canônico: sempre usa
  `candidates_quadro2.csv` + `catalog_validated.csv` (anti-footgun de
  placeholder). `--budget` default `configs/budgets/secular.yaml`.

### Resultados dos experimentos (runs REAIS em runs/, escopo 1 Myr)
1. `runs/experiment_angle_robustness_20260812T145545073924Z`:
   - Classificação estável: 5 ω9 todos `candidate_of_interest`, score 0.71–0.78
     (±~9%). Nominal ω9=200 em 4º (0.722).
   - Porém anti_alignment varia ±~30% com ω9 (0.357 em ω180 → 0.643 em ω0);
     nominal 200 → 0.395. Confirma P0: a sensibilidade é REAL no canal secular
     (não resolvida a 1 Myr; resolução exige Gyr = benchmark-gated).
   - stability ~0.9996, survival 1.0, R_cluster ~0.37 (planos).
2. `runs/experiment_i_boundary_scan_20260812T145800363579Z`:
   - Sem transição em i 31–35°: todos `candidate_of_interest`, scores planos
     (0.7212–0.7226, ~0.2%), survival 1.0, stability ~0.9997, R_cluster ~0.37.
   - Sonda única i=32° é representativa; o corte i>30° não discrimina a 1 Myr.
- Frase defensável p/ artigo (escopo 1 Myr): classificação robusta à ω9 (±10%)
  e a i na fronteira (sem transição 31–35°); componente anti-alinhamento oscila
  ~30% com ω9 — só resolvível em integração secular.
- `runs/latest_run.txt` aponta para o i_boundary_scan (mais recente). `runs/`
  é gitignored; os 2 runs + pointer estão lá.

## Decisões científicas (P0/P1/P2) — status

- P0 (Fase B, ângulos ω9/Ω9/M0): canônico mantém fixos (200/270/180). Teste de
  robustez = experimento `angle_robustness` (FEITO, ver resultado acima).
  Incluí ω9=200 nominal no grid — usuário pode querer só {0,90,180,270}.
- P1 ("1 a 4 Gyr" no artigo): manter, com proveniência no manifest. Depende do
  benchmark REAL (pendente). Não mexer em `secular.yaml` (1e8) sem esse dado.
- P2 (Linha 4, i>30°): manter sonda única i=32° no canônico; varredura =
  experimento `i_boundary_scan` (FEITO, sem transição a 1 Myr).

## Pendências reais (nada inventado)

1. **Benchmark de hardware REAL** (máquina do usuário):
   `python3 scripts/benchmark_integration_cost.py`. Hoje só existe o do sandbox
   (`results/hardware_benchmark.json`), que projeta 4e9 yr alcançável em
   48h/par — NÃO representativo, não usar para validar claim.
2. **Alegação "1 a 4 Gyr"** + valor de `secular.yaml` (hoje 1e8): dependem do
   benchmark real. Rodar canônico secular depois disso:
   `python3 scripts/run_artigo.py` (max_candidates 7; horas-dias).
3. Commit do working tree (usuário fará ao final destas etapas).
4. Opcionais: texto do artigo com os resultados de robustez; reavaliar grid de
   ω9 sem nominal; decidir se a varredura de i deve usar secular (Gyr) depois
   do benchmark.

## Próximos passos (ordem sugerida, confirmar com o usuário)

1. Benchmark real na máquina do usuário → decidir secular.yaml e a alegação.
2. `python3 scripts/run_artigo.py` para o ranking canônico secular dos 7.
3. Atualizar o artigo com a seção de robustez (frase acima) quando quiser.
4. Commit final (usuário).

## Comandos úteis

- Experimentos: `python3 scripts/experiments/run_grid_experiment.py
  configs/experiments/<nome>.yaml` (produção) ou `--budget-override
  configs/budgets/low.yaml --run-root /tmp/xxx` (wiring smoke, barato).
- Canônico: `python3 scripts/run_artigo.py` (secular) — ou `--budget
  configs/budgets/low.yaml` para smoke.
- Screen manual com catálogos reais:
  `python3 main.py screen --budget configs/budgets/<b>.yaml --candidates
  data/candidates_quadro2.csv --etnos data/etnos/catalog_validated.csv`.
- Gate: pytest, ruff, doctor (acima). Audit: `python3 main.py audit-run <dir>`.

## Referências externas

- Drive "PROJETO PLANETA 9":
  https://drive.google.com/drive/folders/1znTIGi8rADgKK9e60FzwvYNG5saI30P_?usp=sharing
  Contém: Artigo_FEBRACE_revisado.docx (id 1PzhY_jJUGn3ZWgrky71H8Y4YYfzJvRxJ),
  evolução do simulador (parcial).zip (1snj5SLLMGP-EQd7O3BQC0yntgjF1RHc4),
  LOG_SESSAO_Planeta9.md (1mCSxolIZb2tRduBVz4C0b-r_82IL7Z5c),
  Planeta9_Analise_Dinamica_ABNT (1).docx (1gvMPNRBv9qLQZNqP_-UA50eMFnUxYkbf),
  PROMPT_continuidade_Planeta9.md (1P-lzW0F3H7__ugO3lXtV0Vg-FOFHd9mt).
- O zip quadro2 já foi integrado ao workspace (acima); o artigo está em
  `docs/Artigo_FEBRACE_revisado.docx`.
