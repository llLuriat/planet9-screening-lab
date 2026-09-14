"""Caminhos do estado local do dashboard e defaults do servidor.

O estado próprio do dashboard (registros de jobs, logs de lançamento)
vive em `.dashboard/` na raiz do repositório — gitignored no mesmo commit
do código (regra da Tarefa D: nenhum arquivo solto não-rastreado).
O dashboard nunca escreve dentro de `runs/` (artefatos do pipeline).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".dashboard"
JOBS_DIR = STATE_DIR / "jobs"
LAUNCH_LOG_DIR = STATE_DIR / "launch_logs"
# Zips de artefatos montados sob demanda pelo botão "Baixar resultados" e
# backups do benchmark antes de sobrescrevê-lo (tudo em estado próprio do
# dashboard; o dashboard NUNCA escreve dentro de runs/ nem de results/).
DOWNLOADS_DIR = STATE_DIR / "downloads"
BACKUPS_DIR = STATE_DIR / "backups"

# Servidor exclusivamente local — nunca 0.0.0.0 nem exposto na rede.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_RUN_ROOT = REPO_ROOT / "runs"

# Variável de ambiente que redireciona o destino das runs. Existe para os
# testes (user simulation) apontarem o app para um diretório temporário sem
# tocar em `runs/` real do repositório. Em uso normal, fica ausente e vale
# DEFAULT_RUN_ROOT.
RUN_ROOT_ENV = "PLANET9_RUN_ROOT"


def run_root() -> Path:
    """Destino das runs lido A CADA CHAMADA (nunca capturado no import)."""
    override = os.environ.get(RUN_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_RUN_ROOT


def downloads_dir() -> Path:
    """Diretório dos zips gerados pelo botão de download."""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOADS_DIR


def backups_dir() -> Path:
    """Diretório dos backups do benchmark de hardware."""
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR


def ensure_state_dirs() -> None:
    """Cria os diretórios de estado local se ainda não existirem."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
