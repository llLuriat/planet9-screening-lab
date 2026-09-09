"""Aplicação NiceGUI do dashboard (Tarefa D) — bind EXCLUSIVO em localhost.

Restrições da tarefa respeitadas aqui:
- servidor apenas em ``HOST`` = 127.0.0.1 (nunca 0.0.0.0/rede);
- NUNCA altera ``cli.py``/``planet9lab/``: só chama os comandos existentes
  via ``dashboard.runner`` (Popen detached — runs longas sobrevivem ao
  fechamento da UI; Abordagem A travada por teste);
- números/textos exibidos vêm dos artefatos via ``runstore``/``report``
  (caveats/interpretation verbatim, contrato do ``report.py``).

Decisões do Executor (registradas no Log): formulário gerado do schema
curado ``dashboard/commands.py`` (23 subcomandos, ``watch`` bloqueado);
campos de run são texto livre validado pelo runner (sem depender de APIs
dinâmicas do NiceGUI); páginas: ``/`` (runs), ``/run/{id}`` (relatório +
progresso com auto-refresh), ``/launch`` (disparo), ``/jobs`` (jobs).
"""
from __future__ import annotations

import html
import logging
from typing import Any

from nicegui import ui

from dashboard import __version__, commands, report, runner, runstore
from dashboard.config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_RUN_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dashboard")

HOST = DEFAULT_HOST  # 127.0.0.1 — nunca 0.0.0.0 (regra não negociável)
PORT = DEFAULT_PORT
RUN_ROOT = DEFAULT_RUN_ROOT


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

_BADGE_COLOR = {
    "completed": "positive",
    "running": "info",
    "failed": "negative",
    "invalid": "warning",
    "unknown": "grey",
}


def _badge(status: Any) -> None:
    text = str(status) if status else "unknown"
    ui.badge(text, color=_BADGE_COLOR.get(text, "grey"))


def _run_ids() -> list[str]:
    return [info["run_id"] for info in runstore.list_runs(RUN_ROOT)]


def _index_page() -> None:
    ui.label("Planet9 Screening Lab — Dashboard").classes("text-h5")
    ui.label("Triagem exploratória; nada aqui confirma nem descarta candidato (ver LIMITACOES.md).").classes(
        "text-caption"
    )
    runs = runstore.list_runs(RUN_ROOT)
    if not runs:
        ui.label("Nenhuma run encontrada em runs/.")
        return
    columns = [
        {"name": "run_id", "label": "run_id", "field": "run_id", "align": "left"},
        {"name": "status", "label": "status", "field": "status"},
        {"name": "global_result_status", "label": "resultado global", "field": "global_result_status"},
        {"name": "started_at", "label": "início", "field": "started_at"},
        {"name": "ended_at", "label": "fim", "field": "ended_at"},
        {"name": "blockers", "label": "blockers", "field": "n_blockers"},
    ]
    rows = [
        {
            "run_id": info["run_id"],
            "status": info["status"],
            "global_result_status": info.get("global_result_status") or "—",
            "started_at": info.get("started_at") or "—",
            "ended_at": info.get("ended_at") or "—",
            "n_blockers": len(info.get("blockers") or []),
        }
        for info in runs
    ]
    table = ui.table(columns=columns, rows=rows, row_key="run_id").classes("w-full")
    table.on("rowClick", lambda e: ui.navigate.to(f"/run/{e.args[1]['run_id']}"))
    for info in runs:
        if info.get("blockers"):
            ui.label(f"{info['run_id']}: {len(info['blockers'])} blocker(s) ativo(s)").classes(
                "text-warning text-caption"
            )


def _detail_page(run_id: str) -> None:
    run_dir = runstore.resolve_run(RUN_ROOT, run_id)
    ui.label(f"Run: {run_id}").classes("text-h5")
    if run_dir is None:
        ui.label("Run não encontrada.").classes("text-negative")
        return
    ui.link("← voltar", "/")
    progress = runstore.candidate_progress(run_dir)
    total = progress.get("candidates_total") or 0
    done = progress.get("candidates_done") or 0
    frac = (done / total) if isinstance(total, (int, float)) and total else 0.0
    with ui.row().classes("items-center gap-4"):
        _badge(runstore.lifecycle_status(run_dir))
        ui.label(f"candidatos: {done}/{total} (fonte: {progress.get('source', '?')})")
    bar = ui.linear_progress(value=frac).classes("w-full")
    checkpoints = runstore.checkpoint_info(run_dir)
    if checkpoints.get("present"):
        ui.label(
            f"checkpoints: {checkpoints['n_files']} arquivo(s) "
            f"(pastas: {', '.join(checkpoints['dirs'])})"
        ).classes("text-caption")
    blockers = runstore.load_blockers(run_dir)
    if blockers:
        with ui.card().style("background: #4a1d1d"):
            ui.label("Blockers ativos").classes("text-bold")
            for blocker in blockers:
                ui.label(str(blocker.get("blocker_id", "?"))).classes("text-caption")
    ui.html(report.render_run_report(run_dir)).classes("w-full")

    def refresh() -> None:
        p = runstore.candidate_progress(run_dir)
        t = p.get("candidates_total") or 0
        d = p.get("candidates_done") or 0
        bar.set_value((d / t) if isinstance(t, (int, float)) and t else 0.0)

    ui.timer(5.0, refresh)


def _launch_page() -> None:
    ui.label("Disparar comando do cli.py").classes("text-h5")
    ui.label(
        "Cada comando roda como processo desacoplado (python main.py …) e "
        "sobrevive ao fechamento desta página/navegador. Logs em .dashboard/jobs/."
    ).classes("text-caption")
    launchable = [name for name in commands.COMMAND_NAMES if name not in commands.BLOCKED_COMMANDS]
    form_container = ui.column().classes("w-full max-w-3xl")
    output = ui.log(max_lines=40).classes("w-full h-40")

    def _rebuild_form(name: str) -> None:
        form_container.clear()
        with form_container:
            _command_form(name, output)

    select = ui.select(
        {name: name for name in launchable},
        label="subcomando",
        value="smoke",
        on_change=lambda e: _rebuild_form(e.value),
    ).classes("w-64")
    ui.link("Ver jobs lançados", "/jobs")
    _rebuild_form(select.value)


def _command_form(name: str, output: ui.log) -> None:
    cmd = commands.get_command(name)
    ui.label(cmd["description"]).classes("text-caption")
    inputs: dict[str, Any] = {}
    with ui.grid(columns=2).classes("w-full gap-2"):
        for arg in cmd["args"]:
            label = arg["flag"] + (" *" if arg.get("required") else "")
            kind = arg["kind"]
            default = arg.get("default")
            if kind == "flag":
                inputs[arg["flag"]] = ui.checkbox(label, value=False)
            elif kind == "int":
                inputs[arg["flag"]] = ui.number(label, value=default, format="%.0f").classes("w-full")
            elif kind == "float":
                inputs[arg["flag"]] = ui.number(label, value=default).classes("w-full")
            else:
                initial = "" if default is None else str(default)
                inputs[arg["flag"]] = ui.input(label, value=initial).classes("w-full")

    def _do_launch() -> None:
        values: dict[str, Any] = {}
        for flag, widget in inputs.items():
            value = getattr(widget, "value", None)
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    value = None
            values[flag] = value
        try:
            record = runner.launch(name, values)
        except ValueError as exc:
            output.push(f"ERRO: {exc}")
            return
        output.push(f"lançado {record['job_id']} → PID {record['pid']}: {' '.join(record['cmd'])}")

    with ui.row().classes("items-center gap-4"):
        ui.button(f"Executar {name}", on_click=_do_launch)
        ui.label("Valida o formulário e lança o processo; acompanhe em /jobs.").classes("text-caption")


def _jobs_page() -> None:
    ui.label("Jobs lançados pelo dashboard").classes("text-h5")
    ui.link("← voltar", "/")
    rows = []
    for record in runner.list_jobs():
        polled = runner.poll(record["job_id"])
        rows.append(
            {
                "job_id": polled["job_id"],
                "command": polled["command"],
                "pid": polled["pid"],
                "launched_at": polled.get("launched_at", ""),
                "finished": "sim" if polled.get("finished") else "não",
            }
        )
    if not rows:
        ui.label("Nenhum job lançado ainda.")
        return
    columns = [
        {"name": "job_id", "label": "job_id", "field": "job_id", "align": "left"},
        {"name": "command", "label": "comando", "field": "command"},
        {"name": "pid", "label": "PID", "field": "pid"},
        {"name": "launched_at", "label": "lançado em", "field": "launched_at"},
        {"name": "finished", "label": "terminou?", "field": "finished"},
    ]
    table = ui.table(columns=columns, rows=rows, row_key="job_id").classes("w-full")
    log_container = ui.column().classes("w-full")

    def _show_log(e: Any) -> None:
        job_id = e.args[1]["job_id"]
        log_container.clear()
        with log_container, ui.card().classes("w-full"):
            ui.html(f"<pre style='white-space:pre-wrap;margin:0'>{html.escape(runner.tail(job_id))}</pre>")

    table.on("rowClick", _show_log)
    ui.label("Clique numa linha para ver a cauda do log do job.").classes("text-caption")


def _header() -> None:
    with ui.row().classes("w-full items-center gap-4 q-pa-sm"):
        ui.link("Runs", "/")
        ui.link("Disparar", "/launch")
        ui.link("Jobs", "/jobs")
        ui.label(f"v{__version__} — bind 127.0.0.1 apenas; leitura de artefatos canônicos").classes(
            "text-caption text-grey"
        )


@ui.page("/")
def index() -> None:
    _header()
    _index_page()


@ui.page("/run/{run_id}")
def run_detail(run_id: str) -> None:
    _header()
    _detail_page(run_id)


@ui.page("/launch")
def launch_page() -> None:
    _header()
    _launch_page()


@ui.page("/jobs")
def jobs_page() -> None:
    _header()
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
