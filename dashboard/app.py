"""Aplicação NiceGUI do dashboard — painel em modo escuro, 100% pt-BR.

Restrições da tarefa (intocáveis aqui):
- servidor apenas em ``HOST`` = 127.0.0.1 (nunca 0.0.0.0/rede);
- NUNCA altera ``cli.py``/``planet9lab/``: só chama os comandos existentes
  via ``dashboard.runner`` (Popen detached — runs longas sobrevivem ao
  fechamento da UI);
- números/textos exibidos vêm dos artefatos via ``runstore``/``report``
  (caveats/interpretation verbatim, contrato do ``report.py``);
- estimativas de tempo NUNCA são inventadas: vêm do
  ``integration_years`` do YAML escolhido multiplicado pela taxa REAL
  medida em ``results/hardware_benchmark.json``; sem esses dois dados,
  o painel diz honestamente que não há estimativa.

Redesign de UX (autorização do Auditor, antes da Tarefa C):
- painel inteiro em modo escuro; navegação superior com a página ativa
  destacada; 4 páginas (Runs, Disparar, Detalhe da run, Jobs);
- na /launch, comandos agrupados por categoria funcional em accordions;
- na página da run, DUAS barras de progresso explícitas: candidatos
  (done/total, de status.json/heartbeat.json) e integração (t_years das
  séries de checkpoint ÷ integration_years);
- ao lado do campo ``--budget``, hint de escala temporal (o que o
  horizonte significa e tempo estimado por candidato, par com/sem P9).
"""
from __future__ import annotations

import html
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml
from nicegui import ui

from dashboard import __version__, commands, report, runner, runstore
from dashboard.config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_RUN_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dashboard")

HOST = DEFAULT_HOST  # 127.0.0.1 — nunca 0.0.0.0 (regra não negociável)
PORT = DEFAULT_PORT
RUN_ROOT = DEFAULT_RUN_ROOT
REPO_ROOT = commands.REPO_ROOT

# ---------------------------------------------------------------------------
# Apresentação (redesign): navegação, status, categorias, budgets
# ---------------------------------------------------------------------------

_NAV_ITEMS = (
    ("/", "Runs", "dashboard"),
    ("/launch", "Disparar", "rocket_launch"),
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

# Ordem fixa das categorias na página de disparo (accordion). As chaves são
# os valores de ``group`` do schema curado (dashboard/commands.py).
_GROUP_ORDER: tuple[str, ...] = ("Runs", "Infra", "Diagnósticos", "Robustez V2")

_GROUP_META: dict[str, dict[str, str]] = {
    "Runs": {
        "label": "Execução de runs",
        "caption": "Screening, comparação, Monte Carlo, retomada e verificação do pipeline.",
    },
    "Infra": {
        "label": "Utilidades e infraestrutura",
        "caption": "Status das runs e verificação do ambiente de física.",
    },
    "Diagnósticos": {
        "label": "Diagnósticos e auditoria",
        "caption": "Investigação de runs existentes; não entram no funil de classificação.",
    },
    "Robustez V2": {
        "label": "Robustez (V2)",
        "caption": "Leave-one-out, modelos nulos, convergência, validação do topo e re-pontuação.",
    },
}

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
    return f"{meaning}{_pair_hint_text(years, rate)}".strip()


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


def _index_page() -> None:
    with page_shell("/"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Runs").classes("text-h5")
            ui.button("Nova run", icon="add", on_click=lambda: ui.navigate.to("/launch"))
        ui.label(
            "Cada linha é uma run em runs/. Clique na linha para abrir o relatório, "
            "bloqueadores e progresso detalhado."
        ).classes("text-caption text-grey-6")
        runs = runstore.list_runs(RUN_ROOT)
        if not runs:
            with ui.card():
                ui.label("Nenhuma run encontrada em runs/.")
                ui.label(
                    "Dispare a primeira em “Disparar” (comece pelo budget low ou medium, "
                    "que levam segundos/minutos)."
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


def _detail_page(run_id: str) -> None:
    run_dir = runstore.resolve_run(RUN_ROOT, run_id)
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
            ui.html(report.render_run_report(run_dir)).classes("w-full")


# ---------------------------------------------------------------------------
# Página: /launch — comandos por categoria + estimativa de tempo
# ---------------------------------------------------------------------------


def _make_field(arg: dict[str, Any], run_options: list[str]) -> Any:
    """Widget do formulário para um argumento, com tooltip do help."""
    flag, kind = arg["flag"], arg["kind"]
    label = f"{flag} {'*' if arg['required'] else ''}"
    if kind == "path_run":
        initial = run_options[0] if (run_options and arg["required"]) else None
        select = ui.select(
            run_options, with_input=True, new_value_mode="add", label=label, value=initial
        ).classes("w-full")
        select.tooltip("Escolha uma run existente de runs/ ou digite o nome.")
        return select
    if kind == "path" and flag == "--budget":
        initial = "configs/budgets/medium.yaml" if not arg["required"] else None
        return ui.select(
            list(_BUDGET_OPTIONS.keys()),
            with_input=True,
            new_value_mode="add",
            label=label,
            value=initial,
        ).classes("w-full")
    if kind == "flag":
        return ui.switch(label).classes("w-full")
    if kind == "int":
        return ui.number(label, format="%.0f", precision=0).classes("w-full")
    if kind == "float":
        return ui.number(label).classes("w-full")
    return ui.input(label).classes("w-full")


def _launch_form(cmd: dict[str, Any], output: Any) -> None:
    """Formulário de UM comando: obrigatórios antes dos opcionais + hint."""
    name = cmd["name"]
    fields: dict[str, Any] = {}
    run_options = [info["run_id"] for info in runstore.list_runs(RUN_ROOT)]

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
                        if arg["help"]:
                            ui.label(arg["help"]).classes("text-caption text-grey-6")
                            if arg["kind"] == "path" and arg["flag"] == "--budget":
                                budget_widget = fields[arg["flag"]]
                                hint = ui.label(_time_hint_text(budget_widget.value)).classes(
                                    "text-caption text-grey-5"
                                )

                                def _update_hint(
                                    _change: Any,
                                    budget_widget: Any = budget_widget,
                                    hint: Any = hint,
                                ) -> None:
                                    hint.set_text(_time_hint_text(budget_widget.value))

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
    try:
        record = runner.launch(name, values)
    except ValueError as exc:
        output.push(f"ERRO: {exc}")
        return
    output.push(f"lançado {record['job_id']} → PID {record['pid']}: {' '.join(record['cmd'])}")


def _launch_page() -> None:
    with page_shell("/launch"):
        ui.label("Disparar comando").classes("text-h5")
        ui.label(
            "Todos os comandos do cli.py, agrupados por função. O dashboard nunca "
            "inventa flags: o formulário é gerado do mesmo schema verificado por "
            "teste contra o argparse do cli.py. O tempo estimado junto ao campo "
            "--budget vem da medição REAL desta máquina "
            "(results/hardware_benchmark.json)."
        ).classes("text-caption text-grey-6")
        output = ui.log(max_lines=100).classes("w-full h-24")
        grouped: dict[str, list[dict[str, Any]]] = {}
        for cmd in commands.COMMANDS:
            grouped.setdefault(str(cmd.get("group") or "Outros"), []).append(cmd)
        group_order = _GROUP_ORDER + tuple(g for g in grouped if g not in _GROUP_ORDER)
        for group in group_order:
            cmds = grouped.get(group)
            if not cmds:
                continue
            meta = _GROUP_META.get(group, {"label": group, "caption": ""})
            with ui.expansion(
                f"{meta['label']} ({len(cmds)})", caption=meta["caption"], icon="folder"
            ).classes("w-full"):
                for cmd in cmds:
                    with ui.expansion(
                        cmd["name"],
                        caption=str(cmd.get("description") or ""),
                        icon="chevron_right",
                    ).classes("w-full"):
                        _launch_form(cmd, output)


# ---------------------------------------------------------------------------
# Página: /jobs
# ---------------------------------------------------------------------------


def _jobs_page() -> None:
    with page_shell("/jobs"):
        ui.label("Jobs lançados pelo dashboard").classes("text-h5")
        ui.label(
            "Processos desacoplados: seguem rodando mesmo se você fechar esta "
            "página (ou o dashboard). Clique numa linha para ver a cauda do log."
        ).classes("text-caption text-grey-6")
        rows = []
        for record in runner.list_jobs():
            polled = runner.poll(record["job_id"])
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


# ---------------------------------------------------------------------------
# Rotas + main
# ---------------------------------------------------------------------------


@ui.page("/")
def index() -> None:
    _index_page()


@ui.page("/run/{run_id}")
def run_detail(run_id: str) -> None:
    _detail_page(run_id)


@ui.page("/launch")
def launch_page() -> None:
    _launch_page()


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
