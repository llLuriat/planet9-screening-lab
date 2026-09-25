"""MEGNO em lote para todos os candidatos de um catálogo (campanha 2026-09-25).

Repete o caminho do CLI ``megno`` (planet9lab.megno.run_megno) candidato a
candidato, com horizonte limitado por ``--years`` (custo controlado; o
horizonte completo do budget seria caro demais para 8+ candidatos), e grava
um JSON agregado em ``results/``. Não implementa física nova — só agregação.

Uso:
    python scripts/megno_batch.py --catalog data/candidates_quadro2.csv \
        --budget configs/budgets/secular_100myr.yaml --years 10000000
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from planet9lab.engine import ReboundEngine  # noqa: E402
from planet9lab.loaders import (  # noqa: E402
    included_etnos,
    load_budget,
    load_candidates,
    load_etnos,
    load_giants,
)
from planet9lab.megno import run_megno  # noqa: E402
from planet9lab.run import default_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default="data/candidates_quadro2.csv")
    parser.add_argument("--budget", default="configs/budgets/secular_100myr.yaml")
    parser.add_argument("--years", type=float, default=1e7)
    parser.add_argument("--seed", type=int, default=42, help="seed fixa do MEGNO (padrao do CLI: 42)")
    args = parser.parse_args()

    paths = default_paths()
    budget = load_budget(args.budget)
    giants = load_giants(str(paths["giants_catalog"]))
    engine = ReboundEngine(budget, args.seed, giants, allow_analytical_fallback=False)
    etnos = included_etnos(load_etnos(str(paths["etno_catalog"])))
    candidates = load_candidates(args.catalog, budget.max_candidates)

    results = []
    for candidate in candidates:
        payload = run_megno(engine, etnos, candidate, args.years, seed=args.seed)
        entry = {"candidate_id": candidate.candidate_id, **payload}
        results.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path("results") / f"megno_batch_{stamp}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "catalog": args.catalog,
                "budget": args.budget,
                "years": args.years,
                "seed": args.seed,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"MEGNO batch written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
