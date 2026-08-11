# Relatório de Evolução Pós-V2 — Planet9 Screening Lab

## Veredito

ACCEPTED_WITH_WARNINGS

O pipeline pós-V2 foi implementado e auditou corretamente, mas o resultado científico continua fraco. Nenhum candidato deve ser apresentado como evidência forte: os modelos nulos ampliados ainda bloqueiam a elevação de `evidence_level`.

## O que foi corrigido

- `run_id` agora usa microssegundos, evitando colisão silenciosa de pastas de run em execuções rápidas.
- `audit-run` passou a verificar artefatos novos: seed stability, diagnósticos, famílias e percentis de modelos nulos.
- Modelos nulos foram otimizados sem remover REBOUND real: o ramo sem P9, que é independente do candidato, não é reintegrado inutilmente para cada candidato.
- O custo dos modelos nulos serious ficou explícito em `configs/budgets/serious.yaml` via `null_model_t_myr: 0.002`.
- O relatório final inclui diagnóstico de score, diagnóstico de nulos, estabilidade por seed, famílias de candidatos e status do catálogo.

## O que foi implementado

- `python main.py diagnose-null-models --from-run runs/<run_id>`
- `python main.py diagnose-scoring --from-run runs/<run_id>`
- `python main.py candidate-families --from-run runs/<run_id> --top 20`
- `configs/science/etno_selection.yaml`
- `configs/scoring/v2_weights.yaml`
- `configs/budgets/serious.yaml`
- `data/etnos/catalog_v2.csv`
- `data/etnos/catalog_sources.md`
- `data/etnos/catalog_validation_report.md`
- Modelos nulos múltiplos: `shuffle_varpi`, `randomize_angles`, `no_p9_catalog_baseline`
- Artefatos:
  - `results/seed_stability.csv`
  - `results/seed_stability_summary.json`
  - `robustness/null_model_percentiles.csv`
  - `diagnostics/scoring_diagnosis.md`
  - `diagnostics/scoring_components.csv`
  - `diagnostics/null_model_diagnosis.md`
  - `analysis/candidate_families.csv`
  - `analysis/candidate_families_summary.md`

## Comandos executados

- `python -m pytest` -> `68 passed, 0 failed`
- `python main.py physics-check` -> PASS, REBOUND 5.0.0 disponível
- `python main.py screen --budget configs/budgets/low.yaml --seed 12345` -> `runs/screen_20260604T023542Z`
- `python main.py leave-one-out --from-run runs/screen_20260604T023542Z --top 5` -> PASS
- `python main.py convergence --from-run runs/screen_20260604T023542Z --top 5` -> PASS
- `python main.py validate-top --from-run runs/screen_20260604T023542Z --top 5 --integrator ias15` -> PASS
- `python main.py null-models --from-run runs/screen_20260604T023542Z --top 5 --n-shuffles 20 --models shuffle_varpi,randomize_angles,no_p9_catalog_baseline` -> PASS
- `python main.py audit-run runs/screen_20260604T023542Z` -> `AUDIT OK`
- `python main.py screen --budget configs/budgets/serious.yaml --seed 12345` -> `runs/screen_20260604T031622764645Z`
- `python main.py audit-run runs/screen_20260604T031622764645Z` -> `AUDIT OK`
- `python main.py diagnose-scoring --from-run runs/screen_20260604T031622764645Z` -> PASS
- `python main.py diagnose-null-models --from-run runs/screen_20260604T031622764645Z` -> PASS
- `python main.py leave-one-out --from-run runs/screen_20260604T031622764645Z --top 10` -> PASS
- `python main.py convergence --from-run runs/screen_20260604T031622764645Z --top 10` -> PASS
- `python main.py validate-top --from-run runs/screen_20260604T031622764645Z --top 10 --integrator ias15` -> PASS
- `python main.py null-models --from-run runs/screen_20260604T031622764645Z --top 10 --n-shuffles 100 --models shuffle_varpi,randomize_angles,no_p9_catalog_baseline` -> PASS após sub-orçamento configurado
- `python main.py candidate-families --from-run runs/screen_20260604T031622764645Z --top 20` -> PASS
- `python main.py report --from-run runs/screen_20260604T031622764645Z` -> PASS
- `python main.py audit-run runs/screen_20260604T031622764645Z` -> `AUDIT OK`

Observação: uma primeira tentativa de `null-models` serious com 50.000 anos por shuffle excedeu 20 minutos. A correção foi tornar o sub-orçamento nulo explícito e auditável, não reduzir silenciosamente a física.

## Testes

Total final: 68 testes passando.

Cobertura nova adicionada:

- seleção ETNO por `a_au` e periélio `q`
- budget serious e aliases
- diagnóstico de scoring
- modelos nulos múltiplos
- `p_like` e `null_percentile`
- estabilidade por seed
- famílias de candidatos
- claim cap com catálogo parcial
- report pós-V2
- audit-run detectando ausência de artefatos novos

## Última run serious

Run: `runs/screen_20260604T031622764645Z`

Status: auditada com sucesso.

REBOUND: instalado e usado (`5.0.0`).

Screen principal: 50.000 anos.

Modelos nulos: REBOUND real com sub-orçamento configurado de 2.000 anos por shuffle.

## Resultado dos modelos nulos

Os modelos nulos não foram superados de forma robusta.

Resumo:

- `p9_high_mass_family`: falhou em `shuffle_varpi` e `no_p9_catalog_baseline`; passou em `randomize_angles`.
- `p9_mid_mass_aligned`: falhou em `shuffle_varpi` e `no_p9_catalog_baseline`; passou em `randomize_angles`.
- `p9_inner_unstable`: falhou em `shuffle_varpi` e `no_p9_catalog_baseline`; passou em `randomize_angles`.
- `p9_low_mass_weak`: passou em `shuffle_varpi` e `randomize_angles`; falhou em `no_p9_catalog_baseline`.
- `p9_bad_geometry`: falhou nos três modelos.

Conclusão honesta: nenhum candidato passou os três modelos nulos. O blocker `null_model_not_exceeded` permanece ativo.

## Estabilidade por seed

Todos os cinco candidatos apareceram no top 10 nas três seeds (`12345`, `22345`, `32345`), com `seed_stability_score = 1.0`.

Isso mostra estabilidade operacional do ranking para este catálogo pequeno, mas não resolve o problema científico dos modelos nulos.

## Famílias de candidatos

O agrupamento simples encontrou uma única família contendo os cinco candidatos disponíveis.

Interpretação: há um padrão amplo demais para sustentar candidato isolado forte. O agrupamento é diagnóstico, não evidência orbital independente.

## Diagnóstico do score

O score não parece totalmente colapsado, pois `delta_spread = 0.169962` e `candidates_receive_similar_score = false`.

Mas há saturação clara:

- `survival_rate = 1.0` para todos.
- `stability` saturada.
- `numerical_health` saturada.

Isso reduz o poder discriminativo de parte do score. O ranking é carregado principalmente por componentes dinâmicos restantes, especialmente anti-alinhamento e clustering.

## Gargalos científicos

- Catálogo ETNO efetivo ainda pequeno: 4 objetos incluídos.
- Catálogo V2 está marcado como `partial`, sem validação externa MPC/JPL/Horizons.
- Não há modelo observacional real.
- O baseline `no_p9_catalog_baseline` domina negativamente a interpretação dos nulos.
- A métrica ainda não mostra separação suficiente contra `shuffle_varpi` para os três candidatos de topo.
- Os nulos usam sub-orçamento de 2.000 anos por shuffle; isso é honesto e auditável, mas limita a equivalência com o screen principal de 50.000 anos.

## Blockers ativos

- `no_observational_bias_model`
- `etno_catalog_not_fully_validated`
- `null_model_not_exceeded`

## Claim máximo permitido

Pode-se dizer apenas que a run encontrou candidatos/família de interesse dentro do protocolo, com estabilidade interna, mas sem superar modelos nulos de forma suficiente.

Não se pode afirmar confirmação, descoberta, validação ou órbita real do Planeta 9.

Mesmo que algum candidato supere testes internos, este projeto não confirma a existência do Planeta 9.

## Próximo passo recomendado

A próxima etapa não deve ajustar pesos para forçar aprovação. O gargalo real é científico:

1. Validar manualmente o catálogo ETNO contra MPC/JPL/NASA Horizons.
2. Rever o modelo nulo `no_p9_catalog_baseline`, porque ele está operando como baseline muito forte e precisa de justificativa física clara.
3. Melhorar métricas que hoje saturam (`survival_rate`, `stability`, `numerical_health`).
4. Aumentar catálogo e validar seleção antes de buscar claims mais fortes.

