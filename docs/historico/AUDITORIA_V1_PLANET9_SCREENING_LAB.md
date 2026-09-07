# Auditoria V1 — Planet9 Screening Lab

## 1. Veredito geral

NOT_ACCEPTED

## 2. Resumo curto

O V1 é uma ferramenta headless funcional e conservadora, mas ainda não é um screening físico validado.
Os comandos principais executam e geram runs com ranking, métricas, blockers, hashes e relatório.
Não há UI, renderer, dashboard ou dependência visual detectada.
Claims fortes aparecem apenas como claims proibidos, não como conclusão permitida.
O controle com/sem P9 é gerado para todos os candidatos da run testada.
Porém, REBOUND real não está instalado nem usado; o motor é fallback analítico.
Os CSVs científicos canônicos, schemas completos, docs científicos e artefatos de run estritos estão incompletos.
A suíte tem apenas 5 testes e é majoritariamente caminho feliz.
Conclusão: serve como esqueleto auditável inicial, não como V1 aceito para banca crítica de IC.

## 3. Tabela de achados

| ID | Severidade | Categoria | Status | Descrição | Evidência | Correção recomendada |
| --- | --- | --- | --- | --- | --- | --- |
| F-001 | CRITICAL | REBOUND / física | FAIL | REBOUND real não está instalado e não é usado; o screening usa fallback analítico. | `python main.py physics-check` retorna `rebound_available: false`; `planet9lab/engine.py` só checa `importlib.util.find_spec("rebound")`. | Instalar/validar REBOUND real e fazer o motor executar integração física real antes de aceitar como screening físico. |
| F-002 | CRITICAL | Testes | FAIL | Há apenas 5 testes reais; o critério da auditoria marca menos de 10 testes como crítico para aceite. | `rg "^def test_" tests` encontrou 5 testes. | Ampliar suíte para schemas, catálogo, métricas, control_pair, audit_run, errors e claims. |
| F-003 | CRITICAL | CSV científico | FAIL | CSVs canônicos obrigatórios não existem. | `data/etnos/catalog.csv: False`; `data/solar_system/giants_epoch.csv: False`. | Criar CSVs canônicos com colunas exigidas e validação. |
| F-004 | MAJOR | CSV científico | FAIL | O CSV existente usa nomes incompatíveis com o contrato. | `data/etnos_example.csv` usa `object_id`, `inc_deg`, `M_deg`; faltam `name`, `i_deg`, `mean_anomaly_deg`, `epoch`, `frame`, `source`, `validation_status`. | Migrar para schema canônico ou documentar conversão explícita e testada. |
| F-005 | MAJOR | Estrutura | PARTIAL | Estrutura básica existe, mas faltam `pyproject.toml`, `.gitignore`, `configs/grids/`, `data/etnos/`, `data/solar_system/`. | Matriz de estrutura: esses itens retornaram `False`. | Completar estrutura mínima do projeto. |
| F-006 | MINOR | Estrutura | PASS | Divergência `p9lab/` vs `planet9lab/` não causa erro de import. | Pacote `planet9lab/` existe; `main.py` importa `planet9lab.cli`; comandos executam. | Manter nome ou documentar explicitamente. |
| F-007 | PASS | Proibições visuais | PASS | Nenhuma dependência/pasta visual proibida encontrada. | `rg -i "render|renderer|ui|OpenGL|..."` retornou exit 1, sem matches. | Nenhuma ação. |
| F-008 | MAJOR | Docs científicos | PARTIAL | Só existem 2 dos 7 docs científicos obrigatórios. | Presentes: `HIPOTESE_CIENTIFICA.md`, `CRITERIO_SELECAO_ETNOS.md`; ausentes: `MODELO_FISICO.md`, `METRICAS.md`, `LIMITACOES.md`, `PROTOCOLO_EXPERIMENTAL.md`, `COMO_INTERPRETAR_RESULTADOS.md`. | Criar documentação científica completa. |
| F-009 | PASS | Hipótese | PASS | Hipótese contém H0 e H1 e não apresenta prova do Planeta 9. | `docs/HIPOTESE_CIENTIFICA.md` contém seções `H0` e `H1`. | Nenhuma ação. |
| F-010 | MAJOR | Critério ETNO | PARTIAL | Critério registra intenção anti cherry-picking, mas usa dados de fixture e não define catálogo canônico real. | `docs/CRITERIO_SELECAO_ETNOS.md`; `data/etnos_example.csv`. | Formalizar critérios aplicados ao catálogo canônico e validar linhas incluídas/excluídas. |
| F-011 | MAJOR | Configs | PARTIAL | Configs centrais existem, mas faltam `configs/budgets/medium.yaml` e `configs/grids/p9_target_region.yaml`. | Matriz de configs: ambos `False`. | Adicionar budget médio e grid alvo. |
| F-012 | PASS | Bias config | PASS | `observational_bias.yaml` contém os campos exigidos. | `bias_model: none`, `blocker_if_none: true`, `max_evidence_level_without_bias_model: weak`. | Nenhuma ação. |
| F-013 | PASS | Protocolo | PASS | `protocol.yaml` contém versionamento e `allow_metric_changes_after_run: false`. | `configs/science/protocol.yaml`. | Nenhuma ação. |
| F-014 | CRITICAL | Schemas | FAIL | Não existem validações reais para `GiantPlanetRecord`, `BudgetConfig`, `RunConfig`, `SingleRunResult`, `ControlPairResult`; validações de ETNO/candidato são incompletas. | `planet9lab/schemas.py` só valida campos básicos de ETNO/candidato. | Implementar schemas completos com validações de domínio. |
| F-015 | MAJOR | Validação orbital | FAIL | Massa positiva, inclinação 0-180, ângulos 0-360, epoch/frame/source/status não são plenamente validados. | `validate_candidate` só checa `a_au > 0` e `0 <= e < 1`; ETNO não valida ranges. | Adicionar validação de ranges e campos obrigatórios científicos. |
| F-016 | CRITICAL | Motor físico | PARTIAL | Fallback é honestamente marcado, mas `ReboundEngine` não integra REBOUND real. | `physics-check` avisa fallback; `engine.py` calcula scores analíticos. | Substituir fallback por integração real para screening validado. |
| F-017 | PASS | Physics-check | PARTIAL | Registra `rebound_available`, conversões, órbita simples, energia/momento angular e sanidade P9; não mede drift de uma integração real. | Saída de `physics-check`: `rebound_available=false`, `sun_test_particle_orbit_simple_ok=true`. | Com REBOUND real, medir drift em simulação real. |
| F-018 | MAJOR | Experimento pareado | PARTIAL | Todos os candidatos da run geram `with_p9` e `without_p9`, mas o controle é analítico e pouco detalhado. | `results/control_pairs.csv` tem `with_p9_status=completed` e `without_p9_status=completed` para 5 candidatos. | Persistir detalhes completos de comparação e estados físicos. |
| F-019 | MAJOR | Métricas | PARTIAL | Há scores separados e delta, mas métricas são simplificadas e `anti_alignment`/`stability` não aparecem como campos explícitos. | `metrics_by_candidate.csv` tem `with_p9_apsidal_coherence`, `nodal`, `survival`, `numerical`, `delta_dynamic_score`. | Separar e nomear métricas científicas exigidas. |
| F-020 | PASS | Evidence cap | PASS | `no_observational_bias_model` limita evidence_level a `weak` na run. | Ranking da run: top positivo com `evidence_level=weak`; blocker ativo. | Nenhuma ação. |
| F-021 | PASS | Strong evidence | PASS | `strong` não aparece como evidence_level na run. | `ranking.csv` contém apenas `weak` e `none`. | Nenhuma ação. |
| F-022 | MAJOR | Run artifacts | FAIL | Vários artefatos estritos de run estão ausentes. | Ausentes: `status.json`, `heartbeat.json`, `events.log`, `config.resolved.yaml`, `environment.json`, `data_manifest.json`, `candidates_input.csv`, `candidates_status.csv`, `results/ranking.csv`, `reports/report.md`. | Gerar artefatos estritos e ajustar `audit-run` para exigi-los. |
| F-023 | MAJOR | Lock/heartbeat | NOT IMPLEMENTED | Não há `RUNNING.lock` nem lógica equivalente observável durante execução. | Matriz de artefatos: `RUNNING.lock: False`; nenhum código de lock em `run.py`. | Implementar ciclo de vida de run com lock/eventos/heartbeat. |
| F-024 | PASS | Ranking summary | PASS | `ranking_summary.json` contém todos os campos anti top 10 enganoso exigidos. | `results/ranking_summary.json`. | Nenhuma ação. |
| F-025 | PASS | Top 1 enganoso | PASS | Relatório explica quando o top 1 não está fortemente separado. | `report.md`: “O top 1 não está fortemente separado...”. | Nenhuma ação. |
| F-026 | MAJOR | Audit-run | PARTIAL | `audit-run` passa, mas só verifica uma lista menor que a lista estrita da auditoria. | `planet9lab/audit.py` não exige `status.json`, `events.log`, `reports/report.md`, etc. | Endurecer auditoria para a lista completa. |
| F-027 | PASS | Comandos obrigatórios | PASS | Todos os comandos obrigatórios executaram com exit code 0. | Ver seção 4. | Nenhuma ação para CLI básica. |
| F-028 | MAJOR | Rescore | PASS | `rescore` cria pasta própria e não sobrescreve ranking original; salva hashes e relatório. | `runs/screen_20260602T023149Z/rescore_20260602T023229Z/`. | Nenhuma ação imediata. |
| F-029 | MAJOR | Resume | PARTIAL | `resume` é stub: só imprime latest run; não lê `candidates_status.csv`, pending, nem eventos. | `python main.py resume` imprime path; `cli.py` não faz lógica de retomada. | Implementar resume real ou remover do aceite. |
| F-030 | MAJOR | Explain | PARTIAL | `explain-candidate` mostra métricas principais, controle, delta, blockers e claim, mas é textual e raso. | Saída para `p9_low_mass_weak`. | Aprofundar explicação com contribuições de métricas e limites. |
| F-031 | MAJOR | Why rejected | PARTIAL | Mostra motivo, delta, survival, energia e ETNOs perdidos; falhas numéricas são genéricas. | Saída para `p9_bad_geometry`: “Numerical failures: none recorded”. | Persistir falhas numéricas reais por candidato. |
| F-032 | MAJOR | Report | FAIL | `report.md` não contém a frase obrigatória literal nem várias seções exigidas. | Falta “Este projeto não confirma a existência do Planeta 9.”; faltam dados usados, região, config, rejeitados, reprodução em seção própria. | Expandir relatório técnico. |
| F-033 | PASS | Claims proibidos | PASS | Claims proibidos aparecem apenas em listas proibidas/código de validação; não aparecem como conclusão permitida. | `rg` encontra `confirmed_planet9`, etc. em `conclusion_policy.yaml` e `schemas.py`; sem uso como claim/status permitido. | Nenhuma ação. |
| F-034 | INFO | Encoding console | INFO | PowerShell exibiu mojibake em textos UTF-8, mas JSON/arquivos parecem UTF-8 corretos. | `Get-Content report.md` mostra `NÃ£o`; `blockers.json` mostra escapes Unicode válidos. | Opcional: orientar leitura UTF-8 ou ajustar console. |

## 4. Comandos executados

| Comando | Resultado | Observação |
| --- | --- | --- |
| `python -m pytest` | PASS, exit 0 | `5 passed, 0 failed`; cobertura insuficiente para aceite. |
| `python main.py plan --budget configs/budgets/low.yaml` | PASS, exit 0 | Mostrou 5 candidatos, blocker `no_observational_bias_model`, custo e arquivos previstos. |
| `python main.py init-data` | PASS, exit 0 | Regravou dados de exemplo. |
| `python main.py physics-check` | PARTIAL, exit 0 | Sanidade básica passou; `rebound_available: false`; fallback analítico. |
| `python main.py smoke` | PASS, exit 0 | Criou `runs/smoke_20260602T023131Z`. |
| `python main.py compare --candidate configs/candidates/mid_mass.yaml --budget configs/budgets/low.yaml` | PASS, exit 0 | Criou `runs/compare_20260602T023140Z`. |
| `python main.py screen --budget configs/budgets/low.yaml --seed 12345` | PASS, exit 0 | Criou `runs/screen_20260602T023149Z`. |
| `python main.py audit-run runs\screen_20260602T023149Z` | PASS, exit 0 | `AUDIT OK`, mas auditoria interna é menos estrita que a exigida. |
| `python main.py explain-candidate p9_low_mass_weak --from-run runs\screen_20260602T023149Z` | PASS, exit 0 | Mostrou rank, delta, métricas melhoradas, controle, blocker e claim. |
| `python main.py why-rejected p9_bad_geometry --from-run runs\screen_20260602T023149Z` | PASS, exit 0 | Mostrou rejeição por `did_not_improve_control`, delta negativo e saúde numérica. |
| `python main.py rescore --from-run runs\screen_20260602T023149Z --weights configs/scoring/default_weights.yaml` | PASS, exit 0 | Criou `rescore_20260602T023229Z` sem sobrescrever ranking original. |
| `python main.py resume` | PARTIAL, exit 0 | Apenas imprime latest run; não retoma candidatos. |

## 5. Arquivos ausentes

Estrutura:

- `pyproject.toml`
- `.gitignore`
- `configs/grids/`
- `data/etnos/`
- `data/solar_system/`
- `p9lab/` ausente, mas `planet9lab/` é consistente internamente.

Docs científicos:

- `docs/MODELO_FISICO.md`
- `docs/METRICAS.md`
- `docs/LIMITACOES.md`
- `docs/PROTOCOLO_EXPERIMENTAL.md`
- `docs/COMO_INTERPRETAR_RESULTADOS.md`

Configs:

- `configs/budgets/medium.yaml`
- `configs/grids/p9_target_region.yaml`

CSVs:

- `data/etnos/catalog.csv`
- `data/solar_system/giants_epoch.csv`

Artefatos ausentes na run `runs/screen_20260602T023149Z`:

- `RUNNING.lock`
- `status.json`
- `heartbeat.json`
- `events.log`
- `config.resolved.yaml`
- `environment.json`
- `data_manifest.json`
- `candidates_input.csv`
- `candidates_status.csv`
- `results/ranking.csv`
- `reports/report.md`

## 6. Artefatos gerados

Run principal auditada:

- `runs/screen_20260602T023149Z/SUCCESS.marker`
- `runs/screen_20260602T023149Z/report.md`
- `runs/screen_20260602T023149Z/ranking.csv`
- `runs/screen_20260602T023149Z/replay_command.txt`
- `runs/screen_20260602T023149Z/results/metrics_by_candidate.csv`
- `runs/screen_20260602T023149Z/results/control_pairs.csv`
- `runs/screen_20260602T023149Z/results/ranking_summary.json`
- `runs/screen_20260602T023149Z/audit/run_manifest.json`
- `runs/screen_20260602T023149Z/audit/blockers.json`
- `runs/screen_20260602T023149Z/audit/hashes.json`
- `runs/screen_20260602T023149Z/presentation/summary_for_presentation.md`
- `runs/screen_20260602T023149Z/presentation/top10_table.csv`

Rescore:

- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/ranking.csv`
- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/ranking_summary.json`
- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/rescore_report.md`
- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/rescore_hashes.json`
- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/old_scoring_hash.txt`
- `runs/screen_20260602T023149Z/rescore_20260602T023229Z/new_scoring_hash.txt`

## 7. Testes

Quantidade: 5 testes.

Arquivos:

- `tests/test_metrics.py`
- `tests/test_physics.py`
- `tests/test_policy.py`
- `tests/test_run_outputs.py`

Cobertura observada:

- Bias blocker e cap: sim, superficial.
- Claim policy: sim, superficial.
- Physics-check: sim, só caminho feliz.
- Ranking summary: sim, um caso.
- Run artifacts: sim, mas usa `audit_run` com lista reduzida.

Lacunas:

- Sem testes de `candidate_schema`.
- Sem testes de validação de catálogo canônico.
- Sem testes de `GiantPlanetRecord`.
- Sem testes de erro/ranges de massa, inclinação e ângulos.
- Sem testes de `apsidal_clustering` científico real.
- Sem teste explícito de `anti_alignment`.
- Sem teste robusto de scoring.
- Sem teste de `control_pair` como invariante obrigatório.
- Sem teste de `audit_run` contra artefatos estritos.
- Sem teste de `rescore` não sobrescrever original.

Classificação: CRITICAL para aceite do V1, porque há menos de 10 testes reais.

## 8. REBOUND

Instalado: não.

Usado: não como integrador físico real.

Fallback: sim, fallback analítico/determinístico.

Impacto científico:

O fallback está honestamente marcado no `physics-check` e no integrador `ias15_or_analytical_fallback`, então não há maquiagem direta. Porém, pela regra final da auditoria, sem REBOUND real instalado o projeto não pode ser aceito como screening físico validado. O máximo aceitável seria uso como protótipo de pipeline/auditabilidade.

## 9. Claims e segurança científica

Claims proibidos pesquisados:

- `confirmed_planet9`
- `planet9_found`
- `found_planet9`
- `discovered_planet9`
- `proved_planet9`
- `validated_planet9`
- `real_orbit_confirmed`
- `confirmed`
- `discovered`
- `proved`

Resultado:

PASS. Claims proibidos aparecem em listas proibidas (`configs/science/conclusion_policy.yaml`, `planet9lab/schemas.py`) e na lógica de validação. Não aparecem como claim/status permitido nem como conclusão de run.

Observação:

`rg` encontrou falso positivo em `Improved metrics` porque `improved` contém a substring `proved`; isso não é claim.

## 10. Controle com/sem P9

Na run auditada, todo candidato possui linha em `results/control_pairs.csv` com:

- `with_p9_status=completed`
- `without_p9_status=completed`
- `control_type=same_etno_catalog_without_p9`

Também há `dynamic_score_with_p9`, `dynamic_score_without_p9` e `delta_dynamic_score` em `ranking.csv` e `metrics_by_candidate.csv`.

Classificação: PARTIAL.

Motivo: o pareamento existe como contrato operacional, mas é calculado por fallback analítico, não por integração física real com REBOUND.

## 11. Blockers

Blockers ativos na run `screen_20260602T023149Z`:

- `no_observational_bias_model`
  - Severidade: `science_limit`
  - Mensagem: “Não há modelo completo de viés observacional nesta versão; portanto, o resultado é apenas screening exploratório.”

Impacto:

O blocker limita o `evidence_level` máximo observado a `weak` e impede claim forte.

## 12. Riscos para IC

- Risco de banca rejeitar o V1 como “simulador físico” porque REBOUND real não está instalado nem usado.
- Risco de reprodutibilidade científica incompleta por falta de catálogo canônico com `epoch`, `frame`, `source` e `validation_status`.
- Risco de falsa confiança porque os comandos passam, mas os testes são poucos e superficiais.
- Risco de auditoria incompleta porque `audit-run` não exige os artefatos estritos solicitados.
- Risco de interpretação indevida do ranking porque métricas são heurísticas analíticas, embora o relatório seja conservador.
- Risco de impossibilidade de resume real, pois não há `candidates_status.csv` nem `events.log`.
- Risco documental: faltam documentos de modelo físico, métricas, limitações e protocolo experimental.
- Risco de claims: baixo no estado atual; a política é conservadora e o blocker de viés está ativo.

## 13. Próximo prompt recomendado

Próximo passo recomendado: A) corrigir V1.

Prioridade imediata:

1. C) instalar/validar REBOUND real e substituir o fallback no caminho de screening.
2. B) aumentar testes para pelo menos 20 testes reais, incluindo erros e invariantes científicos.
3. A) corrigir estrutura, CSVs canônicos, schemas e artefatos estritos de run.
4. D) implementar robustez somente depois que integração física, catálogo e auditoria estiverem sólidos.

Resumo final:

Este V1 não deve ser aceito como screening físico validado. Pode ser usado como protótipo conservador de pipeline headless e auditável, desde que explicitamente rotulado como não científico/analítico até REBOUND real e dados canônicos entrarem no fluxo.
