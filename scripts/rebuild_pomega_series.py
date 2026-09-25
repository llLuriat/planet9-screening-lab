"""Rebuild the per-ETNO Delta_pomega series of a run from its own checkpoints.

Why this exists
---------------
`run_branch_checkpointed` saves, at every checkpoint, the full N-body state in a
REBOUND SimulationArchive (`checkpoints/<candidate>_with_p9.bin`) and the derived
per-ETNO Delta_pomega series in a CSV beside it. Until 2026-09-25 the CSV column
set was recomputed at every checkpoint, so a checkpoint at which an ETNO had been
ejected wrote a row NARROWER than the file header. Reading such a file back maps
cells positionally, which attributes the surviving values to the WRONG ETNO
names, and `float(None)` could abort the candidate AFTER its multi-hour
integration had already finished. That is what discarded 4 of the 5 candidates of
the 4 Gyr secular run `screen_20260924T174217246692Z`.

The engine fix (2026-09-25) stops new runs from writing ragged series. Series
already written by the old code cannot be repaired from the file alone (the
damage is information-destroying), but they do not need to be: the series is
derived data and the SimulationArchive keeps every state required to recompute it
exactly as the live run did.

Usage
-----
    python scripts/rebuild_pomega_series.py --run runs/<run_id>
    python scripts/rebuild_pomega_series.py --run runs/<run_id> --candidate-id p9_inner_unstable
    python scripts/rebuild_pomega_series.py --run runs/<run_id> --dry-run

Only `<candidate>_with_p9_delta_pomega_series.csv` files are written; the damaged
version is preserved next to it as `*.pre_rebuild_<UTC>` for forensics, and every
other artifact of the run is left untouched. To turn a rebuilt series into
results, recompute the discarded candidates through the normal resume flow
(`python main.py resume <run_dir>`), which loads each branch's final snapshot and
recomputes the metrics from disk - no re-integration.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from planet9lab.artifacts import read_csv_dicts  # noqa: E402
from planet9lab.config import load_yaml  # noqa: E402
from planet9lab.engine import ReboundEngine  # noqa: E402
from planet9lab.loaders import included_etnos, load_etnos, load_giants  # noqa: E402
from planet9lab.run import default_paths, read_manifest  # noqa: E402
from planet9lab.schemas import BudgetConfig, P9Candidate  # noqa: E402

TIME_TOLERANCE_YEARS = 1e-6


def _load_run(run_dir: Path) -> tuple[ReboundEngine, list[P9Candidate], list]:
    """Rebuild the exact run configuration from the run folder itself."""
    config = load_yaml(run_dir / "config.resolved.yaml")
    budget = BudgetConfig.model_validate(config["budget"])
    candidates = [P9Candidate.model_validate(row) for row in read_csv_dicts(run_dir / "candidates_input.csv")]
    paths = default_paths()
    etnos = included_etnos(load_etnos(paths["etno_catalog"]))
    giants = load_giants(paths["giants_catalog"])
    try:
        seed = int(read_manifest(run_dir).get("seed", budget.seeds[0]))
    except (FileNotFoundError, KeyError, TypeError):
        seed = int(budget.seeds[0])
    engine = ReboundEngine(budget, seed, giants, bool(config.get("allow_analytical_fallback", False)))
    return engine, candidates, etnos


def _verify(series_path: Path, archive_path: Path) -> str:
    """Check the rewritten series against the archive it came from."""
    import rebound

    with series_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return f"FALHOU: larguras de linha diferentes {sorted(widths)}"

    archive = rebound.Simulationarchive(str(archive_path))
    times_archive = [archive[index].t for index in range(len(archive)) if archive[index].t > 0]
    times_csv = [float(row[0]) for row in rows[1:]]
    if len(times_csv) != len(times_archive):
        return f"FALHOU: {len(times_csv)} linhas de dados vs {len(times_archive)} snapshots com t>0"
    worst = max(abs(a - b) for a, b in zip(times_csv, times_archive, strict=True))
    if worst > TIME_TOLERANCE_YEARS:
        return f"FALHOU: tempos divergem do archive (pior diferenca {worst:.6f} anos)"
    return f"OK: {len(times_csv)} linhas, {widths.pop()} colunas, tempos identicos ao archive"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="run directory (must contain checkpoints/)")
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=None,
        help="limit to this candidate id (repeatable); default: every candidate with a with_p9 archive",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be rebuilt and write nothing")
    args = parser.parse_args()

    run_dir = Path(args.run)
    checkpoint_dir = run_dir / "checkpoints"
    if not checkpoint_dir.is_dir():
        print(f"erro: {run_dir} nao tem checkpoints/", file=sys.stderr)
        return 2

    engine, candidates, etnos = _load_run(run_dir)
    if args.candidate_id:
        wanted = set(args.candidate_id)
        candidates = [candidate for candidate in candidates if candidate.candidate_id in wanted]
        missing = wanted - {candidate.candidate_id for candidate in candidates}
        if missing:
            print(f"erro: candidato(s) ausente(s) de candidates_input.csv: {sorted(missing)}", file=sys.stderr)
            return 2

    rebuilt = 0
    for candidate in candidates:
        archive = checkpoint_dir / f"{candidate.candidate_id}_with_p9.bin"
        series = checkpoint_dir / f"{candidate.candidate_id}_with_p9_delta_pomega_series.csv"
        if not archive.exists():
            print(f"[pular]    {candidate.candidate_id}: sem archive with_p9")
            continue
        if args.dry_run:
            print(f"[dry-run]  {candidate.candidate_id}: reconstruiria {series.name}")
            continue

        backup = None
        if series.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = series.with_name(f"{series.name}.pre_rebuild_{stamp}")
            backup.write_bytes(series.read_bytes())

        path = engine.rebuild_delta_pomega_series(etnos, candidate, checkpoint_dir)
        if path is None:
            print(f"[pular]    {candidate.candidate_id}: nada a reconstruir")
            continue
        print(f"[ok]       {candidate.candidate_id}: {path.name} -> {_verify(path, archive)}")
        if backup is not None:
            print(f"           original preservado em {backup.name}")
        rebuilt += 1

    where = "seria(m) reconstruida(s)" if args.dry_run else "reconstruida(s)"
    print(f"\n{rebuilt} serie(s) {where} em {checkpoint_dir}")
    if rebuilt and not args.dry_run:
        print("Proximo passo: python main.py resume <run_dir> para recomputar as metricas dos candidatos descartados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
