"""Resume um run a partir de runs/<id>/candidates_results_cache.json.

Uso:
    .venv\\Scripts\\python.exe scripts\\cache_summary.py [run_id]

Sem argumentos usa o run mais recente em runs/ que tenha cache.
Imprime: chaves top-level, campos do primeiro candidato e uma tabela
compacta com as métricas-chave de todos os candidatos cacheados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _latest_run_with_cache() -> Path:
    runs = sorted((ROOT / "runs").glob("screen_*"), key=lambda p: p.name)
    for run in reversed(runs):
        cache = run / "candidates_results_cache.json"
        if cache.is_file():
            return cache
    raise SystemExit("nenhum candidates_results_cache.json encontrado em runs/")


def main() -> int:
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
        cache = ROOT / "runs" / run_id / "candidates_results_cache.json"
        if not cache.is_file():
            cache = Path(run_id)
    else:
        cache = _latest_run_with_cache()

    data = json.loads(cache.read_text(encoding="utf-8"))
    print(f"CACHE {cache}")
    print("TOP", type(data).__name__, len(data))

    if isinstance(data, dict):
        keys = list(data)
        print("CANDIDATES", keys)
        first = data[keys[0]]
        if isinstance(first, dict):
            print("FIELDS(first)", sorted(first))
            for k in sorted(first):
                print("   ", k, "=", str(first[k])[:150])
        else:
            print("FIRST", str(first)[:400])
    elif isinstance(data, list):
        print("LIST len", len(data))
        if data:
            item = data[0]
            if isinstance(item, dict):
                print("FIELDS(first)", sorted(item))
                for k in sorted(item):
                    print("   ", k, "=", str(item[k])[:150])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
