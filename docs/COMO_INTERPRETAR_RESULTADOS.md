# Como Interpretar Resultados

Este projeto é uma ferramenta de screening dinâmico.

Interpretação correta:

- `delta_dynamic_score > 0` indica que o candidato melhorou o score dinâmico em relação ao controle.
- `delta_dynamic_score <= 0` indica que o candidato não melhorou o controle.
- `evidence_level` é limitado por blockers científicos.
- `robustness_score=not_computed` significa que robustez ainda não foi executada.
- `no_candidate_found` é resultado válido quando nenhum candidato supera o controle de forma relevante.

Interpretação proibida:

- Não dizer que o Planeta 9 foi confirmado.
- Não dizer que o Planeta 9 foi descoberto.
- Não dizer que a órbita real foi determinada.

Sem modelo completo de viés observacional, os resultados continuam exploratórios.

