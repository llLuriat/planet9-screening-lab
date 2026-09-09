"""Schema curado dos subcomandos de ``planet9lab.cli`` (Tarefa D).

O dashboard NUNCA altera ``cli.py`` nem nenhum módulo de ``planet9lab/`` —
apenas CHAMA os comandos existentes. Este módulo declara, para o
formulário de disparo, os subcomandos com os MESMOS flags e defaults
verificados linha a linha em ``planet9lab/cli.py`` (build_parser). Se um
comando do CLI mudar, atualizar aqui; a UI nunca inventa flags fora
deste schema.

O subcomando ``watch`` (visualização live em terminal) não está no
schema — a própria UI do dashboard o substitui; ele continua disponível
manualmente e segue bloqueado para disparo (BLOCKED_COMMANDS).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _a(
    flag: str | None,
    kind: str,
    *,
    default: Any = None,
    required: bool = False,
    help: str = "",
) -> dict[str, Any]:
    """Uma entrada de argumento. ``flag`` sem ``--`` é posicional."""
    return {"flag": flag, "kind": kind, "default": default, "required": required, "help": help}


# kinds: "path" (caminho livre) | "path_run" (diretório de run existente; a
# UI oferece as runs de runs/) | "str" | "int" | "float" | "flag"
# (store_true) | posicional (flag sem ":", ex.: "run_dir").
COMMANDS: tuple[dict[str, Any], ...] = (
    # __GROUP_RUNS__
    {
        "name": "screen",
        "group": "Runs",
        "long_running": True,
        "description": "Screening do catálogo de candidatos (pipeline completo por candidato).",
        "args": (
            _a("--budget", "path", required=True, help="YAML de orçamento (configs/budgets/*.yaml)"),
            _a("--seed", "int", default=12345, help="registrado no manifest; sem efeito físico em screen/compare (só vale para montecarlo-scan e modelos nulos)"),
            _a("--allow-analytical-fallback", "flag", help="permitir fallback analítico sem REBOUND"),
            _a("--candidates", "path", help="CSV de candidatos (ex.: data/candidates_quadro2.csv; default do CLI: data/candidates_example.csv)"),
            _a("--etnos", "path", help="CSV de ETNOs (ex.: data/etnos/catalog_validated.csv; default do CLI: data/etnos/catalog.csv)"),
            _a("--run-root", "path", help="diretório destino da run (default: ./runs)"),
            _a("--max-workers", "int", help="workers paralelos (default: CPU count; 1 = sequencial)"),
        ),
    },
    {
        "name": "compare",
        "group": "Runs",
        "long_running": True,
        "description": "Par de controle com/sem P9 para um candidato.",
        "args": (
            _a("--candidate", "str", required=True, help="candidate_id do CSV de candidatos"),
            _a("--budget", "path", required=True, help="YAML de orçamento"),
            _a("--seed", "int", default=12345, help="sem efeito físico em compare/screen (ver --seed do screen)"),
            _a("--allow-analytical-fallback", "flag", help="permitir fallback analítico sem REBOUND"),
            _a("--run-root", "path", help="diretório destino da run"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "smoke",
        "group": "Runs",
        "long_running": False,
        "description": "Screen de fumaça determinístico e minúsculo (sanidade do pipeline).",
        "args": (
            _a("--allow-analytical-fallback", "flag", help="permitir fallback analítico sem REBOUND"),
            _a("--run-root", "path", help="diretório destino da run"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "montecarlo-scan",
        "group": "Runs",
        "long_running": True,
        "description": "Varredura Monte Carlo/QMC do espaço de parâmetros (pode levar horas).",
        "args": (
            _a("--config", "path", default="configs/montecarlo/parameter_space.yaml", help="YAML do espaço de parâmetros"),
            _a("--seed", "int", help="semente"),
            _a("--run-root", "path", help="diretório destino da run"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "resume",
        "group": "Runs",
        "long_running": True,
        "description": "Retomar (ou inspecionar) candidatos pendentes de uma run.",
        "args": (
            _a("run_dir", "path_run", help="diretório da run (vazio = runs/latest_run.txt)"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "plan",
        "group": "Runs",
        "long_running": False,
        "description": "Dry-run de um screen, sem simulação.",
        "args": (
            _a("--budget", "path", required=True, help="YAML de orçamento"),
            _a("--allow-analytical-fallback", "flag", help="permitir fallback analítico sem REBOUND"),
        ),
    },
    {
        "name": "init-data",
        "group": "Runs",
        "long_running": False,
        "description": "Escreve os catálogos canônicos V1 e configs de candidatos.",
        "args": (),
    },
    {
        "name": "status",
        "group": "Infra",
        "long_running": False,
        "description": "Snapshot do status da última (ou dada) run (scripts/watch_progress.py --once).",
        "args": (_a("run_dir", "path_run", help="diretório da run (vazio = latest)"),),
    },
    {
        "name": "physics-check",
        "group": "Infra",
        "long_running": False,
        "description": "Checagens de sanidade REBOUND/numéricas.",
        "args": (),
    },
    {
        "name": "audit-run",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Audita a pasta de uma run (manifests, integridade).",
        "args": (_a("run_dir", "path_run", required=True, help="diretório da run"),),
    },
    {
        "name": "explain-candidate",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Explica o ranking de um candidato.",
        "args": (
            _a("candidate_id", "str", required=True, help="candidate_id"),
            _a("--from-run", "path_run", required=True, help="diretório da run"),
        ),
    },
    {
        "name": "why-rejected",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Explica a rejeição de um candidato.",
        "args": (
            _a("candidate_id", "str", required=True, help="candidate_id"),
            _a("--from-run", "path_run", required=True, help="diretório da run"),
        ),
    },
    {
        "name": "diagnose-scoring",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Contribuição por componente do score e saturação (V2).",
        "args": (_a("--from-run", "path_run", required=True, help="diretório da run"),),
    },
    {
        "name": "diagnose-null-models",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Resume resultados de modelos nulos já calculados (V2).",
        "args": (_a("--from-run", "path_run", required=True, help="diretório da run"),),
    },
    {
        "name": "selection-bias-check",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Testa se o clustering angular real pode ser artefato de seleção (V2).",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--config", "path", default="configs/science/observational_bias.yaml", help="YAML do modelo de viés"),
        ),
    },
    {
        "name": "candidate-families",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Agrupa candidatos parecidos por distância de parâmetros (V2).",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--top", "int", default=20, help="quantos candidatos agrupar"),
        ),
    },
    {
        "name": "circular-stats",
        "group": "Diagnósticos",
        "long_running": False,
        "description": "Estatísticas circulares Rayleigh/Kuiper lado a lado (read-only; nunca reclassifica).",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--alpha", "float", default=0.05, help="nível de significância dos flags (default: 0.05)"),
        ),
    },
    {
        "name": "megno",
        "group": "Diagnósticos",
        "long_running": True,
        "description": "EXPERIMENTAL: indicador de caos MEGNO por candidato (auxiliar, não calibrado; não é afirmação de estabilidade).",
        "args": (
            _a("--candidate", "str", required=True, help="candidate_id"),
            _a("--budget", "path", required=True, help="YAML de orçamento"),
            _a("--years", "float", help="tempo de integração em yr (default: budget.integration_years)"),
            _a("--seed", "int", default=42, help="semente fixa do MEGNO"),
            _a("--allow-analytical-fallback", "flag", help="permitir fallback analítico sem REBOUND"),
        ),
    },
    {
        "name": "leave-one-out",
        "group": "Robustez V2",
        "long_running": True,
        "description": "Re-executa os top candidatos com cada ETNO retirado, um por vez.",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--top", "int", default=5, help="quantos top candidatos"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "convergence",
        "group": "Robustez V2",
        "long_running": True,
        "description": "Estabilidade do ranking sob refinamento do timestep.",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--top", "int", default=5, help="quantos top candidatos"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "validate-top",
        "group": "Robustez V2",
        "long_running": True,
        "description": "Re-executa os top candidatos com outro integrador (ex.: IAS15).",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--top", "int", default=5, help="quantos top candidatos"),
            _a("--integrator", "str", default="ias15", help="integrador REBOUND (default: ias15)"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "null-models",
        "group": "Robustez V2",
        "long_running": True,
        "description": "Compara o delta real contra modelos nulos (shuffle_varpi etc.).",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--top", "int", default=5, help="quantos top candidatos"),
            _a("--n-shuffles", "int", default=20, help="quantos shuffles por modelo"),
            _a("--models", "str", default="shuffle_varpi", help="modelos separados por vírgula (ex.: shuffle_varpi,randomize_angles,no_p9_catalog_baseline)"),
            _a("--max-workers", "int", help="workers paralelos"),
        ),
    },
    {
        "name": "rescore",
        "group": "Robustez V2",
        "long_running": False,
        "description": "Rescore de uma run existente, sem simulação.",
        "args": (
            _a("--from-run", "path_run", required=True, help="diretório da run"),
            _a("--weights", "path", required=True, help="YAML de pesos"),
        ),
    },
    {
        "name": "report",
        "group": "Robustez V2",
        "long_running": False,
        "description": "Regera reports/report.md, com a seção de robustez V2 se presente.",
        "args": (_a("--from-run", "path_run", required=True, help="diretório da run"),),
    },
)

# Nunca disparável pelo dashboard, mesmo se um dia entrar no schema
# (`watch` é a visualização live em terminal, substituída pela própria UI).
BLOCKED_COMMANDS: frozenset[str] = frozenset({"watch"})

COMMAND_NAMES: frozenset[str] = frozenset(cmd["name"] for cmd in COMMANDS)


def get_command(name: str) -> dict[str, Any]:
    """Retorna a definição do subcomando ou levanta ValueError."""
    for cmd in COMMANDS:
        if cmd["name"] == name:
            return cmd
    raise ValueError(f"subcomando fora do schema do dashboard: {name!r}")


def validate(name: str, values: dict[str, Any]) -> list[str]:
    """Valida valores do formulário contra o schema; retorna problemas.

    Caminhos (kind ``path``/``path_run``) precisam existir — falha rápida
    ANTES de spawnar o processo. Relativos são resolvidos contra a raiz do
    repositório (o runner spawn com ``cwd=REPO_ROOT``).
    """
    cmd = get_command(name)
    problems: list[str] = []
    for arg in cmd["args"]:
        value = values.get(arg["flag"])
        if arg["required"] and (value is None or value == "" or value is False):
            problems.append(f"{arg['flag']} é obrigatório")
            continue
        if value in (None, "") or arg["kind"] == "flag":
            continue
        if arg["kind"] == "int":
            try:
                int(value)
            except (TypeError, ValueError):
                problems.append(f"{arg['flag']}: valor inteiro inválido ({value!r})")
        elif arg["kind"] == "float":
            try:
                float(value)
            except (TypeError, ValueError):
                problems.append(f"{arg['flag']}: valor numérico inválido ({value!r})")
        elif arg["kind"] in ("path", "path_run"):
            candidate = Path(str(value))
            if not candidate.is_absolute():
                candidate = REPO_ROOT / candidate
            if not candidate.exists():
                problems.append(f"{arg['flag']}: caminho não existe ({value})")
    return problems


def build_argv(name: str, values: dict[str, Any]) -> list[str]:
    """Monta o argv (sem o nome do subcomando) na ordem do schema."""
    cmd = get_command(name)
    argv: list[str] = []
    for arg in cmd["args"]:
        value = values.get(arg["flag"])
        if arg["kind"] == "flag":
            if value:
                argv.append(arg["flag"])
        elif value in (None, ""):
            continue
        elif arg["flag"].startswith("--"):
            argv.extend([arg["flag"], str(value)])
        else:  # posicional: só o valor, sem nome
            argv.append(str(value))
    return argv
