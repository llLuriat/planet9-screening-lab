"""Launcher de jobs desacoplados do processo da UI (requisito runs longas).

Abordagem A (implementada e travada por teste): ``subprocess.Popen`` com
``CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB``
(Windows) — o filho não pertence ao job object/console do servidor
NiceGUI e sobrevive ao fechamento do servidor e da aba. stdout/stderr vão
para ``.dashboard/jobs/<id>.log`` (gitignored). Abordagem B (fallback
planejado, ``Start-Process``/PowerShell -WindowStyle Hidden) não foi
necessária enquanto a A funcionar — reativar só se a A falhar.

Limitações declaradas: (1) exit code de processo detached não é
capturável após o fato — o poll marca `finished` quando o PID desaparece
e o resultado científico é julgado pelos artefatos da run, nunca pelo
exit code; (2) PID pode ser reutilizado pelo SO entre polls — mitigação
fora do escopo do uso local.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard import config
from dashboard.commands import BLOCKED_COMMANDS, COMMAND_NAMES, build_argv, validate

if sys.platform == "win32":
    DETACHED_FLAGS = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_BREAKAWAY_FROM_JOB
    )
else:  # pragma: no cover - ambiente de teste pode não ser Windows
    DETACHED_FLAGS = 0


def _popen_detached(cmd: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
    """Popen desacoplado, com fallback se breakaway for negado pelo job."""
    if sys.platform != "win32":
        return subprocess.Popen(cmd, start_new_session=True, **kwargs)  # type: ignore[arg-type]
    try:
        return subprocess.Popen(cmd, creationflags=DETACHED_FLAGS, **kwargs)
    except OSError:
        # job object do pai pode negar CREATE_BREAKAWAY_FROM_JOB; tente sem.
        flags = DETACHED_FLAGS & ~subprocess.CREATE_BREAKAWAY_FROM_JOB
        return subprocess.Popen(cmd, creationflags=flags, **kwargs)


def launch(command_name: str, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Lança ``python -m planet9lab.cli <comando> <argv>`` desacoplado.

    Duplo guardião: o comando precisa estar no schema curado (commands.py)
    E fora de BLOCKED_COMMANDS. Retorna o record do job.
    """
    if command_name in BLOCKED_COMMANDS or command_name not in COMMAND_NAMES:
        raise ValueError(f"comando não permitido pelo dashboard: {command_name!r}")
    values = dict(values or {})
    problems = validate(command_name, values)
    if problems:
        raise ValueError("; ".join(problems))
    config.ensure_state_dirs()
    job_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    log_path = config.JOBS_DIR / f"{job_id}.log"
    argv = build_argv(command_name, values)
    # Entrypoint do projeto é `python main.py <comando>` (main.py é quem
    # chama planet9lab.cli.main; `-m planet9lab.cli` NÃO executa — cli.py
    # não tem guarda __main__). Mesma convenção dos replay_command.txt.
    cmd = [sys.executable, "main.py", command_name, *argv]
    with log_path.open("wb") as log_file:
        proc = _popen_detached(
            cmd,
            cwd=str(config.REPO_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
    record = {
        "job_id": job_id,
        "command": command_name,
        "argv": argv,
        "cmd": cmd,
        "pid": proc.pid,
        "log_path": str(log_path),
        "launched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "finished": False,
        "exit_code": None,
    }
    (config.JOBS_DIR / f"{job_id}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


def read_job(job_id: str) -> dict[str, Any] | None:
    path = config.JOBS_DIR / f"{job_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_jobs() -> list[dict[str, Any]]:
    """Jobs mais recentes primeiro."""
    config.ensure_state_dirs()
    jobs = []
    for path in sorted(config.JOBS_DIR.glob("*.json"), reverse=True):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return jobs


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(  # noqa: S603 - argumentos fixos, sem shell
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        return str(pid) in out.split()
    try:  # pragma: no cover - não-Windows
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except ImportError:  # pragma: no cover
        return False


def poll(job_id: str) -> dict[str, Any]:
    """Atualiza o record se o processo já terminou (PID desapareceu)."""
    record = read_job(job_id)
    if record is None:
        raise FileNotFoundError(job_id)
    if record.get("finished"):
        return record
    if not pid_alive(int(record["pid"])):
        record["finished"] = True
        record["note"] = (
            "processo finalizado (exit code não capturável em lançamento "
            "detached; julgar pelos artefatos da run e pelo log do job)"
        )
        (config.JOBS_DIR / f"{job_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return record


def tail(job_id: str, limit: int = 4000) -> str:
    """Cauda do log do job (utf-8 com reposição, tolerante a escrita concorrente)."""
    record = read_job(job_id)
    if record is None:
        return "(job não encontrado)"
    path = Path(record["log_path"])
    try:
        data = path.read_bytes()[-limit:]
    except OSError:
        return "(log ainda não criado)"
    return data.decode("utf-8", errors="replace")
