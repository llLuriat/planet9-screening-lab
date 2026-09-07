# Relatório de Correção Auditoria V3 — Planet9 Screening Lab

## Veredito honesto

ACCEPTED_WITH_WARNINGS

Os 13 achados da Auditoria V3
(`docs/AUDITORIA_V3_PLANET9_SCREENING_LAB.md`) foram endereçados. Todos os
achados de **código** foram corrigidos e verificados (116 testes, `ruff`
limpo, `doctor` OK). O achado de maior gravidade (P0-1 — artigo com 7
resultados dinâmicos sem run correspondente) foi fechado pela **reescrita do
artigo** para refletir apenas o que foi executado, não pela execução secular
(que permanece pendente e exige decisão de hardware/horizonte). Duas
limitações científicas permanecem explícitas e não são elevadas a resultado
validado: estabilidade entre seeds (P1-2) e regime de inclinação não
prógrado-moderado (P2-4).

## O que foi corrigido nesta sessão (4 itens restantes)

| ID | Correção aplicada |
|---|---|
| P1-3 | `anti_alignment_score` renomeado para `mean_angular_alignment_score` (média angular média normalizada, **não** estatística circular/resultant). Renome aplicado em `metrics.py` (função + chave de métrica + `dynamic_score`), `schemas.py` (`SingleRunResult`), `engine.py` (2 call sites), `run.py` (RANKING_FIELDS + build de colunas), `rescore.py`, `diagnostics.py`, `explain.py`, `robustness.py` e `docs/METRICAS.md` (fórmula documentada). Compatibilidade preservada: alias `anti_alignment_score = mean_angular_alignment_score`, leitura tolerante das colunas legadas das 2 runs reais (`metric_column_value`) e normalização de colunas ao reescrever ranking (`normalize_metric_columns`). Valores publicados intactos. |
| P2-4 | Blocker **consultivo** `inclination_out_of_model_regime` para candidatos com `i_deg >= 80` (regime Kozai-Lidov / retrógrado, não validado pelo modelo secular/apsidal). Implementado em `policy.py` (`inclination_regime_blocker`, limiar `INCLINATION_REGIME_THRESHOLD_DEG = 80.0`, severidade `science_limit`), integrado em `build_candidate_row` (coluna `blockers` do ranking/candidates_status) e registrado em `audit/blockers.json` (com `candidate_id`) sem invalidar a run. Documentado em `docs/LIMITACOES.md`. Testes: `test_policy.py` (5) + integração em `test_run_artifacts.py`. |
| P0-1 | Reescrita do artigo `docs/Artigo_FEBRACE_revisado.docx` (opção A, sem run secular): Seção 4 (parágrafos de horizonte e retenção), Tabela 2 (7 linhas), Seção 5 (parágrafos de precessão e ressonâncias), Tabela 5/funil (Seção 7) e Seção 8.2 (cenário preferido). O artigo agora afirma apenas o executado (1 Myr; 2 experimentos de sensibilidade: rotação de ω9 do candidato row6 e varredura de i = 31°–35° do row4); os outros 5 resultados foram classificados como "não executado nesta versão". Strings sem lastro removidas (verificação via busca: "1 a 4 Gyr", "80% dos ETNOs", "sem ejeções", "< 500 Myr", "Oort interna", "órbitas polares previstas", "Ammonite desalinhado" — todas 0 ocorrências como resultado). Backup do docx original: `/tmp/opencode/Artigo_FEBRACE_revisado_pre_P0-1.docx`. |
| P1-2 | Sem mudança de código — `docs/LIMITACOES.md` reforçado: nenhuma run real testa múltiplas seeds (todas usam `seeds: [12345]`, resumo sai `"enabled": false`); estabilidade entre seeds permanece PENDENTE explícita, sem elevar "robustez validada". |

## O que foi corrigido na sessão anterior (9 itens, já verificados)

| ID | Correção aplicada |
|---|---|
| P0-2 | `load_candidates` ordena por `candidate_id` antes de truncar; nova `load_candidates_with_excluded`; excluídos registrados como `not_evaluated_capacity_limit` no `data_manifest.json` e `audit/run_manifest.json`; propagado via `plan_run`/`run_smoke`/`run_screen`/`execute_run`. |
| P1-1 | `--seed` documentado como inerte no `--help` (`cli.py`) e no relatório; campo `seed_effect: "inert_for_screen_compare_fixed_catalog"` no manifest. |
| P1-4 | `weak_delta_floor` removido de `configs/scoring/v2_weights.yaml` e `default_weights.yaml` (campo morto). |
| P1-5 | Divisores `1e-4`/`1e-3` extraídos para `DRIFT_PENALTY_DIVISOR_NUMERICAL_HEALTH`/`DRIFT_PENALTY_DIVISOR_STABILITY` (`metrics.py`) com justificativa documentada ancorada ao texto do artigo (padrão-ouro do `DELTA_POMEGA_LIBRATION_R_THRESHOLD`). |
| P1-6 | `doctor.py` verifica `Path(conteúdo de latest_run.txt).exists()` em vez de só a existência do arquivo-ponteiro. |
| P2-1 | `[tool.ruff.lint] select` pinado no `pyproject.toml` (11 regras); erros da auditoria corrigidos (TRY004, RUF059, FLY002×2, BLE001, PLR0124) + W293 + E402×6 com `# noqa: E402` justificado. |
| P2-2 | `docs/LIMITACOES.md`: item "candidatos de exemplo não substituídos" corrigido para apontar `data/candidates_quadro2.csv` + `CANDIDATOS_QUADRO2.md`. |
| P2-3 | `--run-root` exposto no CLI (`screen`, `compare`, `smoke`, `montecarlo-scan`) e repassado às funções de `run.py`. |
| P2-5 | `tests/test_audit_v3_code_fixes.py` — 9 testes: ordem determinística de `load_candidates`, `not_evaluated_capacity_limit` nos manifests, ranking byte-idêntico entre seeds, `seed_effect` inerte. |

## Limitações que permanecem (explícitas, não elevadas a validação)

- **Run secular não executada.** O artigo foi reescrito (opção A) porque a
  execução secular das 7 configurações do Quadro 2 exigiria
  horas–dias/candidato e decisão de hardware/horizonte. `secular.yaml` (1e8 yr)
  continua nunca executado. As únicas 2 runs reais permanecem de 1 Myr. A
  execução canônica secular é a via para, no futuro, reverter os itens marcados
  como "não executado nesta versão".
- **Estabilidade entre seeds** (P1-2): nenhuma run real testa múltiplas seeds;
  permanece PENDENTE explícito.
- **Regime de inclinação** (P2-4): modelo secular/apsidal não validado para
  `i` próximo de 90° ou retrógrado; aviso consultivo por candidato.
- **Viés observacional** ausente (`no_observational_bias_model`) e **catálogo**
  ainda não validado externamente (limitações pré-existentes do V1/V2).
- **`results/hardware_benchmark.json` é de sandbox**, não da máquina real
  E3-1230 v2 — não deve justificar alegações de custo do artigo.
- **`runs/` sem `.gitignore`**: as 2 runs reais + `runs/latest_run.txt` estão
  trackeadas. Decidir com o usuário o que versionar antes do próximo commit.

## Resultado dos testes

Total: 116 testes (110 da sessão anterior + 6 novos desta sessão: 5 em
`tests/test_policy.py` para o blocker de inclinação e 1 em
`tests/test_run_artifacts.py` de integração do blocker).

Cobertura adicionada nesta sessão:

- Rename P1-3: `mean_angular_alignment_score` = alias legado; `dynamic_score`
  com chave renomeada; fallback de leitura de colunas legadas validado contra
  uma cópia da run real `experiment_angle_robustness_...` (`explain`,
  `diagnostics`, `rescore` — valores preservados, ex. 0.643215).
- Blocker P2-4: `inclination_regime_blocker` (limiar, retrograde, None,
  prograde); integração verifica blocker no ranking/candidates_status/blockers.json
  sem invalidar a run.

## Comandos executados (gate final)

| Comando | Resultado |
| --- | --- |
| `python3 -m pytest -q` | PASS — 116 passed |
| `python3 -m ruff check . --no-cache` | PASS — All checks passed |
| `python3 main.py doctor` | PASS — Tudo certo, REBOUND real |
| `python3 -c "from docx import Document; Document('docs/Artigo_FEBRACE_revisado.docx')"` | PASS — docx íntegro, 5 tabelas |

## Arquivos tocados nesta sessão

- `planet9lab/metrics.py` (rename P1-3 + doc)
- `planet9lab/schemas.py` (campo `SingleRunResult.mean_angular_alignment_score`)
- `planet9lab/engine.py` (2 call sites do campo renomeado)
- `planet9lab/run.py` (RANKING_FIELDS, `metric_column_value`,
  `normalize_metric_columns`, `inclination_regime_blocker` integrado,
  blockers por candidato no payload)
- `planet9lab/policy.py` (novo `inclination_regime_blocker` + limiar)
- `planet9lab/rescore.py`, `planet9lab/diagnostics.py`, `planet9lab/explain.py`,
  `planet9lab/robustness.py` (leitores com fallback de coluna legada)
- `docs/METRICAS.md` (fórmula documentada), `docs/LIMITACOES.md` (P1-2/P2-4)
- `docs/Artigo_FEBRACE_revisado.docx` (P0-1 — reescrita)
- `tests/test_metrics.py`, `tests/test_policy.py`, `tests/test_run_artifacts.py`

## Decisões de escopo tomadas com o usuário

- P1-3: **opção A** (renomear/documentar mantendo valores publicados; não trocar
  pela circular-resultant formal).
- P2-4: **opção A** (blocker consultivo no código; não apenas nota em
  LIMITACOES.md).
- P0-1: **opção A** (reescrita do artigo; o usuário não autorizou run que leve
  horas–dias nesta etapa — execução secular registrada como pendência).
- P0-1 limiar de regime: `i_deg >= 80` (próximo de 90°/retrógrado).
