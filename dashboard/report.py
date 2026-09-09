"""Relatório HTML legível de uma run — números e textos VÊM DOS ARQUIVOS.

Contrato científico (Tarefa D, não negociável, travado por teste em
``tests/test_dashboard.py``):
- todo campo ``caveats``/``interpretation`` dos JSONs de diagnóstico
  aparece NA ÍNTEGRA no HTML (substring exata após escape — sem
  paráfrase, resumo ou corte), marcado com ``data-verbatim``;
- além dos blocos destacados, CADA JSON canônico é embutido inteiro num
  ``<pre data-verbatim="arquivo">`` — a cópia textual do artefato está
  sempre visível junto dos números;
- nenhum número é recalculado ou aproximado na camada de UI: ranking,
  métricas e stats vêm diretamente de ``results/``, ``audit/``,
  ``diagnostics/`` e ``status.json`` (raiz da run). Duplicatas na raiz
  de run antiga só são usadas como fallback pelo runstore.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

from dashboard import runstore

_MAX_TABLE_ROWS = 50

_CSS = (
    "body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #ddd; background: #14181f; } "
    "h1 { font-size: 1.4rem; } h2 { font-size: 1.15rem; margin-top: 1.6rem; "
    "border-bottom: 1px solid #3a4150; padding-bottom: .2rem; } "
    "table { border-collapse: collapse; margin: .5rem 0; font-size: .85rem; } "
    "th, td { border: 1px solid #3a4150; padding: .15rem .5rem; text-align: left; } "
    "th { background: #232a36; } "
    "pre.verbatim { background: #0d1117; border: 1px solid #3a4150; padding: .6rem; "
    "overflow-x: auto; font-size: .78rem; white-space: pre-wrap; } "
    "p.verbatim { background: #1d2430; border-left: 3px solid #7a9cc6; padding: .4rem .6rem; } "
    ".badge { display: inline-block; padding: .1rem .55rem; border-radius: .6rem; "
    "font-size: .8rem; font-weight: 600; } "
    ".badge.completed { background: #1d4023; color: #7ce38b; } "
    ".badge.running { background: #173a52; color: #7cc6ff; } "
    ".badge.failed { background: #4a1d1d; color: #ff8181; } "
    ".badge.invalid { background: #4a3d1d; color: #ffd479; } "
    ".badge.unknown { background: #333a45; color: #ccc; } "
    ".blockers { background: #4a1d1d; border: 1px solid #ff8181; padding: .5rem .8rem; "
    "border-radius: .3rem; } "
    ".muted { color: #8b93a3; font-size: .8rem; }"
)


def _dumps(data: Any) -> str:
    """Serialização canônica: a mesma usada no <pre> verbatim e nos testes."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def _pre(source: str, text: str) -> str:
    return (
        f'<pre class="verbatim" data-verbatim="{html.escape(source, quote=True)}">'
        f"{html.escape(text)}</pre>"
    )


def _verbatim_block(source: str, text: str) -> str:
    return (
        f'<p class="verbatim" data-verbatim="{html.escape(source, quote=True)}">'
        f"{html.escape(text)}</p>"
    )


def _badge(status: str) -> str:
    return f'<span class="badge {html.escape(status)}">{html.escape(status)}</span>'


def _section_status(run_dir: Path) -> str:
    status = runstore.lifecycle_status(run_dir)
    raw_status = runstore.load_status(run_dir)
    parts = [f"<p>status: {_badge(status)}</p>"]
    if raw_status:
        parts.append(_pre("status.json", _dumps(raw_status)))
    else:
        parts.append("<p class='muted'>status.json ausente.</p>")
    return "".join(parts)


def _section_blockers(run_dir: Path) -> str:
    blockers = runstore.load_blockers(run_dir)
    if not blockers:
        return "<p class='muted'>Nenhum blocker ativo (audit/blockers.json vazio ou ausente).</p>"
    parts = ["<div class='blockers'><strong>Blockers ativos</strong>"]
    for i, blocker in enumerate(blockers):
        if not isinstance(blocker, dict):
            continue
        text = " | ".join(
            f"{key}: {blocker[key]}" for key in ("blocker_id", "severity", "message") if key in blocker
        )
        parts.append(_verbatim_block(f"audit/blockers.json#blockers[{i}]", text))
    parts.append(_pre("audit/blockers.json", _dumps({"blockers": blockers})))
    parts.append("</div>")
    return "".join(parts)


def _section_progress(run_dir: Path) -> str:
    progress = runstore.candidate_progress(run_dir)
    checkpoints = runstore.checkpoint_info(run_dir)
    parts = [
        "<p>Progresso de candidatos (fonte: "
        f"{html.escape(str(progress.get('source', '?')))}): "
        f"{progress.get('candidates_done', 0)}/{progress.get('candidates_total', 0)} "
        f"(falhas: {progress.get('candidates_failed', 0)}; estágio: "
        f"{html.escape(str(progress.get('current_stage', '?')))})</p>",
        _pre("candidate_progress", _dumps(progress)),
    ]
    if checkpoints.get("present"):
        parts.append(_pre("checkpoints", _dumps(checkpoints)))
    else:
        parts.append("<p class='muted'>Sem checkpoints/ nem montecarlo_checkpoints/.</p>")
    return "".join(parts)


def _csv_table(path: Path, source: str) -> str:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except (OSError, csv.Error):
        return f"<p class='muted'>Não foi possível ler {html.escape(source)}.</p>"
    if not rows:
        return f"<p class='muted'>{html.escape(source)} vazio.</p>"
    header, body = rows[0], rows[1:]
    shown = body[:_MAX_TABLE_ROWS]
    parts = ["<table><tr>" + "".join(f"<th>{html.escape(cell)}</th>" for cell in header) + "</tr>"]
    for row in shown:
        parts.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>")
    parts.append("</table>")
    if len(body) > len(shown):
        parts.append(
            f"<p class='muted'>Exibindo {len(shown)} de {len(body)} linhas; "
            "a íntegra está no arquivo canônico.</p>"
        )
    return "".join(parts)


def _section_results(run_dir: Path) -> str:
    results_dir = run_dir / "results"
    if not results_dir.is_dir():
        return "<p class='muted'>Sem results/ nesta run.</p>"
    parts: list[str] = []
    for name in ("ranking.csv", "metrics_by_candidate.csv"):
        path = results_dir / name
        if path.is_file():
            parts.append(f"<h3>{name}</h3>{_csv_table(path, f'results/{name}')}")
    others = sorted(p.name for p in results_dir.iterdir() if p.is_file())
    skipped = [n for n in others if n not in ("ranking.csv", "metrics_by_candidate.csv")]
    if skipped:
        parts.append(f"<p class='muted'>Outros arquivos em results/: {html.escape(', '.join(skipped))}</p>")
    if not parts:
        return "<p class='muted'>results/ sem ranking.csv nem metrics_by_candidate.csv.</p>"
    return "".join(parts)


def _section_diagnostics(run_dir: Path) -> str:
    diag_dir = run_dir / "diagnostics"
    if not diag_dir.is_dir():
        return "<p class='muted'>Sem diagnostics/ nesta run.</p>"
    files = sorted(diag_dir.glob("*.json"))
    if not files:
        return "<p class='muted'>diagnostics/ sem arquivos .json.</p>"
    parts: list[str] = []
    for path in files:
        source = f"diagnostics/{path.name}"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parts.append(f"<h3>{html.escape(source)}</h3><p class='muted'>JSON inválido: {html.escape(str(exc))}</p>")
            continue
        parts.append(f"<h3>{html.escape(source)}</h3>")
        if isinstance(data, dict):
            caveats = data.get("caveats")
            if isinstance(caveats, list):
                for i, caveat in enumerate(caveats):
                    if isinstance(caveat, str):
                        parts.append(_verbatim_block(f"{source}#caveats[{i}]", caveat))
            interpretation = data.get("interpretation")
            if isinstance(interpretation, str):
                parts.append(_verbatim_block(f"{source}#interpretation", interpretation))
        # Contrato: o JSON inteiro, texto canônico, embutido verbatim.
        parts.append(_pre(source, _dumps(data)))
    return "".join(parts)


def render_run_report(run_dir: Path) -> str:
    """HTML completo do relatório de uma run (uma string; nada é escrito)."""
    run_dir = Path(run_dir)
    sections = [
        ("Status", _section_status(run_dir)),
        ("Blockers", _section_blockers(run_dir)),
        ("Progresso", _section_progress(run_dir)),
        ("Resultados", _section_results(run_dir)),
        ("Diagnósticos", _section_diagnostics(run_dir)),
    ]
    body = "".join(f"<h2>{title}</h2>{content}" for title, content in sections)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Run {html.escape(run_dir.name)}</title><style>{_CSS}</style></head><body>"
        f"<h1>Run: {html.escape(run_dir.name)}</h1>"
        f"<p class='muted'>Relatório gerado pelo dashboard a partir dos artefatos "
        "canônicos; caveats/interpretation e JSONs embutidos verbatim.</p>"
        f"{body}</body></html>"
    )
