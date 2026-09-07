# Métricas V1

O V1 separa score dinâmico de evidência científica.

Campos obrigatórios:

- `dynamic_score_with_p9`
- `dynamic_score_without_p9`
- `delta_dynamic_score`
- `survival_rate_with_p9`
- `survival_rate_without_p9`
- `energy_drift_rel_with_p9`
- `energy_drift_rel_without_p9`
- `angular_momentum_drift_rel_with_p9`
- `angular_momentum_drift_rel_without_p9`
- `apsidal_clustering_R_with_p9`
- `apsidal_clustering_R_without_p9`
- `mean_angular_alignment_score_with_p9`
- `mean_angular_alignment_score_without_p9`
- `stability_score_with_p9`
- `stability_score_without_p9`
- `numerical_health_score_with_p9`
- `numerical_health_score_without_p9`
- `evidence_level`
- `robustness_score`

`delta_dynamic_score = dynamic_score_with_p9 - dynamic_score_without_p9`.

Nota (auditoria V3, P1-3): `mean_angular_alignment_score` é a **distância
angular média normalizada** dos ETNOs à longitude anti-alinhada com P9
(ϖ_P9 + 180°), mapeada para [0, 1] via `1 - média/180°`. **Não** é uma
estatística circular (`resultant`); a concentração da distribuição de ϖ é
medida separadamente por `apsidal_clustering_R`. Runs persistidas antes da
auditoria V3 usam o nome legado `anti_alignment_score` nas colunas; os
leitores aceitam ambos os nomes.

Um ranking alto não é prova. O ranking apenas ordena candidatos para inspeção dentro do protocolo V1.

