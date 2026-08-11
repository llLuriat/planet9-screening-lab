# Planet9 Screening Lab

Pipeline headless de screening dinâmico para perguntar:

> O modelo com P9 melhora as métricas dinâmicas dos ETNOs em relação ao modelo sem P9?

Este projeto **não confirma a existência do Planeta 9** e **não determina a órbita real do
Planeta 9**. Gera ranking apenas como screening dinâmico conservador, com controle
sem P9, hashes, blockers e auditoria. Veja `docs/LIMITACOES.md` para o que está e o
que não está implementado agora.

## 0. Primeira coisa a rodar, sempre

```bash
python main.py doctor
```

Verifica se `pydantic`, `rebound`, `pytest` etc. estão instalados e funcionando -
e, importante, funciona mesmo se algo estiver faltando (é o único comando que não
depende de nada além da biblioteca padrão do Python). Se `doctor` reclamar de algo,
resolva antes de tentar qualquer outro comando; o resto do pipeline vai falhar com
mensagens menos claras se as dependências não estiverem certas.

```bash
pip install -e .
python main.py doctor   # deve mostrar tudo OK
python -m pytest        # suíte de testes completa
```

## 1. Fluxo do dia a dia

| Quero...                                          | Comando |
|-----------------------------------------------------|---------|
| Ver se o ambiente está OK                            | `python main.py doctor` |
| Testar o pipeline rápido (sem física real, segundos)  | `python main.py smoke` |
| Ver o que uma run *faria*, sem rodar de verdade       | `python main.py plan --budget configs/budgets/low.yaml` |
| Rodar screening curto (50 anos, minutos)              | `python main.py screen --budget configs/budgets/low.yaml --seed 12345` |
| Rodar screening real, escala secular (**horas/dias**) | `python main.py screen --budget configs/budgets/secular.yaml --seed 12345` |
| Ver quanto tempo isso vai levar no seu hardware       | `python scripts/benchmark_integration_cost.py` |
| Ver status da run mais recente (foto única)           | `python main.py status` |
| Acompanhar progresso ao vivo (atualiza sozinho)       | `python main.py watch` |
| Continuar uma run interrompida (crash, PC desligou)   | `python main.py resume runs/<run_id>` |
| Rodar a varredura Monte Carlo do espaço de parâmetros | `python main.py montecarlo-scan` |
| Comparar um candidato específico                      | `python main.py compare --candidate configs/candidates/mid_mass.yaml --budget configs/budgets/low.yaml` |
| Entender por que um candidato foi rejeitado           | `python main.py why-rejected <candidate_id> --from-run runs/<run_id>` |
| Ver a explicação completa de um candidato             | `python main.py explain-candidate <candidate_id> --from-run runs/<run_id>` |
| Auditar uma run já feita                              | `python main.py audit-run runs/<run_id>` |

### Robustez científica (item 5 do plano V1->V2)

| Quero...                                          | Comando |
|-----------------------------------------------------|---------|
| Testar sensibilidade a cada ETNO (leave-one-out)      | `python main.py leave-one-out --from-run runs/<run_id> --top 5` |
| Testar convergência numérica (refinar timestep)       | `python main.py convergence --from-run runs/<run_id> --top 5` |
| Validar com outro integrador (IAS15)                  | `python main.py validate-top --from-run runs/<run_id> --top 5 --integrator ias15` |
| Comparar contra modelos nulos reais (REBOUND)         | `python main.py null-models --from-run runs/<run_id> --top 5 --n-shuffles 20 --models shuffle_varpi,randomize_angles,no_p9_catalog_baseline` |
| Diagnosticar saturação/contribuição do score          | `python main.py diagnose-scoring --from-run runs/<run_id>` |
| Diagnosticar por que os modelos nulos passaram/falharam | `python main.py diagnose-null-models --from-run runs/<run_id>` |
| Agrupar candidatos parecidos                          | `python main.py candidate-families --from-run runs/<run_id> --top 20` |
| Regerar o relatório com a seção de robustez V2        | `python main.py report --from-run runs/<run_id>` |

Os comandos de robustez sempre regeram `reports/report.md` automaticamente
(exceto `diagnose-*`/`candidate-families`, que só escrevem seus próprios
arquivos - rode `report` depois deles se quiser ver tudo junto no relatório).

`status` e `watch` usam `runs/latest_run.txt` por padrão; passe um caminho explícito
(`python main.py status runs/screen_2026...`) para olhar uma run específica que não
seja a mais recente.

**Regra prática:** `low.yaml` é para testar se o pipeline funciona (minutos).
`secular.yaml` é para gerar resultado que sustenta o artigo (horas a dias, dependendo
do hardware - meça com `benchmark_integration_cost.py` antes de rodar em escala).
Não confunda os dois; `config.resolved.yaml` dentro de cada run sempre mostra qual foi
usado, então se estiver em dúvida sobre uma run já feita, olhe lá.

## 2. Budgets disponíveis (`configs/budgets/`)

| Budget | integration_years | Uso |
|---|---|---|
| `low.yaml` | 50 | teste rápido de que o pipeline roda |
| `medium.yaml` | 200 | teste um pouco mais longo |
| `secular.yaml` | 1e8 (ponto de partida - ver `docs/LIMITACOES.md`) | o único com validade científica para o artigo; usa checkpointing |
| `serious.yaml` | 50.000 (via aliases legados `screen_t_myr` etc.) | budget usado pelos testes de robustez V2 (leave-one-out, modelos nulos); `null_model_integration_years` separado para o sub-orçamento dos nulos |
| `montecarlo_stage2.yaml` | 1e6 | usado internamente pelo `montecarlo-scan`, não rode direto |

`data/etnos/catalog_v2.csv` é uma versão com seleção explícita/auditável do
mesmo catálogo (`configs/science/etno_selection.yaml` define os critérios).
Os comandos de robustez usam `catalog_v2.csv` automaticamente se ele existir;
`screen`/`compare`/`smoke` continuam usando `catalog.csv`. Nenhum dos dois
catálogos está validado externamente (MPC/JPL/Horizons) ainda - ver
`data/etnos/catalog_validation_report.md`.

## 3. Artefatos de cada run

`SUCCESS.marker` ou `INVALID.marker`, `status.json`, `heartbeat.json`, `report.md`,
`ranking.csv`, `replay_command.txt`, `results/metrics_by_candidate.csv`,
`results/control_pairs.csv`, `results/ranking_summary.json`,
`audit/run_manifest.json`, `audit/blockers.json`, `audit/hashes.json`,
`presentation/summary_for_presentation.md`, `presentation/top10_table.csv`. Runs com
`checkpoint_interval_years` também geram `checkpoints/*.bin` (estado REBOUND) e
`checkpoints/*_drift_series.csv` / `*_delta_pomega_series.csv` (séries temporais).

O caminho principal usa REBOUND real. Se REBOUND não estiver disponível, `screen`,
`smoke` e `compare` recusam rodar como screening físico, exceto com
`--allow-analytical-fallback`, que gera run marcada `INVALID`.

## 4. Onde as coisas estão documentadas

- `docs/LIMITACOES.md` - o que está implementado de verdade vs. pendente, atualizado
  a cada bloco do plano V1->V2.
- `docs/historico/` - auditorias e relatórios de correção anteriores (histórico, não
  reflete o estado atual do código).
- `docs/COMO_INTERPRETAR_RESULTADOS.md`, `docs/CRITERIO_SELECAO_ETNOS.md` - guias de
  interpretação científica.
