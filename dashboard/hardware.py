"""Defaults inteligentes derivados do hardware medido — nunca inventados.

Princípio (mesma regra científica do resto do dashboard): um campo
pré-preenchido só pode vir de um dado que EXISTE no repositório ou de uma
propriedade real da máquina local. Nada aqui estima nem arredonda de
memória.

Fontes usadas:
- ``os.cpu_count()`` — número de threads lógicas DESTA máquina (dado real,
  lido em tempo de execução);
- ``results/hardware_benchmark.json`` — medido por
  ``scripts/benchmark_integration_cost.py`` (ou pelo subcomando
  ``python main.py benchmark``) e VÁLIDO SOMENTE para a máquina registrada
  nele (o próprio arquivo declara isso no campo ``provenance``).

Por isso a comparação ``logical_cpus`` do arquivo vs. threads locais é
explícita: se o benchmark veio de OUTRA máquina, o hint diz isso em vez de
sugerir um número calibrado que não vale aqui.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dashboard import runstore
from dashboard.config import REPO_ROOT

BENCHMARK_RELPATH = "results/hardware_benchmark.json"
BENCHMARK_PATH = REPO_ROOT / BENCHMARK_RELPATH


def local_logical_cpus() -> int:
    """Threads lógicas desta máquina (mínimo 1; nunca 0)."""
    return max(1, os.cpu_count() or 1)


def load_benchmark(path: Path | None = None) -> dict[str, Any]:
    """Conteúdo do benchmark de hardware; ``{}`` se ausente/ilegível."""
    data = runstore.read_json(Path(path) if path is not None else BENCHMARK_PATH)
    return data if isinstance(data, dict) else {}


def benchmark_matches_this_machine(data: dict[str, Any]) -> bool:
    """True só se o benchmark foi medido NESTA máquina (threads coincidem)."""
    recorded = data.get("logical_cpus")
    if not isinstance(recorded, (int, float)) or int(recorded) <= 0:
        return False
    return int(recorded) == local_logical_cpus()


def suggest_max_workers() -> int:
    """Sugestão de ``--max-workers``: threads lógicas DESTA máquina.

    Não usa o número do arquivo quando ele veio de outra máquina (o valor
    medido lá não descreve o paralelismo disponível aqui).
    """
    return local_logical_cpus()


def benchmark_summary(path: Path | None = None) -> dict[str, Any]:
    """Resumo honesto do benchmark para a UI (sem recálculo de números)."""
    data = load_benchmark(path)
    if not data:
        return {
            "present": False,
            "matches_this_machine": False,
            "measured_on": None,
            "cpu_model": None,
            "logical_cpus": None,
            "simulated_years_per_second": None,
            "local_logical_cpus": local_logical_cpus(),
        }
    return {
        "present": True,
        "matches_this_machine": benchmark_matches_this_machine(data),
        "measured_on": data.get("measured_on"),
        "cpu_model": data.get("cpu_model"),
        "logical_cpus": data.get("logical_cpus"),
        "simulated_years_per_second": data.get("simulated_years_per_second"),
        "local_logical_cpus": local_logical_cpus(),
    }


def max_workers_hint(path: Path | None = None) -> str:
    """Texto do tooltip/legenda do campo ``--max-workers`` (pt-BR, honesto)."""
    local = local_logical_cpus()
    summary = benchmark_summary(path)
    if not summary["present"]:
        return (
            f"{local} threads lógicas detectadas nesta máquina — valor sugerido. "
            f"Sem benchmark local (results/hardware_benchmark.json ausente): use "
            f"'Rodar benchmark de hardware' para medir a taxa desta máquina."
        )
    rate = summary["simulated_years_per_second"]
    rate_text = f"{rate:,.1f}".replace(",", " ").replace(".", ",") if isinstance(rate, (int, float)) else "?"
    if summary["matches_this_machine"]:
        return (
            f"{local} threads lógicas nesta máquina (valor sugerido; sobrescreva à vontade). "
            f"Benchmark medido AQUI em {summary['measured_on']}: {rate_text} anos simulados/s "
            f"(single-core, single branch)."
        )
    return (
        f"{local} threads lógicas nesta máquina — valor sugerido. Atenção: o benchmark do "
        f"repositório foi medido em OUTRA máquina ({summary['logical_cpus']} threads, "
        f"{summary['cpu_model']}, {summary['measured_on']}) e vale apenas para ela; para um "
        f"número calibrado aqui, use 'Rodar benchmark de hardware'."
    )


def suggest_run_root() -> str:
    """Default do campo ``--run-root``: o diretório óbvio do projeto."""
    return "runs"
