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
- `anti_alignment_score_with_p9`
- `anti_alignment_score_without_p9`
- `stability_score_with_p9`
- `stability_score_without_p9`
- `numerical_health_score_with_p9`
- `numerical_health_score_without_p9`
- `evidence_level`
- `robustness_score`

`delta_dynamic_score = dynamic_score_with_p9 - dynamic_score_without_p9`.

Um ranking alto não é prova. O ranking apenas ordena candidatos para inspeção dentro do protocolo V1.

