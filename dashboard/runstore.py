"""Leitura read-only dos artefatos canônicos de `runs/`.

O pipeline (`planet9lab/run.py`) é o dono de cada arquivo da run; este
módulo apenas lê. Pastas canônicas (Tarefa D, escopo 4): `results/`,
`audit/`, `diagnostics/` e `status.json` na raiz da run. Duplicatas na
raiz (ex.: `blockers.json`, `ranking.csv`) são evitadas — usadas só como
fallback quando o arquivo canônico não existe (runs antigas).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MARKERS = ("SUCCESS.marker", "INVALID.marker", "FAILED.marker")

_STATUS_FALLBACK_BY_MARKER = {
    "SUCCESS.marker": "completed",
    "INVALID.marker": "invalid",
    "FAILED.marker": "failed",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_status(run_dir: Path) -> dict[str, Any]:
    data = read_json(Path(run_dir) / "status.json")
    return data if isinstance(data, dict) else {}


def load_heartbeat(run_dir: Path) -> dict[str, Any]:
    data = read_json(Path(run_dir) / "heartbeat.json")
    return data if isinstance(data, dict) else {}


def load_blockers(run_dir: Path) -> list[dict[str, Any]]:
    """Blockers do arquivo canônico `audit/blockers.json` (fallback: raiz)."""
    run_dir = Path(run_dir)
    for candidate in (run_dir / "audit" / "blockers.json", run_dir / "blockers.json"):
        data = read_json(candidate)
        if isinstance(data, dict) and isinstance(data.get("blockers"), list):
            return data["blockers"]
    return []


def find_marker(run_dir: Path) -> str | None:
    run_dir = Path(run_dir)
    return next((marker for marker in MARKERS if (run_dir / marker).exists()), None)


def lifecycle_status(run_dir: Path) -> str:
    """Status efetivo: RUNNING.lock sem marcador => running; senão status.json."""
    run_dir = Path(run_dir)
    status = load_status(run_dir)
    marker = find_marker(run_dir)
    if (run_dir / "RUNNING.lock").exists() and marker is None:
        return "running"
    if status.get("status"):
        return str(status["status"])
    return _STATUS_FALLBACK_BY_MARKER.get(marker or "", "unknown")


def candidate_progress(run_dir: Path) -> dict[str, Any]:
    """Progresso persistido pelo pipeline: status.json; fallback heartbeat.

    Chaves: candidates_done / candidates_total / candidates_failed /
    current_stage, além de `source` indicando o arquivo lido.
    """
    run_dir = Path(run_dir)
    for source_name, data in (("status.json", load_status(run_dir)), ("heartbeat.json", load_heartbeat(run_dir))):
        if data.get("candidates_total") is not None:
            result = dict(data)
            result["source"] = source_name
            return result
    return {"candidates_done": 0, "candidates_total": 0, "current_stage": "?", "source": "nenhum"}


def checkpoint_info(run_dir: Path) -> dict[str, Any]:
    """Resumo das pastas de checkpoint do pipeline.

    Duas pastas canônicas existem: `checkpoints/` (integração checkpointed)
    e `montecarlo_checkpoints/` (estágio secular do Monte Carlo, ver
    planet9lab/montecarlo.py e scripts/watch_progress.py).
    """
    run_dir = Path(run_dir)
    found: dict[str, dict[str, Any]] = {}
    for name in ("checkpoints", "montecarlo_checkpoints"):
        checkpoint_dir = run_dir / name
        if not checkpoint_dir.is_dir():
            continue
        files = [item for item in checkpoint_dir.iterdir() if item.is_file()]
        if not files:
            continue
        found[name] = {
            "n_files": len(files),
            "latest_mtime": max(item.stat().st_mtime for item in files),
        }
    if not found:
        return {"present": False, "n_files": 0, "latest_mtime": None, "dirs": {}}
    return {
        "present": True,
        "n_files": sum(info["n_files"] for info in found.values()),
        "latest_mtime": max(info["latest_mtime"] for info in found.values()),
        "dirs": found,
    }


def _read_yaml(path: Path) -> dict[str, Any]:
    """Leitura tolerante de YAML da run (config.resolved.yaml); {} se ausente."""
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ImportError):
        return {}
    return data if isinstance(data, dict) else {}


def progress_info(run_dir: Path) -> dict[str, Any]:
    """Progresso de uma run em andamento, derivado dos mesmos arquivos que
    scripts/watch_progress.py lê (status.json, heartbeat.json,
    config.resolved.yaml e as séries de drift em checkpoints/ e
    montecarlo_checkpoints/).

    A porcentagem por série é uma ESTIMATIVA (taxa média desde a criação do
    arquivo), não uma figura exata — mesma ressalva do watch_progress.py.
    Esta função é read-only e nunca escreve na pasta da run.
    """
    import csv as _csv
    import time as _time

    run_dir = Path(run_dir)
    status = read_json(run_dir / "status.json")
    heartbeat = read_json(run_dir / "heartbeat.json")
    config = _read_yaml(run_dir / "config.resolved.yaml")
    integration_years = (config.get("budget", {}) or {}).get("integration_years")

    series: list[dict[str, Any]] = []
    now = _time.time()
    for checkpoint_dir in (run_dir / "checkpoints", run_dir / "montecarlo_checkpoints"):
        if not checkpoint_dir.is_dir():
            continue
        for series_path in sorted(checkpoint_dir.glob("*_drift_series.csv")):
            try:
                with series_path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(_csv.DictReader(handle))
            except OSError:
                continue
            if not rows:
                continue
            try:
                t_years = float(rows[-1]["t_years"])
            except (KeyError, TypeError, ValueError):
                t_years = None
            age_s = now - series_path.stat().st_mtime
            pct = (
                t_years / integration_years * 100.0
                if integration_years and t_years is not None
                else None
            )
            series.append({"name": series_path.name.replace("_drift_series.csv", ""), "t_years": t_years, "pct": pct, "age_s": age_s})

    done, total = status.get("candidates_done"), status.get("candidates_total")
    candidate_fraction = done / total if isinstance(done, (int, float)) and isinstance(total, (int, float)) and total else None
    heartbeat_path = run_dir / "heartbeat.json"
    heartbeat_age_s = (
        now - heartbeat_path.stat().st_mtime if heartbeat_path.is_file() else None
    )
    return {
        "status": status.get("status"),
        "current_stage": status.get("current_stage"),
        "candidates_done": done,
        "candidates_total": total,
        "candidates_failed": status.get("candidates_failed"),
        "candidate_fraction": candidate_fraction,
        "heartbeat_age_s": heartbeat_age_s,
        "heartbeat_present": bool(heartbeat),
        "integration_years": integration_years,
        "series": series,
        "max_series_pct": max((s["pct"] for s in series if s["pct"] is not None), default=None),
    }


def list_runs(run_root: Path) -> list[dict[str, Any]]:
    """Lista runs passadas e em andamento, ordenadas por run_id desc."""
    run_root = Path(run_root)
    runs: list[dict[str, Any]] = []
    if not run_root.is_dir():
        return runs
    for child in run_root.iterdir():
        if not child.is_dir():
            continue
        has_status = (child / "status.json").exists()
        has_audit = (child / "audit" / "run_manifest.json").exists()
        has_marker = find_marker(child) is not None
        if not (has_status or has_audit or has_marker):
            continue  # pasta que não é uma run
        status = load_status(child)
        runs.append(
            {
                "run_id": child.name,
                "path": str(child),
                "status": lifecycle_status(child),
                "marker": find_marker(child),
                "started_at": status.get("started_at"),
                "ended_at": status.get("ended_at"),
                "global_result_status": status.get("global_result_status"),
                "current_stage": status.get("current_stage"),
                "candidates_done": status.get("candidates_done"),
                "candidates_total": status.get("candidates_total"),
                "candidates_failed": status.get("candidates_failed"),
                "blockers": load_blockers(child),
                "has_running_lock": (child / "RUNNING.lock").exists(),
            }
        )
    return sorted(runs, key=lambda info: info["run_id"], reverse=True)


def resolve_run(run_root: Path, run_id: str) -> Path | None:
    candidate = Path(run_root) / run_id
    if candidate.is_dir():
        return candidate
    return None
