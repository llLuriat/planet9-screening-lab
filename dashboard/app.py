"""Aplicação NiceGUI do dashboard — painel em modo escuro, 100% pt-BR.

Restrições da tarefa (intocáveis aqui):
- servidor apenas em ``HOST`` = 127.0.0.1 (nunca 0.0.0.0/rede);
- o dashboard NUNCA inventa subcomando nem flag: o formulário é gerado do
  schema curado (``dashboard/commands.py``), verificado por teste contra o
  argparse de ``cli.py`` (o subcomando ``benchmark`` foi ADICIONADO ao
  cli.py sob autorização explícita do Auditor neste redesign, delegando ao
  script ``scripts/benchmark_integration_cost.py``);
- runs longas são lançadas via ``dashboard.runner`` (Popen detached —
  sobrevivem ao fechamento da UI);
- números/textos exibidos vêm dos artefatos via ``runstore``/``report``
  (caveats/interpretation verbatim, contrato do ``report.py``);
- estimativas de tempo NUNCA são inventadas: vêm do
  ``integration_years`` do YAML escolhido multiplicado pela taxa REAL
  medida em ``results/hardware_benchmark.json``; sem esses dois dados,
  o painel diz honestamente que não há estimativa.

Redesign de UX 2 (autorização do Auditor, antes da Tarefa C) — critério
de aceite: uma pessoa que não fez o simulador consegue usar sem
explicação prévia:
- UMA tela principal (Painel, ``/``) com os 3 comandos científicos
  principais como cartões em linguagem comum + benchmark + runs recentes;
- aba ``/testes`` separada com os 19 comandos de diagnóstico/robustez/
  utilidade (fora do fluxo principal);
- explicações em TOOLTIP (hover), não em texto permanente;
- formulários com defaults inteligentes já preenchidos
  (``dashboard/hardware.py``), sobrescrevíveis;
- run concluída ganha botão "Baixar resultados (zip)"
  (``dashboard/artifacts.py``);
- na página da run, DUAS barras de progresso explícitas: candidatos
  (done/total, de status.json/heartbeat.json) e integração (t_years das
  séries de checkpoint ÷ integration_years);
- ao lado do campo ``--budget``, hint de escala temporal (o que o
  horizonte significa e tempo estimado por candidato, par com/sem P9).
"""
from __future__ import annotations

import html
import json
import logging
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from nicegui import ui

from dashboard import __version__, artifacts, commands, config, hardware, report, runner, runstore
from dashboard.config import DEFAULT_HOST, DEFAULT_PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dashboard")

HOST = DEFAULT_HOST  # 127.0.0.1 — nunca 0.0.0.0 (regra não negociável)
PORT = DEFAULT_PORT
REPO_ROOT = commands.REPO_ROOT

# ---------------------------------------------------------------------------
# Apresentação (redesign): navegação, status, categorias, budgets
# ---------------------------------------------------------------------------

_NAV_ITEMS = (
    ("/", "Painel", "dashboard"),
    ("/testes", "Testes e diagnósticos", "science"),
    ("/jobs", "Jobs", "terminal"),
)

# Status de lifecycle -> rótulo pt-BR + cor de badge.
_STATUS_PT = {
    "completed": "concluída",
    "running": "em execução",
    "failed": "falhou",
    "invalid": "inválida",
    "unknown": "desconhecido",
}

_BADGE_COLOR = {
    "completed": "positive",
    "running": "info",
    "failed": "negative",
    "invalid": "warning",
    "unknown": "grey",
}

# ---------------------------------------------------------------------------
# Taxonomia do redesign 2 (aprovada pelo Auditor). Toda a lista de comandos
# do schema aparece em exatamente UM lugar da UI — travado por teste
# (tests/test_dashboard_redesign.py): 5 ações no Painel + benchmark dedicado
# + 19 comandos na aba /testes.
# ---------------------------------------------------------------------------

# (nome no schema, rótulo pt-BR em linguagem comum, ícone, tooltip/hover)
_HOME_PRIMARY: tuple[tuple[str, str, str, str], ...] = (
    (
        "screen",
        "Rodar triagem de candidatos",
        "travel_explore",
        "Pipeline completo por candidato: integra o sistema com e sem o P9 "
        "hipotético, aplica o modelo de viés do survey e ranqueia os "
        "candidatos. Resultados possíveis: triagem exploratória, candidato "
        "de interesse dentro do protocolo, nenhum candidato encontrado ou "
        "inconclusivo — nunca uma confirmação.",
    ),
    (
        "compare",
        "Comparar candidato com/sem Planeta Nove",
        "compare_arrows",
        "Par de controle para UM candidato: integra o sistema duas vezes "
        "(com P9 e sem P9) e compara o comportamento das órbitas dos ETNOs. "
        "É a base física do ranking da triagem.",
    ),
    (
        "montecarlo-scan",
        "Varredura Monte Carlo",
        "casino",
        "Varredura Monte Carlo/QMC do espaço de parâmetros do P9 (pode "
        "levar horas). Gera a distribuição de regiões compatíveis com os "
        "ETNOs — triagem exploratória, não confirmação.",
    ),
)

_HOME_SECONDARY: tuple[tuple[str, str, str, str], ...] = (
    (
        "resume",
        "Retomar run interrompida",
        "restart_alt",
        "Continua uma run interrompida de onde ela parou (usa os "
        "checkpoints; candidatos já concluídos não são refeitos).",
    ),
    (
        "report",
        "Regenerar relatório de uma run",
        "description",
        "Reconstrói o relatório (reports/report.md) de uma run existente — "
        "rápido, sem simulação.",
    ),
)

_BENCHMARK_TOOLTIP = (
    "Mede a taxa de integração REBOUND DESTA máquina (minutos) e atualiza "
    "results/hardware_benchmark.json — fonte das estimativas de tempo do "
    "painel. O arquivo anterior é copiado para .dashboard/backups/ antes de "
    "ser sobrescrito. O número novo vale apenas para esta máquina "
    "(provenance registrada no próprio arquivo)."
)

# Aba /testes: (título, legenda curta, comandos — todos existem no schema).
_TESTS_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Robustez",
        "Leave-one-out, convergência, validação do topo, modelos nulos e re-pontuação.",
        (
            "leave-one-out",
            "convergence",
            "validate-top",
            "null-models",
            "rescore",
            "diagnose-null-models",
            "diagnose-scoring",
        ),
    ),
    (
        "Diagnóstico de candidatos e estatística",
        "Investigação de candidatos e do clustering angular; não entram no funil de classificação.",
        (
            "explain-candidate",
            "why-rejected",
            "candidate-families",
            "circular-stats",
            "selection-bias-check",
            "megno",
        ),
    ),
    (
        "Sanidade e utilidades do pipeline",
        "Verificações rápidas do ambiente e do pipeline; úteis após mudanças.",
        ("smoke", "plan", "init-data", "physics-check", "status", "audit-run"),
    ),
)

_TESTS_TAB_META: dict[str, dict[str, str]] = {
    "Robustez": {"icon": "shield"},
    "Diagnóstico de candidatos e estatística": {"icon": "query_stats"},
    "Sanidade e utilidades do pipeline": {"icon": "health_and_safety"},
}

_COMMAND_LABELS: dict[str, str] = {
    **{name: label for name, label, _, _ in (*_HOME_PRIMARY, *_HOME_SECONDARY)},
    "benchmark": "Rodar benchmark de hardware",
}


def _home_command_names() -> tuple[str, ...]:
    """Nomes dos comandos expostos no Painel (cartões + benchmark)."""
    return (*{name for name, *_ in (*_HOME_PRIMARY, *_HOME_SECONDARY)}, "benchmark")


def _tests_command_names() -> tuple[str, ...]:
    """Nomes dos comandos da aba /testes, na ordem dos grupos."""
    return tuple(name for _, _, names in _TESTS_GROUPS for name in names)

# Rótulos pt-BR dos budgets padrão (o valor continua sendo o caminho real).
_BUDGET_OPTIONS: dict[str, str] = {
    "configs/budgets/low.yaml": "low — 50 anos (teste rápido de que o pipeline roda)",
    "configs/budgets/medium.yaml": "medium — 200 anos (sanidade um pouco mais longa)",
    "configs/budgets/secular.yaml": "secular — 4 Gyr (horizonte do artigo; usa checkpointing)",
    "configs/budgets/serious.yaml": "serious — 50 mil anos (robustez V2)",
}

_BUDGET_HINT_FALLBACK = (
    "Selecione (ou digite o caminho de) um budget; a estimativa aparece aqui "
    "quando o YAML e a medição desta máquina permitem calcular."
)

_MONTECARLO_HINT_FALLBACK = (
    "Escolha (ou digite o caminho de) um YAML de espaço de parâmetros; a "
    "estimativa de pior caso aparece aqui quando o YAML e a medição desta "
    "máquina permitem calcular."
)

def _pt_num(value: float, ndigits: int = 1) -> str:
    """Número em formato pt-BR (vírgula decimal, ponto de milhar)."""
    return f"{value:,.{ndigits}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _pair_hint_text(years: float, rate_years_per_second: float) -> str:
    """Frase de estimativa por candidato (par com/sem P9, single-core).

    Matemática pura (testável): ``years / rate`` é o tempo de UMA branch;
    o par com/sem P9 multiplica por 2 (mesma conta de
    ``scripts/benchmark_integration_cost.py`` e de ``engine.run_control_pair``).
    """
    pair_hours = years / rate_years_per_second * 2.0 / 3600.0
    base = f"Horizonte de {_pt_num(years, 0)} anos de integração."
    if pair_hours < 1.0 / 60.0:
        return f"{base} Par com/sem P9 por candidato: menos de 1 min (single-core)."
    if pair_hours < 2.0:
        return (
            f"{base} Par com/sem P9 por candidato: ≈ {_pt_num(pair_hours * 60.0, 0)} min "
            "(single-core). Em série, multiplique pelo n.º de candidatos."
        )
    return (
        f"{base} Par com/sem P9 por candidato: ≈ {_pt_num(pair_hours)} h (single-core); "
        f"ex.: 8 candidatos em série ≈ {_pt_num(pair_hours * 8.0, 0)} h. "
        "--max-workers divide entre os núcleos físicos."
    )


def _integration_years_from_budget(path_text: str) -> float | None:
    """``integration_years`` do YAML escolhido; None se legado/inexistente."""
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    if not candidate.is_file():
        return None
    try:
        data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(data, dict):
        value = data.get("integration_years")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _measured_years_per_second() -> float | None:
    """Taxa medida NESTA máquina (results/hardware_benchmark.json) ou None."""
    data = runstore.read_json(REPO_ROOT / "results" / "hardware_benchmark.json")
    rate = data.get("simulated_years_per_second") if isinstance(data, dict) else None
    if isinstance(rate, (int, float)) and float(rate) > 0.0:
        return float(rate)
    return None


def _benchmark_provenance() -> tuple[float, str] | None:
    """(taxa anos/s, data da medição) do benchmark REAL desta máquina.

    Fonte obrigatória de todo número de estimativa exibido na UI — o
    hint deve dizer ONDE/QUANDO foi medido, nunca apresentar como
    número universal.
    """
    data = runstore.read_json(REPO_ROOT / "results" / "hardware_benchmark.json")
    if not isinstance(data, dict):
        return None
    rate = data.get("simulated_years_per_second")
    measured = data.get("measured_on")
    if isinstance(rate, (int, float)) and float(rate) > 0.0:
        date = str(measured)[:10] if measured else "data desconhecida"
        return float(rate), date
    return None


def _time_hint_text(budget_path: str | None) -> str:
    """Hint do campo ``--budget``: significado prático + tempo estimado medido."""
    if not budget_path:
        return _BUDGET_HINT_FALLBACK
    budget_path = str(budget_path)
    known = _BUDGET_OPTIONS.get(budget_path)
    meaning = f"{known}. " if known else ""
    years = _integration_years_from_budget(budget_path)
    if years is None:
        return (
            f"{meaning}Sem estimativa: não foi possível ler integration_years "
            "deste YAML (budget legado?)."
        ).strip()
    rate = _measured_years_per_second()
    if rate is None:
        return (
            f"{meaning}Horizonte: {_pt_num(years, 0)} anos. Sem estimativa de tempo: "
            "rode scripts/benchmark_integration_cost.py nesta máquina "
            "(results/hardware_benchmark.json ausente ou sem taxa medida)."
        ).strip()
    prov = _benchmark_provenance()
    fonte = (
        f" Fonte: medição REAL desta máquina em {prov[1]} ({_pt_num(prov[0])} anos/s) "
        "— não é um número universal."
        if prov
        else ""
    )
    return f"{meaning}{_pair_hint_text(years, rate)}{fonte}".strip()


def _montecarlo_scan_hint_text(config_path: str | None) -> str:
    """Estimativa do montecarlo-scan: COTAS DE PIOR CASO calculáveis.

    Multiplicadores VÊM DO CÓDIGO (planet9lab/montecarlo.py): stage 2 =
    UMA branch por amostra (run_branch, L157, sem fator 2 — não é par de
    controle) no budget de ``stage2_budget``; stage 3 = UMA branch
    secular (L181) com secular.yaml FIXADO NO CÓDIGO (L297). O total
    exato não é estimável (depende da fração de sobreviventes por
    estágio, que o benchmark não mede) — declarado no texto.
    """
    if not config_path:
        return _MONTECARLO_HINT_FALLBACK
    candidate = Path(str(config_path))
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    try:
        data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        data = None
    if not isinstance(data, dict):
        return (
            "Estimativa não disponível: não foi possível ler as cotas "
            f"(max_stage2_samples / max_stage3_samples / stage2_budget) de {config_path}."
        )
    max_s2 = data.get("max_stage2_samples")
    max_s3 = data.get("max_stage3_samples")
    s2_years = _integration_years_from_budget(
        str(data.get("stage2_budget", "configs/budgets/montecarlo_stage2.yaml"))
    )
    s3_years = _integration_years_from_budget("configs/budgets/secular.yaml")
    if (
        not isinstance(max_s2, int)
        or not isinstance(max_s3, int)
        or s2_years is None
        or s3_years is None
    ):
        return (
            "Estimativa não disponível: cotas de amostras ou horizontes "
            "incompletos no YAML escolhido (o total exato também depende da "
            "fração de sobreviventes de cada estágio, que o benchmark não mede)."
        )
    rate = _measured_years_per_second()
    if rate is None:
        return (
            "Estimativa não disponível: sem taxa medida nesta máquina — rode "
            "scripts/benchmark_integration_cost.py (results/hardware_benchmark.json)."
        )
    s2_hours = max_s2 * s2_years / rate / 3600.0
    s3_hours = max_s3 * s3_years / rate / 3600.0
    total = s2_hours + s3_hours
    prov = _benchmark_provenance()
    fonte = (
        f" Fonte: medição REAL desta máquina em {prov[1]} ({_pt_num(prov[0])} anos/s) "
        "— não é um número universal."
        if prov
        else ""
    )
    n_points = data.get("n_points")
    head = (
        f"Varredura de {_pt_num(float(n_points), 0)} pontos (stage 1 analítico, "
        "custo desprezível). "
        if isinstance(n_points, int)
        else ""
    )
    return (
        f"{head}PIOR CASO (todas as cotas cheias): stage 2 ≤ {max_s2} amostras × "
        f"1 branch de {_pt_num(s2_years, 0)} anos ≈ {_pt_num(s2_hours * 60.0, 0)} min; "
        f"stage 3 ≤ {max_s3} amostra(s) × 1 branch de {_pt_num(s3_years, 0)} anos "
        f"(secular.yaml, fixado no código) ≈ {_pt_num(s3_hours)} h; "
        f"total ≤ ≈ {_pt_num(total)} h. O total real depende da fração de pontos "
        "que sobrevive a cada estágio — o benchmark de integração não mede isso, "
        f"então o valor exato não é estimável.{fonte}"
    )


def _age_text(seconds: float | None) -> str:
    """Idade de um heartbeat em texto pt-BR curto."""
    if seconds is None:
        return "—"
    if seconds < 90.0:
        return f"{int(seconds)} s atrás"
    if seconds < 5400.0:
        return f"{int(seconds // 60)} min atrás"
    return f"{seconds / 3600.0:.1f} h atrás"


def _assert_localhost_bind() -> None:
    """Regra não negociável: o servidor nunca pode bindar fora de localhost."""
    import ipaddress

    allowed = (ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1"))
    if ipaddress.ip_address(HOST) not in allowed:
        raise RuntimeError(f"dashboard recusou iniciar: HOST={HOST!r} não é localhost")


def _validate_cli_available() -> None:
    """Falha rápido (na inicialização) se o pacote do pipeline não importar."""
    import importlib

    importlib.import_module("planet9lab.cli")


@contextmanager
def page_shell(active: str):
    """Cabeçalho + navegação + modo escuro; envolve o conteúdo de cada página.

    O painel INTEIRO nasce em modo escuro (decisão do Auditor). A página
    ativa fica destacada em cor primária; as demais em cinza.
    """
    ui.dark_mode(True)
    with ui.header().classes("bg-dark items-center justify-between q-px-lg q-py-sm"):
        with ui.row().classes("items-center gap-2"):
            ui.label("🪐 Planet9 Screening Lab").classes("text-h6")
            ui.badge("triagem exploratória — não confirma candidato", color="grey-7").props("outline")
        with ui.row().classes("items-center gap-1"):
            for path, label, icon in _NAV_ITEMS:
                is_active = path == active
                button = ui.button(label, icon=icon, on_click=lambda _, p=path: ui.navigate.to(p))
                button.props("flat")
                button.props("color=primary" if is_active else "color=grey-5")
    with ui.column().classes("w-full max-w-5xl mx-auto q-px-lg q-py-md gap-4"):
        yield


# ---------------------------------------------------------------------------
# Página: / (runs)
# ---------------------------------------------------------------------------


def _status_pt(status: Any) -> str:
    text = str(status) if status else "unknown"
    return _STATUS_PT.get(text, text)


def _badge_pt(status: Any) -> None:
    text = str(status) if status else "unknown"
    ui.badge(_STATUS_PT.get(text, text), color=_BADGE_COLOR.get(text, "grey"))


def _progress_cell(info: dict[str, Any]) -> str:
    """Progresso (candidatos done/total) como linha única da tabela."""
    total, done = info.get("candidates_total"), info.get("candidates_done")
    if not isinstance(total, (int, float)) or not total:
        return "—"
    pct = 100.0 * (done or 0) / total
    return f"{_pt_num(pct, 0)}% ({done}/{int(total)} candidatos)"


def _home_page() -> None:
    with page_shell("/"):
        ui.label("O que você quer rodar?").classes("text-h5")
        with ui.grid(columns=3).classes("w-full"):
            for name, label, icon, tip in _HOME_PRIMARY:
                with ui.card().classes("w-full"):
                    card = ui.button(
                        label,
                        icon=icon,
                        on_click=lambda _, n=name: ui.navigate.to(f"/executar/{n}"),
                    )
                    card.props("flat align=left").classes("w-full")
                    card.tooltip(tip)
                    card.mark(f"home-{name}")
        with ui.row().classes("w-full items-center gap-1 flex-wrap"):
            ui.label("Operações sobre runs existentes:").classes("text-caption text-grey-5")
            for name, label, icon, tip in _HOME_SECONDARY:
                button = ui.button(
                    label,
                    icon=icon,
                    on_click=lambda _, n=name: ui.navigate.to(f"/executar/{n}"),
                )
                button.props("flat")
                button.tooltip(tip)
                button.mark(f"home-{name}")
        benchmark = ui.button(
            "Rodar benchmark de hardware",
            icon="speed",
            on_click=lambda: ui.navigate.to("/executar/benchmark"),
        )
        benchmark.props("flat")
        benchmark.tooltip(_BENCHMARK_TOOLTIP)
        benchmark.mark("home-benchmark")
        _bm = hardware.benchmark_summary()
        if _bm["present"]:
            _rate = _bm["simulated_years_per_second"]
            _rate_txt = _pt_num(float(_rate)) if isinstance(_rate, (int, float)) else "?"
            _onde = (
                "nesta máquina"
                if _bm["matches_this_machine"]
                else "em OUTRA máquina — re-meça aqui antes de planejar horizontes"
            )
            ui.label(
                f"Último benchmark: {_rate_txt} anos/s simulados ({_onde}; medido em "
                f"{_bm['measured_on']}). Resultado completo em "
                "results/hardware_benchmark.json — botão 'Ver resultado' em Jobs."
            ).classes("text-caption text-grey-6").mark("home-benchmark-summary")
        else:
            ui.label(
                "Sem benchmark medido ainda: rode o benchmark — o resultado "
                "aparece aqui e em Jobs (botão 'Ver resultado')."
            ).classes("text-caption text-grey-6").mark("home-benchmark-summary")
        ui.separator()
        ui.label("Runs").classes("text-h6")
        ui.label(
            "Cada linha é uma run em runs/. Clique na linha para abrir o relatório, "
            "bloqueadores e progresso detalhado."
        ).classes("text-caption text-grey-6")
        runs = runstore.list_runs(config.run_root())
        if not runs:
            with ui.card():
                ui.label("Nenhuma run encontrada em runs/.")
                ui.label(
                    "Clique num dos cartões acima para disparar a primeira "
                    "(budget low ou medium levam segundos/minutos)."
                ).classes("text-caption text-grey-6")
            return
        columns = [
            {"name": "run_id", "label": "Run", "field": "run_id", "align": "left", "required": True},
            {"name": "status_pt", "label": "Situação", "field": "status_pt"},
            {"name": "result", "label": "Resultado global", "field": "result", "align": "left"},
            {"name": "progress", "label": "Progresso", "field": "progress", "align": "left"},
            {"name": "started_at", "label": "Início", "field": "started_at", "align": "left"},
            {"name": "ended_at", "label": "Fim", "field": "ended_at", "align": "left"},
            {"name": "n_blockers", "label": "Bloqueadores", "field": "n_blockers"},
        ]
        rows = [
            {
                "run_id": info["run_id"],
                "status_pt": _status_pt(info["status"]),
                "result": info.get("global_result_status") or "—",
                "progress": _progress_cell(info),
                "started_at": info.get("started_at") or "—",
                "ended_at": info.get("ended_at") or "—",
                "n_blockers": len(info.get("blockers") or []),
            }
            for info in runs
        ]
        with ui.card().classes("w-full"):
            table = ui.table(columns=columns, rows=rows, row_key="run_id").classes("w-full")
            table.props("flat dense")
            table.add_slot(
                "body-cell-status_pt",
                """
                <q-td :props="props">
                  <q-badge :color="props.row.status_pt === 'concluída' ? 'positive' :
                                   props.row.status_pt === 'em execução' ? 'info' :
                                   props.row.status_pt === 'falhou' ? 'negative' :
                                   props.row.status_pt === 'inválida' ? 'warning' : 'grey'">
                    {{ props.row.status_pt }}
                  </q-badge>
                </q-td>
                """,
            )

            def _open(e: Any) -> None:
                ui.navigate.to(f"/run/{e.args[1]['run_id']}")

            table.on("rowClick", _open)
        ui.label(
            "Resultado global e bloqueadores vêm dos artefatos canônicos (status.json, "
            "audit/); vocabulário científico verbatim — nada é reescrito aqui."
        ).classes("text-caption text-grey-6")


# ---------------------------------------------------------------------------
# Página: /run/{run_id} — detalhe com 2 barras + relatório (abaixo)
# ---------------------------------------------------------------------------


def _progress_bar(label: str, pct: float | None, caption: str) -> None:
    """Barra + rótulo; pct None mostra '—' e barra neutra (honesto)."""
    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(label).classes("text-subtitle2")
            ui.label("—" if pct is None else f"{_pt_num(pct, 1)}%").classes("text-subtitle2")
        bar = ui.linear_progress(value=(pct / 100.0) if pct is not None else 0.0).classes("w-full")
        if pct is None:
            bar.props("color=grey-7")
        ui.label(caption).classes("text-caption text-grey-6")


def _do_download(run_dir: Path) -> None:
    """Gera o .zip dos artefatos canônicos e dispara o download.

    ``ui.download.content`` (bytes) funciona igual no navegador real e na
    simulação de usuário dos testes. O zip também é persistido em
    ``.dashboard/downloads/`` para inspeção posterior (o download do
    navegador NÃO é a única cópia).
    """
    try:
        zip_path = artifacts.build_results_zip(run_dir)
    except OSError as exc:
        ui.notify(f"Falha ao gerar o zip: {exc}", type="negative")
        return
    data = zip_path.read_bytes()
    ui.download.content(data, filename=zip_path.name, media_type="application/zip")


def _backup_benchmark() -> Path | None:
    """Copia results/hardware_benchmark.json para .dashboard/backups/.

    O subcomando ``benchmark`` SOBRESCREVE esse arquivo com a medição DESTA
    máquina; o backup preserva o número rastreado anterior (que pode ser a
    medição de outra máquina, como a LURIAT) para o histórico do Auditor.
    Estado gitignored do dashboard — nada é escrito dentro de results/.
    """
    source = REPO_ROOT / "results" / "hardware_benchmark.json"
    if not source.is_file():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = config.backups_dir() / f"hardware_benchmark_{stamp}.json"
    shutil.copy2(source, dest)
    return dest


def _detail_page(run_id: str) -> None:
    run_dir = runstore.resolve_run(config.run_root(), run_id)
    if run_dir is None:
        with page_shell(f"/run/{run_id}"):
            ui.label(f"Run “{run_id}” não encontrada em runs/.")
            ui.link("← voltar para Runs", "/")
        return

    with page_shell(f"/run/{run_id}"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(f"Run {run_id}").classes("text-h5")
                ui.link("← todas as runs", "/").classes("text-caption")
            status = runstore.lifecycle_status(run_dir)
            with ui.row().classes("items-center gap-2"):
                _badge_pt(status)
                if status == "completed":
                    download = ui.button(
                        "Baixar resultados (zip)",
                        icon="download",
                        on_click=lambda run_dir=run_dir: _do_download(run_dir),
                    )
                    download.tooltip(
                        "Gera um .zip com os artefatos de auditoria desta run: "
                        "status/config/manifestos/hashes, events.log, results/, audit/, "
                        "reports/, presentation/, diagnostics/, o relatório HTML e um "
                        "MANIFESTO.txt. Fica de fora (decisão documentada): checkpoints "
                        "pesados da integração secular, cache volátil de candidatos e "
                        "locks. Os arquivos canônicos continuam em runs/."
                    )
                    download.mark("download-results")
                ui.button(
                    "Atualizar", icon="refresh", on_click=lambda: ui.navigate.to(f"/run/{run_id}")
                )
        if status == "running":
            # Auto-refresh só enquanto a run está de fato em execução; a
            # página recarrega sozinha a cada 10 s (barras de progresso ao vivo).
            ui.timer(10.0, lambda: ui.run_javascript("location.reload()"))

        with ui.card().classes("w-full"):
            ui.label("Progresso").classes("text-h6")
            info = runstore.progress_info(run_dir)
            done, total = info["candidates_done"], info["candidates_total"]
            candidate_pct = (
                100.0 * done / total
                if isinstance(done, (int, float))
                and isinstance(total, (int, float))
                and total
                else None
            )
            _progress_bar(
                "Candidatos processados",
                candidate_pct,
                f"{done}/{int(total)} candidatos concluídos (fonte: {info.get('source')}; "
                f"falhas: {info.get('candidates_failed', 0)}).",
            )
            _progress_bar(
                "Integração secular (horizonte do budget)",
                info.get("max_series_pct"),
                (
                    "Fração do horizonte já integrada, lida das séries de checkpoint "
                    f"(t_years ÷ {_pt_num(info['integration_years'] or 0, 0)} anos). "
                    "Budgets curtos não geram checkpoints — sem eles, não há base "
                    "para estimar (o painel mostra '—' em vez de inventar)."
                ),
            )
            age = info.get("heartbeat_age_s")
            stale = age is None or age >= 600
            ui.label(
                f"Último sinal de vida (heartbeat): {_age_text(age)}."
                + (" Atenção: heartbeat ausente ou antigo (>= 10 min)." if stale else "")
            ).classes("text-caption text-grey-6")

        with ui.card().classes("w-full"):
            ui.label("Bloqueadores").classes("text-h6")
            blockers = runstore.load_blockers(run_dir)
            if not blockers:
                ui.label("Nenhum bloqueador registrado nesta run.").classes("text-caption")
            for blocker in blockers:
                with ui.row().classes("w-full items-start gap-2 q-mb-xs"):
                    severity = str(blocker.get("severity") or "info")
                    color = {"science_limit": "warning", "hard": "negative"}.get(severity, "grey")
                    ui.badge(severity, color=color)
                    with ui.column().classes("gap-0"):
                        ui.label(str(blocker.get("blocker_id") or "?")).classes("text-bold")
                        ui.label(str(blocker.get("message") or "")).classes("text-caption")

        with ui.card().classes("w-full"):
            ui.label("Relatório da run").classes("text-h6")
            ui.label(
                "Caveats e interpretações aparecem na ÍNTEGRA, sem reescrita "
                "(contrato com report.py)."
            ).classes("text-caption text-grey-6")
            # CSS vai no <head> (ui.add_head_html): <style> dentro do ui.html
            # é removido pelo sanitizador client-side (DOMPurify) — era a
            # causa do relatório renderizar sem formatação nenhuma. O
            # fragmento carrega só classes + data-verbatim (contrato igual).
            ui.add_head_html(f"<style>{report.REPORT_CSS}</style>")
            ui.html(report.render_run_report_fragment(run_dir)).classes("w-full").mark(
                "run-report-fragment"
            )


# ---------------------------------------------------------------------------
# Página: /launch — comandos por categoria + estimativa de tempo
# ---------------------------------------------------------------------------


def _initial_value(arg: dict[str, Any], run_options: list[str]) -> Any:
    """Valor inicial do campo: default inteligente JÁ PREENCHIDO.

    Regra do redesign (aprovada pelo Auditor): todo campo com um valor
    óbvio e verificável nasce preenchido — o usuário só sobrescreve se
    quiser. Nada aqui inventa número:
    - ``--max-workers`` → threads lógicas reais desta máquina
      (dashboard/hardware.py; o benchmark do repo só é citado no tooltip,
      com o aviso explícito quando foi medido em OUTRA máquina);
    - ``--run-root`` → ``runs`` (o diretório canônico do projeto);
    - ``--budget`` → ``low`` (evita que um clique descuidado dispare o
      horizonte de 4 Gyr, que leva dias; o hint ao lado mostra o custo);
    - demais defaults (seed, top, alpha, --config) vêm do schema espelhado
      do cli.py; campos sem default nascem vazios de propósito.
    """
    flag, kind = arg["flag"], arg["kind"]
    if kind == "path_run":
        return run_options[0] if run_options else None
    if flag == "--budget":
        return "configs/budgets/low.yaml"
    if flag == "--run-root":
        return hardware.suggest_run_root()
    if flag == "--max-workers":
        return hardware.suggest_max_workers()
    return arg.get("default")


def _make_field(arg: dict[str, Any], run_options: list[str]) -> Any:
    """Widget do formulário para um argumento.

    Explicações estáticas vão em TOOLTIP (requisito do redesign: nenhum
    texto permanente explicativo); hints DINÂMICOS (estimativa de tempo do
    budget) continuam como label mutável ao lado do campo.
    """
    flag, kind = arg["flag"], arg["kind"]
    label = f"{flag} {'*' if arg['required'] else ''}"
    initial = _initial_value(arg, run_options)
    if kind == "path_run":
        widget = ui.select(
            run_options, with_input=True, new_value_mode="add", label=label, value=initial
        ).classes("w-full")
        widget.tooltip(
            str(arg["help"]) if arg["help"] else "Escolha uma run existente de runs/ ou digite o nome."
        )
    elif kind == "path" and flag == "--budget":
        widget = ui.select(
            list(_BUDGET_OPTIONS.keys()),
            with_input=True,
            new_value_mode="add",
            label=label,
            value=initial,
        ).classes("w-full")
        widget.tooltip(str(arg["help"]))
    elif kind == "flag":
        widget = ui.switch(label).classes("w-full")
        if arg["help"]:
            widget.tooltip(str(arg["help"]))
    elif kind == "int":
        widget = ui.number(label, format="%.0f", precision=0, value=initial).classes("w-full")
        widget.tooltip(hardware.max_workers_hint() if flag == "--max-workers" else str(arg["help"]))
    elif kind == "float":
        widget = ui.number(label, value=initial).classes("w-full")
        if arg["help"]:
            widget.tooltip(str(arg["help"]))
    else:
        widget = ui.input(label, value=initial).classes("w-full")
        if arg["help"]:
            widget.tooltip(str(arg["help"]))
    widget.mark(f"arg{flag}")
    return widget


def _launch_form(cmd: dict[str, Any], output: Any, run_options: list[str] | None = None) -> None:
    """Formulário de UM comando: obrigatórios antes dos opcionais + hint.

    Explicações estáticas ficam nos TOOLTIPS dos campos; só o hint dinâmico
    do ``--budget`` (estimativa medida) permanece visível como label.
    """
    name = cmd["name"]
    fields: dict[str, Any] = {}
    if run_options is None:
        run_options = [info["run_id"] for info in runstore.list_runs(config.run_root())]

    with ui.column().classes("w-full gap-2"):
        for section_label, args in (
            ("Obrigatórios", [a for a in cmd["args"] if a["required"]]),
            ("Opcionais", [a for a in cmd["args"] if not a["required"]]),
        ):
            if not args:
                continue
            ui.label(section_label).classes("text-subtitle2 text-grey-5")
            with ui.grid(columns=2).classes("w-full gap-2"):
                for arg in args:
                    with ui.column().classes("gap-0 w-full"):
                        fields[arg["flag"]] = _make_field(arg, run_options)
                        hint_text = None
                        if arg["kind"] == "path" and arg["flag"] == "--budget":
                            hint_text = _time_hint_text
                        elif (
                            arg["kind"] == "path"
                            and arg["flag"] == "--config"
                            and name == "montecarlo-scan"
                        ):
                            # montecarlo-scan: estimativa de pior caso a partir
                            # do YAML de espaço de parâmetros escolhido.
                            hint_text = _montecarlo_scan_hint_text
                        if hint_text is not None:
                            budget_widget = fields[arg["flag"]]
                            hint = ui.label(hint_text(budget_widget.value)).classes(
                                "text-caption text-grey-5"
                            )

                            def _update_hint(
                                _change: Any,
                                budget_widget: Any = budget_widget,
                                hint: Any = hint,
                                hint_text: Any = hint_text,
                            ) -> None:
                                hint.set_text(hint_text(budget_widget.value))

                            budget_widget.on_value_change(_update_hint)

    ui.separator()
    with ui.row().classes("w-full items-center gap-4"):
        launch_button = ui.button(
            f"Executar {name}",
            icon="play_arrow",
            on_click=lambda name=name, cmd=cmd, fields=fields: _do_launch(
                name, cmd, fields, output
            ),
        )
        launch_button.mark(f"executar-{name}")
        if cmd.get("long_running"):
            launch_button.props("color=primary")
            ui.label(
                "Processo longo: roda DESACOPLADO (sobrevive ao fechamento do "
                "dashboard). Acompanhe em Jobs e depois em Runs."
            ).classes("text-caption text-grey-6")
        else:
            ui.label("Rápido: também roda desacoplado; veja o log em Jobs.").classes(
                "text-caption text-grey-6"
            )


def _do_launch(name: str, cmd: dict[str, Any], fields: dict[str, Any], output: Any) -> None:
    values: dict[str, Any] = {}
    for arg in cmd["args"]:
        widget = fields.get(arg["flag"])
        if widget is None:
            continue
        value = widget.value
        if arg["kind"] == "int":
            value = int(value) if value not in (None, "") else None
        elif arg["kind"] == "float":
            value = float(value) if value not in (None, "") else None
        if value == "":
            value = None
        values[arg["flag"]] = value
    problems = commands.validate(name, values)
    if problems:
        output.push("ERRO de validação: " + "; ".join(problems))
        return
    if name == "benchmark":
        backup = _backup_benchmark()
        if backup is not None:
            output.push(f"backup do benchmark anterior salvo em: {backup}")
    try:
        record = runner.launch(name, values)
    except ValueError as exc:
        output.push(f"ERRO: {exc}")
        return
    output.push(f"lançado {record['job_id']} → PID {record['pid']}: {' '.join(record['cmd'])}")


def _tests_page() -> None:
    with page_shell("/testes"):
        ui.label("Testes e diagnósticos").classes("text-h5")
        ui.label(
            "Verificações de robustez, diagnóstico de candidatos e utilidades do "
            "pipeline — não fazem parte do fluxo principal de triagem. As "
            "explicações aparecem ao passar o mouse (tooltip) sobre cada comando "
            "e campo."
        ).classes("text-caption text-grey-6")
        output = ui.log(max_lines=100).classes("w-full h-24")
        run_options = [info["run_id"] for info in runstore.list_runs(config.run_root())]
        for group_title, caption, names in _TESTS_GROUPS:
            cmds = [commands.get_command(n) for n in names]
            meta = _TESTS_TAB_META[group_title]
            with ui.expansion(
                f"{group_title} ({len(cmds)})", caption=caption, icon=meta["icon"]
            ).classes("w-full"):
                for cmd in cmds:
                    with ui.expansion(
                        cmd["name"],
                        caption=str(cmd.get("description") or ""),
                        icon="chevron_right",
                    ).classes("w-full"):
                        _launch_form(cmd, output, run_options)


def _executar_page(name: str) -> None:
    """Página de formulário de UM comando (destino dos cartões do Painel).

    Máximo de 2 cliques desde o Painel: cartão → formulário já preenchido →
    botão Executar (o 2º clique dispara).
    """
    try:
        cmd = commands.get_command(name)
    except ValueError:
        with page_shell(f"/executar/{name}"):
            ui.label(f"Comando “{name}” não existe no schema do dashboard.")
            ui.link("← voltar para o Painel", "/")
        return
    label = _COMMAND_LABELS.get(name, name)
    with page_shell(f"/executar/{name}"):
        ui.label(label).classes("text-h5")
        ui.label(
            "Formulário gerado do schema curado (mesmos flags do cli.py, "
            "verificado por teste). Campos óbvios já vêm preenchidos; as "
            "explicações estão nos tooltips de cada campo."
        ).classes("text-caption text-grey-6")
        output = ui.log(max_lines=100).classes("w-full h-24")
        _launch_form(cmd, output)


# ---------------------------------------------------------------------------
# Página: /jobs
# ---------------------------------------------------------------------------


def _benchmark_output_path(polled: dict[str, Any]) -> str:
    """Caminho do JSON de resultado de um job benchmark (default do CLI)."""
    tokens = str(polled.get("command") or "").split()
    if "--output" in tokens:
        index = tokens.index("--output")
        if index + 1 < len(tokens):
            return tokens[index + 1]
    return str(REPO_ROOT / "results" / "hardware_benchmark.json")


def _jobs_page() -> None:
    with page_shell("/jobs"):
        ui.label("Jobs lançados pelo dashboard").classes("text-h5")
        ui.label(
            "Processos desacoplados: seguem rodando mesmo se você fechar esta "
            "página (ou o dashboard). Clique numa linha para ver a cauda do log. "
            "Jobs de benchmark têm botão 'Ver resultado' — benchmark não é run "
            "de screening: o resultado é um JSON (results/hardware_benchmark.json "
            "ou o --output informado), não ranking.csv."
        ).classes("text-caption text-grey-6")
        rows = []
        benchmark_jobs: list[tuple[str, str]] = []  # (job_id, caminho do JSON)
        for record in runner.list_jobs():
            polled = runner.poll(record["job_id"])
            if "benchmark" in str(polled.get("command") or ""):
                benchmark_jobs.append((polled["job_id"], _benchmark_output_path(polled)))
            rows.append(
                {
                    "job_id": polled["job_id"],
                    "command": polled["command"],
                    "pid": polled["pid"],
                    "launched_at": polled.get("launched_at", ""),
                    "finished": "terminou" if polled.get("finished") else "rodando",
                }
            )
        if not rows:
            with ui.card():
                ui.label("Nenhum job lançado ainda.")
            return
        columns = [
            {"name": "job_id", "label": "Job", "field": "job_id", "align": "left"},
            {"name": "command", "label": "Comando", "field": "command", "align": "left"},
            {"name": "pid", "label": "PID", "field": "pid"},
            {"name": "launched_at", "label": "Lançado em", "field": "launched_at", "align": "left"},
            {"name": "finished", "label": "Situação", "field": "finished"},
        ]
        with ui.card().classes("w-full"):
            table = ui.table(columns=columns, rows=rows, row_key="job_id").classes("w-full")
            table.props("flat dense")
        log_container = ui.column().classes("w-full")

        def _show_log(e: Any) -> None:
            job_id = e.args[1]["job_id"]
            log_container.clear()
            with log_container, ui.card().classes("w-full"):
                ui.label(f"Log (cauda) — job {job_id}").classes("text-subtitle2")
                ui.html(
                    f"<pre style='white-space:pre-wrap;margin:0'>"
                    f"{html.escape(runner.tail(job_id))}</pre>"
                )

        table.on("rowClick", _show_log)

        benchmark_container = ui.column().classes("w-full")

        def _show_benchmark_result(job_id: str, path_text: str) -> None:
            """Resultado de benchmark: resumo + JSON na ÍNTEGRA.

            Benchmark não é run de screening (não tem results/ranking.csv nem
            diagnostics/) — NUNCA aplicar o template de run científica a ele.
            """
            benchmark_container.clear()
            with benchmark_container, ui.card().classes("w-full"):
                ui.label(f"Resultado do benchmark — job {job_id}").classes("text-subtitle2")
                resolved = Path(path_text)
                if not resolved.is_absolute():
                    resolved = REPO_ROOT / resolved
                data = runstore.read_json(resolved)
                if not data:
                    ui.label(
                        f"Nenhum resultado em {path_text} — o job ainda está "
                        "rodando ou falhou (veja o log acima)."
                    ).classes("text-caption text-grey-6")
                    return
                rate = data.get("simulated_years_per_second")
                bits: list[str] = []
                if isinstance(rate, (int, float)):
                    bits.append(f"{_pt_num(float(rate))} anos simulados por segundo")
                rec = data.get("recommended_integration_years")
                if isinstance(rec, (int, float)):
                    bits.append(f"horizonte recomendado: {_pt_num(float(rec), 0)} anos")
                if bits:
                    ui.label(" · ".join(bits)).classes("text-caption")
                ui.code(
                    json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2),
                    language="json",
                ).classes("w-full")

        if benchmark_jobs:
            with ui.card().classes("w-full"):
                ui.label("Resultados de benchmark").classes("text-subtitle2")
                ui.label(
                    "Benchmark mede o hardware DESTA máquina; não produz ranking "
                    "nem diagnostics — o resultado é o JSON abaixo, na íntegra."
                ).classes("text-caption text-grey-6")
                for job_id, output_path in benchmark_jobs:
                    ui.button(
                        f"Ver resultado — job {job_id}",
                        icon="insights",
                        on_click=lambda _, jid=job_id, p=output_path: _show_benchmark_result(
                            jid, p
                        ),
                    ).props("flat").mark(f"benchmark-result-{job_id}")


# ---------------------------------------------------------------------------
# Rotas + main
# ---------------------------------------------------------------------------


@ui.page("/")
def index() -> None:
    _home_page()


@ui.page("/run/{run_id}")
def run_detail(run_id: str) -> None:
    _detail_page(run_id)


@ui.page("/testes")
def tests_page() -> None:
    _tests_page()


@ui.page("/executar/{name}")
def executar_page(name: str) -> None:
    _executar_page(name)


@ui.page("/jobs")
def jobs_page() -> None:
    _jobs_page()


def main() -> int:
    _assert_localhost_bind()
    _validate_cli_available()
    log.info("dashboard v%s em http://%s:%s (somente localhost)", __version__, HOST, PORT)
    print(f"Dashboard em http://{HOST}:{PORT} (bind exclusivo em localhost; Ctrl+C para sair)")
    # reload=False e show=False: servidor uvicorn embutido, sem abrir navegador
    # e sem watcher — o processo pode rodar em background por dias (Tarefa C).
    ui.run(
        host=HOST,
        port=PORT,
        title="Planet9 Screening Lab — Dashboard",
        reload=False,
        show=False,
        favicon="🪐",
    )
    return 0
