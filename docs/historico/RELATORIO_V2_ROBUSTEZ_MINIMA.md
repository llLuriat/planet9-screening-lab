# Relatório V2 — Robustez Científica Mínima

## Veredito honesto

ACCEPTED_WITH_WARNINGS

O V2 implementa os testes mínimos de robustez solicitados e mantém o projeto headless, auditável e conservador. A run final usou REBOUND real e passou `audit-run`. Cientificamente, porém, os modelos nulos simples não foram superados pelos top candidatos; portanto o resultado permanece fraco/exploratório e não permite claim forte.

## O que foi implementado

- `python main.py leave-one-out --from-run runs/<run_id> --top 5`
- `python main.py convergence --from-run runs/<run_id> --top 5`
- `python main.py validate-top --from-run runs/<run_id> --top 5 --integrator ias15`
- `python main.py null-models --from-run runs/<run_id> --top 5 --n-shuffles 20`
- `python main.py report --from-run runs/<run_id>`
- Integração dos artefatos V2 ao `audit-run`.
- Atualização do report com seções V2 e frase obrigatória.
- Atualização conservadora de `evidence_level`, sem permitir `strong`.

## Comandos executados

| Comando | Resultado |
| --- | --- |
| `python -m pytest` | PASS — 51 passed, 0 failed |
| `python main.py physics-check` | PASS — REBOUND 5.0.0 disponível |
| `python main.py screen --budget configs/budgets/low.yaml --seed 12345` | PASS — `runs/screen_20260604T021031Z` |
| `python main.py audit-run runs\screen_20260604T021031Z` | PASS antes do V2 |
| `python main.py leave-one-out --from-run runs\screen_20260604T021031Z --top 5` | PASS |
| `python main.py convergence --from-run runs\screen_20260604T021031Z --top 5` | PASS |
| `python main.py validate-top --from-run runs\screen_20260604T021031Z --top 5 --integrator ias15` | PASS |
| `python main.py null-models --from-run runs\screen_20260604T021031Z --top 5 --n-shuffles 20` | PASS |
| `python main.py report --from-run runs\screen_20260604T021031Z` | PASS |
| `python main.py audit-run runs\screen_20260604T021031Z` | PASS final |

## Número de testes

51 testes passando.

Novos testes V2 cobrem:

- geração de rodadas leave-one-out;
- `robustness_score` entre 0 e 1;
- convergência e status permitido;
- validação IAS15 sem claim forte;
- distribuição de modelos nulos;
- ausência de `strong`;
- frase obrigatória no report;
- `audit-run` detectando ausência de artefatos V2.

## Última run usada

`runs/screen_20260604T021031Z`

## Top candidatos antes/depois da robustez

Ranking base antes dos testes V2:

1. `p9_inner_unstable` — delta `0.210542`
2. `p9_mid_mass_aligned` — delta `0.210520`
3. `p9_high_mass_family` — delta `0.210513`
4. `p9_low_mass_weak` — delta `0.206840`
5. `p9_bad_geometry` — delta `0.039476`

Após robustez:

- Leave-one-out: todos os top 5 tiveram `robustness_score=1.0`.
- Convergência WHFast: todos os top 5 tiveram status `passed`.
- IAS15: todos os top 5 tiveram status `validated_preliminarily`.
- Modelos nulos simples: todos os top 5 tiveram status `failed`.

Consequência: o ranking operacional permanece, mas a interpretação científica é limitada. O blocker `null_model_not_exceeded` impede elevação de evidência.

## Blockers ativos

- `no_observational_bias_model`
- `null_model_not_exceeded`

## Limitações restantes

- Não há modelo completo de viés observacional.
- O catálogo ETNO ainda é parcial e de exemplo.
- Não há validação longa.
- Não há propagação de incerteza.
- Não há modelos nulos avançados.
- Não há detectabilidade.
- Não há MCMC ou otimização bayesiana.

## Claim máximo permitido no V2

Permitido apenas em termos condicionais:

> Este candidato ou família de candidatos apresentou robustez preliminar dentro do protocolo V2.

Na run final, como os modelos nulos simples não foram superados, a leitura correta é mais fraca:

> Os candidatos passaram testes numéricos preliminares, mas não se destacaram do modelo nulo simples; portanto, o resultado continua exploratório.

## Conclusão

O V2 transforma o projeto em um screening preliminar com robustez básica, mas ainda não sustenta evidência moderada nesta run específica. O projeto continua não confirmando a existência do Planeta 9 e não determina sua órbita real.
