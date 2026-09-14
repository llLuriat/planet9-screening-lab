"""Empacotamento dos artefatos de uma run concluída para download (.zip).

Escolha documentada do conteúdo (autorizada pelo Auditor no redesign):

- ENTRA: status.json, config.resolved.yaml, environment.json,
  data_manifest.json, hashes.json, replay_command.txt, events.log,
  heartbeat.json, quaisquer ``*.marker`` da raiz, os diretórios
  ``results/``, ``audit/``, ``reports/``, ``presentation/`` e
  ``diagnostics/`` (quando existirem), ``relatorio.html`` (o MESMO HTML
  renderizado pela UI, via ``report.render_run_report``) e
  ``MANIFESTO.txt`` (o que entrou, o que ficou de fora e por quê).
- FICA DE FORA (documentado, nunca silencioso): ``checkpoints/`` e
  ``montecarlo_checkpoints/`` (checkpoints pesados de integração secular),
  ``candidates_results_cache.json`` (cache volátil de execução) e locks
  de execução (``RUNNING.lock``/``RUNNING.pid``).

O zip é um INVENTÁRIO de conveniência: os artefatos canônicos continuam
sendo os arquivos em ``runs/`` — nada aqui os move, apaga ou altera.
O arquivo é gravado no estado próprio do dashboard
(``config.downloads_dir()``); o dashboard nunca escreve dentro de runs/.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from dashboard import config, report

# Arquivos de raiz da run incluídos (presentes ou não, sem falhar).
INCLUDED_ROOT_FILES: tuple[str, ...] = (
    "status.json",
    "config.resolved.yaml",
    "environment.json",
    "data_manifest.json",
    "hashes.json",
    "replay_command.txt",
    "events.log",
    "heartbeat.json",
)

# Diretórios incluídos por inteiro (o que existir dentro deles entra).
INCLUDED_DIRS: tuple[str, ...] = (
    "results",
    "audit",
    "reports",
    "presentation",
    "diagnostics",
)

# Nomes que nunca entram, mesmo aparecendo nos diretórios incluídos.
EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        "candidates_results_cache.json",
        "RUNNING.lock",
        "RUNNING.pid",
    }
)

EXCLUDED_DIRS: frozenset[str] = frozenset({"checkpoints", "montecarlo_checkpoints"})

MANIFESTO_TEXT = """\
Planet9 Screening Lab — pacote de resultados de uma run concluída.

Este .zip é um INVENTÁRIO de conveniência gerado pelo dashboard; os
artefatos canônicos (fonte da verdade) continuam sendo os arquivos da
pasta da run em runs/ do repositório.

ENTRAM: {root_files}, os diretórios {dirs} (o que existir),
relatorio.html (o mesmo relatório renderizado pela UI) e este manifesto.

FICAM DE FORA (decisão documentada): checkpoints/ e
montecarlo_checkpoints/ (checkpoints pesados de integração secular),
candidates_results_cache.json (cache volátil de execução) e
RUNNING.lock/RUNNING.pid (locks de execução).

Vocabulário: os rótulos do relatório vêm VERBATIM dos artefatos
("triagem exploratória", "candidato de interesse dentro do protocolo",
"nenhum candidato encontrado", "inconclusivo") — nada é reescrito aqui.
"""


def _should_include(path: Path) -> bool:
    """Filtro único de inclusão (nomes e diretórios excluídos)."""
    parts = set(path.parts)
    if parts & EXCLUDED_DIRS:
        return False
    return path.name not in EXCLUDED_NAMES


def _collect_files(run_dir: Path) -> list[Path]:
    """Arquivos da run que entram no zip (ordem estável, sem falhar)."""
    files: list[Path] = []
    for name in INCLUDED_ROOT_FILES:
        path = run_dir / name
        if path.is_file():
            files.append(path)
    for marker in sorted(run_dir.glob("*.marker")):
        if marker.is_file() and _should_include(marker):
            files.append(marker)
    for dirname in INCLUDED_DIRS:
        directory = run_dir / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file() and _should_include(path.relative_to(run_dir)):
                files.append(path)
    return files


def build_results_zip(run_dir: Path, dest_dir: Path | None = None) -> Path:
    """Gera o .zip da run e retorna o caminho (sobrescreve se existir).

    Nunca lança por artefato ausente: inclui o que existir. O
    ``relatorio.html`` e o ``MANIFESTO.txt`` são gerados na hora.
    """
    run_dir = Path(run_dir)
    dest_dir = Path(dest_dir) if dest_dir is not None else config.downloads_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / f"{run_dir.name}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in _collect_files(run_dir):
            bundle.write(path, arcname=path.relative_to(run_dir).as_posix())
        bundle.writestr("relatorio.html", report.render_run_report(run_dir))
        bundle.writestr(
            "MANIFESTO.txt",
            MANIFESTO_TEXT.format(
                root_files=", ".join(INCLUDED_ROOT_FILES),
                dirs=", ".join(INCLUDED_DIRS),
            ),
        )
    return zip_path


def zip_summary(zip_path: Path) -> dict[str, Any]:
    """Resumo legível do zip (nomes e tamanhos) para a UI/log."""
    with zipfile.ZipFile(zip_path) as bundle:
        infos = bundle.infolist()
    return {
        "path": str(zip_path),
        "n_files": len(infos),
        "total_bytes": sum(info.file_size for info in infos),
        "names": sorted(info.filename for info in infos),
    }
