"""Recover, from disk, the candidates a finished run discarded before ranking them.

Why this exists
---------------
The 4 Gyr secular run `screen_20260924T174217246692Z` integrated all 10 of its
branches to completion, yet 4 of its 5 candidates reached `results/ranking.csv`
as `failed`/`invalid` with empty metrics: the Delta_pomega series written by the
pre-2026-09-25 engine narrowed its column set as soon as an ETNO was ejected, so
post-processing hit `float(None)` *after* the ~13 h integration had already been
paid for (Bloqueio B5 in TASK.md). Worse, those legacy CSVs are also
positionally corrupted (cells map to the wrong ETNO names when a row is shorter
than the header), so they cannot simply be re-read - they must be regenerated
from the SimulationArchive checkpoints.

What this script does
---------------------
    python scripts/reprocess_run.py --run runs/<run_id> [--candidate-id X ...]
                                    [--max-workers N] [--rebuild-only] [--dry-run]

1. rebuilds each selected candidate's `<id>_with_p9_delta_pomega_series.csv`
   from `<id>_with_p9.bin` and verifies it against the archive;
2. drops those candidates from `candidates_results_cache.json` and resets their
   `candidates_status.csv` row to `pending` - the documented way to make
   `resume` recompute a candidate (`resume` treats `failed` as terminal);
3. calls `planet9lab.run.resume_run()`, which recomputes only the pending
   candidates. Their archives already sit at the integration target, so
   `run_branch_checkpointed` skips the integration loop and only re-reads
   artifacts from disk (minutes instead of the original ~13 h; *no* simulation
   is advanced), then re-finalizes ranking/report/audit for ALL candidates.

Nothing is destroyed: cache, status and series are copied to
`*.pre_reprocess_<UTC>` first and every step is appended to `events.log`,
so the run directory can be restored to its pre-reprocess state by hand.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rebuild_pomega_series import _load_run, _verify  # noqa: E402

from planet9lab.artifacts import read_csv_dicts, write_csv, write_json  # noqa: E402
from planet9lab.run import append_event, cache_path, load_result_cache, resume_run  # noqa: E402


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _backup(path: Path, stamp: str) -> Path | None:
    """Keep the original beside itself before it is rewritten."""
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.pre_reprocess_{stamp}")
    shutil.copy2(path, backup)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--run",
        required=True,
        help="run directory (must contain checkpoints/ and audit/run_manifest.json)",
    )
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=None,
        help="limit to this candidate id (repeatable); default: every 'failed' candidate with a with_p9 archive",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="parallel workers for the resume step (default: pipeline default)",
    )
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="regenerate the Delta_pomega series and stop (no cache/status change, no resume)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan and change nothing")
    args = parser.parse_args()

    run_dir = Path(args.run).resolve()
    checkpoint_dir = run_dir / "checkpoints"
    if not checkpoint_dir.is_dir():
        print(f"erro: {run_dir} nao tem checkpoints/", file=sys.stderr)
        return 2
    if not (run_dir / "audit" / "run_manifest.json").exists():
        print(f"erro: {run_dir} sem audit/run_manifest.json (run nunca finalizada?)", file=sys.stderr)
        return 2

    engine, candidates, etnos = _load_run(run_dir)
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    status_rows = read_csv_dicts(run_dir / "candidates_status.csv")
    cache = load_result_cache(run_dir)

    selected = [
        row["candidate_id"]
        for row in status_rows
        if row.get("operational_status") == "failed"
        and (checkpoint_dir / f"{row['candidate_id']}_with_p9.bin").exists()
    ]
    if args.candidate_id:
        wanted = set(args.candidate_id)
        unknown = wanted - set(by_id)
        if unknown:
            print(f"erro: candidato(s) desconhecido(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        selected = [
            candidate_id
            for candidate_id in sorted(wanted)
            if (checkpoint_dir / f"{candidate_id}_with_p9.bin").exists()
        ]
    if not selected:
        print("nada a fazer: nenhum candidato selecionado possui archive with_p9.")
        return 0

    stamp = _stamp()
    print(f"reprocesso de {run_dir.name}: {', '.join(selected)}")
    if args.dry_run:
        for candidate_id in selected:
            print(f"  [dry-run] {candidate_id}: rebuild da serie + reset para pending + resume")
        return 0

    # 1. Regenerate the (positionally corrupted) Delta_pomega series from the archive.
    rebuilt: list[str] = []
    for candidate_id in selected:
        series = checkpoint_dir / f"{candidate_id}_with_p9_delta_pomega_series.csv"
        archive = checkpoint_dir / f"{candidate_id}_with_p9.bin"
        _backup(series, stamp)
        path = engine.rebuild_delta_pomega_series(etnos, by_id[candidate_id], checkpoint_dir)
        if path is None:
            print(f"  [serie]  {candidate_id}: NADA a reconstruir (sem instantes com ETNOs)")
            continue
        verdict = _verify(path, archive)
        print(f"  [serie]  {candidate_id}: {verdict}")
        if verdict.startswith("FALHOU"):
            append_event(run_dir, "reprocess_verify_failed", candidate_id=candidate_id, verdict=verdict)
            print("erro: serie reconstruida nao bate com o archive; abortado antes de tocar no cache.", file=sys.stderr)
            return 3
        rebuilt.append(candidate_id)
    append_event(run_dir, "reprocess_series_rebuilt", candidates=rebuilt, stamp=stamp)
    if args.rebuild_only or not rebuilt:
        return 0

    # 2. Reset the failed entries so `resume` recomputes them (the procedure
    #    documented in resume_run's docstring). Originals are backed up first.
    _backup(cache_path(run_dir), stamp)
    _backup(run_dir / "candidates_status.csv", stamp)
    remaining = {key: value for key, value in cache.items() if key not in rebuilt}
    write_json(cache_path(run_dir), remaining)
    for row in status_rows:
        if row["candidate_id"] in rebuilt:
            row["operational_status"] = "pending"
            row["scientific_status"] = "pending"
            row["started_at"] = ""
            row["ended_at"] = ""
            row["blockers"] = ""
    write_csv(run_dir / "candidates_status.csv", status_rows, list(status_rows[0]))
    append_event(run_dir, "reprocess_reset_to_pending", candidates=rebuilt, stamp=stamp)
    print(f"  [reset]  {len(rebuilt)} candidato(s) movidos para pending (cache {len(cache)} -> {len(remaining)})")

    # 3. Recompute from the checkpoints and re-finalize the run.
    print("  [resume] recomputando os pendentes a partir dos checkpoints ...")
    result = resume_run(run_dir, max_workers=args.max_workers)
    append_event(run_dir, "reprocess_resumed", candidates=rebuilt, message=str(result.get("message", "")))
    print(f"  [fim]    {result.get('message', '')}")
    for row in read_csv_dicts(run_dir / "candidates_status.csv"):
        note = "  <- recuperado" if row["candidate_id"] in rebuilt else ""
        print(f"           {row['candidate_id']}: {row['operational_status']} / {row['scientific_status']}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
