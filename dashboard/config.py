"""Caminhos do estado local do dashboard e defaults do servidor.

O estado próprio do dashboard (registros de jobs, logs de lançamento)
vive em `.dashboard/` na raiz do repositório — gitignored no mesmo commit
do código (regra da Tarefa D: nenhum arquivo solto não-rastreado).
O dashboard nunca escreve dentro de `runs/` (artefatos do pipeline).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".dashboard"
JOBS_DIR = STATE_DIR / "jobs"
LAUNCH_LOG_DIR = STATE_DIR / "launch_logs"

# Servidor exclusivamente local — nunca 0.0.0.0 nem exposto na rede.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RUN_ROOT = REPO_ROOT / "runs"


def ensure_state_dirs() -> None:
    """Cria os diretórios de estado local se ainda não existirem."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
