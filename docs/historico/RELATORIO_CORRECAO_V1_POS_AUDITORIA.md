# Relatório de Correção V1 Pós-Auditoria

## Veredito honesto

ACCEPTED_WITH_WARNINGS

O V1 agora deixou de ser apenas uma casca analítica: REBOUND real está instalado, `physics-check` executa integração curta real, e `screen`, `smoke` e `compare` usam REBOUND no caminho principal. Ainda não é `ACCEPTED` absoluto porque o V1 mantém blocker de viés observacional, catálogo de exemplo com validação parcial, e não executa leave-one-out, incerteza, modelos nulos ou detectabilidade.

## Problemas da auditoria corrigidos

- REBOUND real instalado e usado no screen.
- Fallback analítico limitado a `--allow-analytical-fallback`, com run inválida e blocker `rebound_not_available`.
- Suíte ampliada de 5 para 37 testes reais.
- CSV canônico criado em `data/etnos/catalog.csv`.
- CSV de gigantes criado em `data/solar_system/giants_epoch.csv`.
- Schemas completos criados para candidatos, ETNOs, gigantes, budget, run e resultados.
- Configs faltantes criadas: `configs/budgets/medium.yaml` e `configs/grids/p9_target_region.yaml`.
- Estrutura base completada com `pyproject.toml`, `.gitignore` e `runs/.gitkeep`.
- Run artifacts estritos implementados.
- `audit-run` endurecido para falhar quando artefato obrigatório falta.
- `resume` lê `candidates_status.csv`, identifica completed/pending, registra evento e não recalcula completed.
- `rescore` preserva ranking original e cria pasta própria.
- `explain-candidate` e `why-rejected` foram aprofundados.
- `reports/report.md` contém as seções e frases obrigatórias.
- Documentos científicos faltantes foram criados.

## Problemas ainda pendentes

- `no_observational_bias_model` continua ativo: não há modelo completo de viés observacional.
- Catálogo canônico V1 ainda usa fixtures parciais, não catálogo científico final validado.
- Robustez completa ainda não existe: leave-one-out, incerteza, modelos nulos e detectabilidade permanecem `not_run`.
- `resume` funciona para identificar pending e preservar completed; a continuação de pending existe como contrato operacional inicial, mas ainda deve ser exercitada em uma run interrompida real.
- Não há PDF, dashboard, UI ou visual, por desenho do V1.

## Comandos executados

| Comando | Resultado | Observação |
| --- | --- | --- |
| `python -m pytest` | PASS | 37 passed, 0 failed |
| `python main.py plan --budget configs/budgets/low.yaml` | PASS | Lista CSVs canônicos, REBOUND/WHFast e artefatos estritos |
| `python main.py init-data` | PASS | Recria dados canônicos |
| `python main.py physics-check` | PASS | `rebound_available=true`, `rebound_version=5.0.0`, integração curta real |
| `python main.py smoke` | PASS | Criou `runs/smoke_20260602T025541Z` |
| `python main.py compare --candidate configs/candidates/mid_mass.yaml --budget configs/budgets/low.yaml` | PASS | Criou `runs/compare_20260602T025550Z` |
| `python main.py screen --budget configs/budgets/low.yaml --seed 12345` | PASS | Criou `runs/screen_20260602T025558Z` |
| `python main.py audit-run runs\screen_20260602T025558Z` | PASS | `AUDIT OK` |
| `python main.py explain-candidate p9_inner_unstable --from-run runs\screen_20260602T025558Z` | PASS | Mostra delta, métricas, controle, blockers, evidence e REBOUND |
| `python main.py why-rejected p9_bad_geometry --from-run runs\screen_20260602T025558Z` | PASS | Mostra motivo, delta, survival, drift, ETNOs perdidos e blockers |
| `python main.py rescore --from-run runs\screen_20260602T025558Z --weights configs/scoring/default_weights.yaml` | PASS | Criou `rescore_20260602T025638Z` sem sobrescrever ranking original |
| `python main.py resume runs\screen_20260602T025558Z` | PASS | Sem pending; registrou evento no `events.log` |

## Resultado dos testes

Total: 37 testes.

Cobertura adicionada:

- Units: massa terrestre para solar, graus/radianos, wrap angular, distância angular.
- Schemas: candidato, ETNO canônico, gigantes, campos obrigatórios e ranges.
- Métricas: clustering, anti-alinhamento, score, delta e ranking summary.
- Policy: NaN, sem controle, delta baixo, delta bom e claims proibidos.
- Control pair: with/without P9 obrigatório, REBOUND ausente sem fallback e fallback explícito inválido.
- Run artifacts: `status.json`, `reports/report.md`, hashes e auditoria falhando se artefato sumir.
- Rescore: não sobrescreve ranking original.

## REBOUND

Instalado: sim.

Versão: 5.0.0.

Usado no screen: sim.

Evidência:

- `physics-check` retornou `rebound_available: true`.
- `audit/run_manifest.json` da última run contém `rebound_used: true`.
- `results/ranking.csv` contém `rebound_used=True` para os candidatos.

## Última run gerada

`runs/screen_20260602T025558Z`

Arquivos principais:

- `status.json`
- `heartbeat.json`
- `events.log`
- `config.resolved.yaml`
- `environment.json`
- `data_manifest.json`
- `candidates_input.csv`
- `candidates_status.csv`
- `results/ranking.csv`
- `results/metrics_by_candidate.csv`
- `results/control_pairs.csv`
- `results/ranking_summary.json`
- `audit/run_manifest.json`
- `audit/blockers.json`
- `audit/hashes.json`
- `reports/report.md`
- `presentation/summary_for_presentation.md`
- `presentation/top10_table.csv`

## Blockers ativos

- `no_observational_bias_model`

Impacto: evidence_level permanece limitado; a run é screening dinâmico conservador, não confirmação.

## Conclusão

O projeto agora atende ao objetivo de V1 físico mínimo real, headless e auditável com REBOUND. O veredito correto é `ACCEPTED_WITH_WARNINGS`: o V1 pode ser usado como screening dinâmico mínimo dentro do protocolo, mas não como prova, confirmação ou determinação orbital do Planeta 9.
