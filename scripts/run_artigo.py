"""Roda o screen canonico do artigo com os catalogos reais do Quadro 2.

Sempre usa data/candidates_quadro2.csv e data/etnos/catalog_validated.csv, para
que um run acidental sem as flags --candidates/--etnos nao use os catalogos
placeholder (data/candidates_example.csv / data/etnos/catalog.csv) e produza um
ranking enganoso. Este wrapper nao adiciona comportamento: apenas fixa as
entradas reais e delega ao run_screen do pipeline.

Uso:
    python scripts/run_artigo.py [--budget configs/budgets/secular.yaml] [--seed 12345]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from planet9lab.run import run_screen  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", default="configs/budgets/secular.yaml")
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args()

    run_dir = run_screen(
        args.budget,
        args.seed,
        candidate_catalog=str(ROOT / "data" / "candidates_quadro2.csv"),
        etno_catalog=str(ROOT / "data" / "etnos" / "catalog_validated.csv"),
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
