from __future__ import annotations

BIAS_NOTICE = (
    "Não há modelo completo de viés observacional nesta versão; portanto, "
    "o resultado é apenas screening exploratório."
)


def build_report(
    manifest: dict,
    ranking_rows: list[dict],
    summary: dict,
    blockers: list[dict],
    v2: dict | None = None,
) -> str:
    top = ranking_rows[:10]
    rejected = [row for row in ranking_rows if row.get("scientific_status") == "rejected"]
    numerical = [
        row
        for row in ranking_rows
        if row.get("operational_status") == "failed" or "numerical" in row.get("classification_reason", "")
    ]
    lines: list[str] = []
    lines.extend(
        [
            "# Planet9 Screening Lab V1 — Report",
            "",
            "## 1. Resumo executivo",
            "",
            f"Run `{manifest['run_id']}` finalizada com status global `{manifest['global_result_status']}`.",
            "Este projeto é uma ferramenta de screening dinâmico.",
            "Este projeto não confirma a existência do Planeta 9.",
            "Este projeto não determina a órbita real do Planeta 9.",
            "",
            "## 2. Objetivo científico",
            "",
            "Avaliar se o modelo com P9 melhora métricas dinâmicas dos ETNOs em relação ao controle sem P9.",
            "",
            "## 3. Hipótese H0/H1",
            "",
            "H0: A distribuição orbital observada dos ETNOs pode ser explicada sem Planeta 9, considerando instabilidade natural, viés observacional e tamanho pequeno da amostra.",
            "",
            "H1: Existe uma faixa de candidatos P9 que melhora a coerência dinâmica dos ETNOs em relação ao controle sem P9.",
            "",
            "## 4. Dados utilizados",
            "",
            f"ETNOs incluídos: {manifest['included_etno_count']}. Catálogo: `data/etnos/catalog.csv`.",
            "Gigantes usados: Júpiter, Saturno, Urano e Netuno em `data/solar_system/giants_epoch.csv`.",
            "",
            "## 5. Critério de seleção dos ETNOs",
            "",
            "Cada linha do catálogo possui `selection_included`, `selection_reason` e `selection_notes` para reduzir risco de cherry-picking.",
            "",
            "## 6. Região de parâmetros",
            "",
            "Região definida em `configs/grids/p9_target_region.yaml`; candidatos de exemplo vêm de `data/candidates_example.csv`.",
            "",
            "## 7. Configuração computacional",
            "",
            f"Python: {manifest['python_version']}",
            f"Plataforma: {manifest['platform']}",
            f"NumPy: {manifest['numpy_version']}; pandas: {manifest['pandas_version']}; REBOUND: {manifest['rebound_version']}",
            f"Seed: {manifest['seed']}",
            "",
            "## 8. Integrador",
            "",
            f"Integrador configurado: `{manifest['budget']['integrator']}` em unidades yr/AU/Msun com `G = 4*pi^2`.",
        ]
    )
    if not manifest.get("rebound_used"):
        lines.append("")
        lines.append("REBOUND real não foi usado nesta execução; portanto, esta run não é screening físico validado.")
    lines.extend(
        [
            "",
            "## 9. Controle com/sem P9",
            "",
            "Cada candidato deve ter uma integração com P9 e uma integração sem P9. Sem controle completo, o candidato é inválido.",
            "",
            "## 10. Métricas",
            "",
            "O score usa clustering apsidal, anti-alinhamento, sobrevivência, estabilidade e saúde numérica. Evidência científica é separada do score dinâmico.",
            "",
            "## 11. Ranking",
            "",
            "| rank | candidate_id | delta_dynamic_score | evidence_level | scientific_status |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in top:
        lines.append(
            f"| {row['rank']} | {row['candidate_id']} | {row['delta_dynamic_score']} | "
            f"{row['evidence_level']} | {row['scientific_status']} |"
        )
    lines.extend(["", "## 12. Candidatos rejeitados", ""])
    if rejected:
        for row in rejected:
            lines.append(f"- `{row['candidate_id']}`: {row['classification_reason']} (delta={row['delta_dynamic_score']})")
    else:
        lines.append("Nenhum candidato classificado como rejeitado nesta run.")
    lines.extend(["", "## 13. Falhas numéricas", ""])
    if numerical:
        for row in numerical:
            lines.append(f"- `{row['candidate_id']}`: {row['classification_reason']}")
    else:
        lines.append("Nenhuma falha numérica registrada nos candidatos classificados como completed.")
    lines.extend(
        [
            "",
            "## 14. Ranking summary / top 10 enganoso",
            "",
            f"- delta_score_min: {summary['delta_score_min']}",
            f"- delta_score_max: {summary['delta_score_max']}",
            f"- delta_score_mean: {summary['delta_score_mean']}",
            f"- delta_score_median: {summary['delta_score_median']}",
            f"- delta_score_std: {summary['delta_score_std']}",
            f"- top1_delta_score: {summary['top1_delta_score']}",
            f"- top1_minus_median: {summary['top1_minus_median']}",
            f"- top1_minus_top10: {summary['top1_minus_top10']}",
            f"- top1_percentile: {summary['top1_percentile']}",
            f"- top1_distinctness: {summary['top1_distinctness']}",
            "",
        ]
    )
    if summary["top1_distinctness"] == "least_bad_only":
        lines.append("O top 1 é apenas o menos ruim, não um candidato robusto.")
    elif summary["top1_distinctness"] == "top1_distinct":
        lines.append("O top 1 está separado da mediana por pelo menos um desvio padrão do delta_score.")
    else:
        lines.append("O top 1 não está fortemente separado do restante do ranking no V1.")
    lines.extend(["", "## 15. Blockers", ""])
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker['blocker_id']}`: {blocker['message']}")
    else:
        lines.append("Nenhum blocker ativo.")
    lines.extend(
        [
            "",
            "## 16. O que pode ser afirmado",
            "",
            f"Claim permitido nesta run: `{manifest['claim_allowed']}`.",
            "Pode-se afirmar apenas o resultado dentro do protocolo V1 e dos blockers ativos.",
            "",
            "## 17. O que não pode ser afirmado",
            "",
            "Não se pode afirmar confirmação, descoberta, validação ou órbita real do Planeta 9.",
            "",
            "## 18. Comando de reprodução",
            "",
            "Ver `replay_command.txt` nesta pasta de run.",
            "",
            "## 19. Próximos passos",
            "",
            "- Implementar propagação de incerteza em versão futura.",
            "- Implementar detectabilidade (limites IR/óptico) em versão futura.",
            "- Substituir fixtures parciais por catálogo científico validado.",
            "",
            "## Limites de robustez V1",
            "",
            f"- leave_one_out_status: {'run' if v2 and v2.get('leave_one_out') != 'Não executado.' else 'not_run'}",
            "- uncertainty_propagation_status: not_run",
            f"- null_models_status: {'run' if v2 and v2.get('null_models') != 'Não executado.' else 'not_run'}",
            f"- convergence_status: {'run' if v2 and v2.get('convergence') != 'Não executado.' else 'not_run'}",
            "- detectability_status: not_run",
        ]
    )
    if v2 is not None:
        lines.extend(
            [
                "",
                "## Robustez V2",
                "",
                "Mesmo após os testes de robustez V2, este projeto não confirma a existência do Planeta 9.",
                "Mesmo que algum candidato supere testes internos, este projeto não confirma a existência do Planeta 9.",
                "",
                "### Leave-one-out",
                "",
                v2.get("leave_one_out", "Não executado."),
                "",
                "### Convergência numérica",
                "",
                v2.get("convergence", "Não executado."),
                "",
                "### Validação IAS15",
                "",
                v2.get("ias15", "Não executado."),
                "",
                "### Modelos nulos",
                "",
                v2.get("null_models", "Não executado."),
                "",
                "### Diagnósticos adicionais",
                "",
                "#### Diagnóstico do score",
                "",
                v2.get("scoring_diagnosis", "Não executado."),
                "",
                "#### Diagnóstico dos modelos nulos",
                "",
                v2.get("null_model_diagnosis", "Não executado."),
                "",
                "#### Estabilidade por seed",
                "",
                v2.get("seed_stability", "Não executado."),
                "",
                "#### Famílias de candidatos",
                "",
                v2.get("candidate_families", "Não executado."),
                "",
                "## Limitações restantes (V2)",
                "",
                v2.get("catalog_status", "Catálogo V2 parcial; validação externa ainda necessária."),
                "",
                "- Resultados continuam exploratórios até validação observacional completa.",
                "- Modelos nulos e testes de robustez reduzem risco, mas não estabelecem descoberta.",
                "- Detectabilidade e viés observacional completo ainda limitam qualquer claim forte.",
            ]
        )
    return "\n".join(lines) + "\n"


def build_summary_for_presentation(manifest: dict, ranking_rows: list[dict], summary: dict) -> str:
    top = ranking_rows[0] if ranking_rows else None
    lines = [
        "# Summary for Presentation",
        "",
        f"Run: {manifest['run_id']}",
        f"Global status: {manifest['global_result_status']}",
        f"Allowed claim: {manifest['claim_allowed']}",
        f"REBOUND used: {manifest['rebound_used']}",
        "",
        "Este projeto não confirma a existência do Planeta 9.",
        "Este projeto não determina a órbita real do Planeta 9.",
        "",
    ]
    if top:
        lines.extend(
            [
                f"Top candidate: {top['candidate_id']}",
                f"Delta dynamic score: {top['delta_dynamic_score']}",
                f"Evidence level: {top['evidence_level']}",
                f"Top1 distinctness: {summary['top1_distinctness']}",
                "",
            ]
        )
    lines.append("Não apresentar como prova, descoberta ou confirmação do Planeta 9.")
    return "\n".join(lines) + "\n"

