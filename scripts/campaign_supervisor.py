"""Supervisor da campanha de simulações (48 h, usuário ausente — 2026-09-25).

Lê ``scripts/campaign_jobs.json`` a CADA iteração (permite podar/reordenar a
fila ao vivo sem reiniciar o supervisor), executa os jobs em sequência e grava
estado em ``runs/campaign_supervisor/progress.json`` + um log por job.
Falha de um job é isolada: sai como "failed" e a fila segue. O job de screen
longo tem um retry via ``resume`` — seguro desde a correção do B3 (manifesto
reconstruído + checkpoints REBOUND).

Mantém o sistema acordado enquanto vivo (SetThreadExecutionState
ES_CONTINUOUS|ES_SYSTEM_REQUIRED — não exige admin; sono/idle são bloqueados,
display pode apagar).

Uso (em background):
    Start-Process -FilePath .venv\\Scripts\\python.exe `
        -ArgumentList scripts\\campaign_supervisor.py `
        -WorkingDirectory <raiz-do-repo> -WindowStyle Hidden `
        -RedirectStandardOutput runs\\campaign_supervisor\\supervisor_out.log `
        -RedirectStandardError  runs\\campaign_supervisor\\supervisor_err.log
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_FILE = ROOT / "scripts" / "campaign_jobs.json"
OUT = ROOT / "runs" / "campaign_supervisor"


def _keep_awake() -> None:
    try:
        import ctypes

        es_continuous = 0x80000000
        es_system_required = 0x1
        ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)
    except (AttributeError, OSError):
        pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_progress(progress: dict) -> None:
    (OUT / "progress.json").write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")


def _resolve(cmd: list[str], py: str) -> list[str]:
    resolved: list[str] = []
    for token in cmd:
        if token == "{py}":
            resolved.append(py)
        elif token == "{latest_run}":
            latest = (ROOT / "runs" / "latest_run.txt").read_text(encoding="utf-8").strip()
            resolved.append(latest)
        else:
            resolved.append(token)
    return resolved


def _run_job(cmd: list[str], log_path: Path, timeout_s: int) -> int:
    """Roda um job com stdout+stderr no log; no timeout mata a árvore inteira."""
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== {_now()} CMD: {' '.join(cmd)}\n")
        log.flush()
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            return proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            log.write(f"\n=== {_now()} TIMEOUT after {timeout_s}s — arvore de processos morta.\n")
            return 124


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    _keep_awake()
    py = sys.executable
    state_path = OUT / "progress.json"
    progress: dict = {"campaign_dir": str(OUT), "started_at": _now(), "updated_at": _now(), "jobs": {}}
    if state_path.exists():
        try:
            progress = json.loads(state_path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    # Idempotente: "done" e "failed" não são reexecutados num relançamento.
    done = {name for name, rec in progress.get("jobs", {}).items() if rec.get("status") in {"done", "failed"}}

    while True:
        spec = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        pending = [job for job in spec["jobs"] if job["name"] not in done]
        if not pending:
            break
        job = pending[0]
        name = job["name"]
        attempts = [("primary", job["cmd"], job["timeout_s"])]
        if job.get("retry_cmd"):
            attempts.append(("retry_resume", job["retry_cmd"], job.get("retry_timeout_s", job["timeout_s"])))
        for kind, cmd_raw, timeout_s in attempts:
            cmd = _resolve(cmd_raw, py)
            started = _now()
            t0 = time.time()
            progress["jobs"][name] = {"status": "running", "attempt": kind, "started": started, "cmd": cmd}
            progress["updated_at"] = _now()
            _write_progress(progress)
            code = _run_job(cmd, OUT / f"{name}.log", timeout_s)
            record = {
                "status": "done" if code == 0 else "failed",
                "attempt": kind,
                "started": started,
                "ended": _now(),
                "duration_s": round(time.time() - t0, 1),
                "exit_code": code,
            }
            progress["jobs"][name] = record
            progress["updated_at"] = _now()
            _write_progress(progress)
            if code == 0 or kind != "primary":
                break
        done.add(name)

    progress["finished_at"] = _now()
    progress["updated_at"] = _now()
    _write_progress(progress)
    (OUT / "DONE.marker").write_text(_now() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
