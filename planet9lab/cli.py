from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .audit import audit_run
from .diagnostics import diagnose_null_models, diagnose_scoring
from .engine import ReboundUnavailable
from .explain import explain_candidate, why_rejected
from .families import candidate_families
from .physics import run_physics_checks
from .rescore import rescore_run
from .robustness import convergence, leave_one_out, null_models, refresh_v2_report, validate_top
from .run import plan_run, resume_run, run_compare, run_montecarlo_scan, run_screen, run_smoke
from .sample_data import init_data
from .selection_bias import run_selection_bias_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planet9-screening-lab")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="dry-run a screen without simulation")
    plan.add_argument("--budget", required=True)
    plan.add_argument("--allow-analytical-fallback", action="store_true")

    sub.add_parser("init-data", help="write canonical V1 catalogs and candidate configs")
    sub.add_parser("physics-check", help="run REBOUND and numerical sanity checks")

    smoke = sub.add_parser("smoke", help="run a tiny deterministic smoke screen")
    smoke.add_argument("--allow-analytical-fallback", action="store_true")
    smoke.add_argument("--run-root", default=None, help="override run destination directory (default: ./runs)")
    smoke.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    compare = sub.add_parser("compare", help="run one with/without P9 control pair")
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--budget", required=True)
    compare.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="recorded in the run manifest for provenance, but has NO physical effect on "
        "`compare`/`screen` (fixed catalog, deterministic WHFast initial conditions). "
        "It only changes results for `montecarlo-scan` and the null models.",
    )
    compare.add_argument("--allow-analytical-fallback", action="store_true")
    compare.add_argument("--run-root", default=None, help="override run destination directory (default: ./runs)")
    compare.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    screen = sub.add_parser("screen", help="screen candidate catalog")
    screen.add_argument("--budget", required=True)
    screen.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="recorded in the run manifest for provenance, but has NO physical effect on "
        "`screen`/`compare` (fixed catalog, deterministic WHFast initial conditions). "
        "It only changes results for `montecarlo-scan` and the null models.",
    )
    screen.add_argument("--allow-analytical-fallback", action="store_true")
    screen.add_argument("--candidates", default=None, help="override candidate_catalog CSV path (default: data/candidates_example.csv)")
    screen.add_argument("--etnos", default=None, help="override etno_catalog CSV path (default: data/etnos/catalog.csv)")
    screen.add_argument("--run-root", default=None, help="override run destination directory (default: ./runs)")
    screen.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    audit = sub.add_parser("audit-run", help="audit a run folder")
    audit.add_argument("run_dir")

    explain = sub.add_parser("explain-candidate", help="explain a candidate ranking")
    explain.add_argument("candidate_id")
    explain.add_argument("--from-run", required=True)

    rejected = sub.add_parser("why-rejected", help="explain candidate rejection")
    rejected.add_argument("candidate_id")
    rejected.add_argument("--from-run", required=True)

    rescore = sub.add_parser("rescore", help="rescore an existing run without simulation")
    rescore.add_argument("--from-run", required=True)
    rescore.add_argument("--weights", required=True)

    resume = sub.add_parser("resume", help="resume or inspect pending candidates in a run")
    resume.add_argument("run_dir", nargs="?")
    resume.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    mc = sub.add_parser("montecarlo-scan", help="run the Monte Carlo/QMC parameter-space scan")
    mc.add_argument("--config", default="configs/montecarlo/parameter_space.yaml")
    mc.add_argument("--seed", type=int, default=None)
    mc.add_argument("--run-root", default=None, help="override run destination directory (default: ./runs)")
    mc.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    status = sub.add_parser("status", help="show status of the latest (or given) run - one-shot snapshot")
    status.add_argument("run_dir", nargs="?")

    watch = sub.add_parser("watch", help="live-refreshing progress view of a run (Ctrl+C to stop)")
    watch.add_argument("run_dir", nargs="?")
    watch.add_argument("--interval", type=float, default=15.0)

    loo = sub.add_parser("leave-one-out", help="V2 robustness: re-run top candidates with each ETNO held out")
    loo.add_argument("--from-run", required=True)
    loo.add_argument("--top", type=int, default=5)
    loo.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    conv = sub.add_parser("convergence", help="V2 robustness: check ranking stability across timestep refinement")
    conv.add_argument("--from-run", required=True)
    conv.add_argument("--top", type=int, default=5)
    conv.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    validate = sub.add_parser("validate-top", help="V2 robustness: re-run top candidates with a different integrator (e.g. IAS15)")
    validate.add_argument("--from-run", required=True)
    validate.add_argument("--top", type=int, default=5)
    validate.add_argument("--integrator", default="ias15")
    validate.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    nulls = sub.add_parser("null-models", help="V2 robustness: compare real delta against null (shuffled) models")
    nulls.add_argument("--from-run", required=True)
    nulls.add_argument("--top", type=int, default=5)
    nulls.add_argument("--n-shuffles", type=int, default=20)
    nulls.add_argument("--models", default="shuffle_varpi")
    nulls.add_argument("--max-workers", type=int, default=None, help="parallel workers (default: CPU count; 1 = sequential)")

    diag_score = sub.add_parser("diagnose-scoring", help="V2 diagnostic: per-component score contribution and saturation")
    diag_score.add_argument("--from-run", required=True)

    diag_null = sub.add_parser("diagnose-null-models", help="V2 diagnostic: summarize null-model results already computed")
    diag_null.add_argument("--from-run", required=True)

    bias_check = sub.add_parser("selection-bias-check", help="V2 diagnostic: test whether real ETNO angular clustering could be a selection-function artifact")
    bias_check.add_argument("--from-run", required=True)
    bias_check.add_argument("--config", default="configs/science/observational_bias.yaml")

    families = sub.add_parser("candidate-families", help="V2 diagnostic: group similar candidates by parameter distance")
    families.add_argument("--from-run", required=True)
    families.add_argument("--top", type=int, default=20)

    report = sub.add_parser("report", help="regenerate report.md, including the V2 robustness section if present")
    report.add_argument("--from-run", required=True)

    megno_cmd = sub.add_parser(
        "megno",
        help="EXPERIMENTAL chaos indicator (MEGNO) for one candidate; auxiliary and uncalibrated, not a stability claim",
    )
    megno_cmd.add_argument("--candidate", required=True, help="candidate_id from data/candidates_example.csv")
    megno_cmd.add_argument("--budget", required=True)
    megno_cmd.add_argument("--years", type=float, default=None, help="integration span in yr (default: budget.integration_years)")
    megno_cmd.add_argument("--seed", type=int, default=42, help="fixed MEGNO seed for reproducibility")
    megno_cmd.add_argument("--allow-analytical-fallback", action="store_true")

    circular = sub.add_parser(
        "circular-stats",
        help="READ-ONLY side-by-side Rayleigh/Kuiper circular statistics over an existing run (never reclassifies)",
    )
    circular.add_argument("--from-run", required=True)
    circular.add_argument("--alpha", type=float, default=0.05, help="significance level for the side-by-side flags (default: 0.05)")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            print_plan(plan_run(args.budget, args.allow_analytical_fallback))
            return 0
        if args.command == "init-data":
            init_data()
            print("Canonical data initialized.")
            return 0
        if args.command == "physics-check":
            checks = run_physics_checks()
            print(json.dumps(checks, indent=2, sort_keys=True))
            if not checks["rebound_available"]:
                print("REBOUND real package is not installed; physical commands will fail without --allow-analytical-fallback.")
            return 0 if checks["overall_ok"] else 1
        if args.command == "smoke":
            run_root = Path(args.run_root) if args.run_root else None
            print(f"Smoke run created: {run_smoke(args.allow_analytical_fallback, run_root=run_root, max_workers=args.max_workers)}")
            return 0
        if args.command == "compare":
            run_root = Path(args.run_root) if args.run_root else None
            print(
                "Compare run created: "
                f"{run_compare(args.candidate, args.budget, args.seed, args.allow_analytical_fallback, run_root=run_root, max_workers=args.max_workers)}"
            )
            return 0
        if args.command == "screen":
            run_root = Path(args.run_root) if args.run_root else None
            print(
                f"Screen run created: {run_screen(args.budget, args.seed, args.allow_analytical_fallback, run_root=run_root, candidate_catalog=args.candidates, etno_catalog=args.etnos, max_workers=args.max_workers)}"
            )
            return 0
        if args.command == "audit-run":
            ok, issues = audit_run(args.run_dir)
            if ok:
                print("AUDIT OK")
                return 0
            print("AUDIT FAILED")
            for issue in issues:
                print(f"- {issue}")
            return 1
        if args.command == "explain-candidate":
            print(explain_candidate(args.candidate_id, args.from_run))
            return 0
        if args.command == "why-rejected":
            print(why_rejected(args.candidate_id, args.from_run))
            return 0
        if args.command == "rescore":
            print(f"Rescore created: {rescore_run(args.from_run, args.weights)}")
            return 0
        if args.command == "resume":
            run_dir = args.run_dir
            if run_dir is None:
                latest = Path("runs/latest_run.txt")
                if not latest.exists():
                    print("No run found.")
                    return 1
                run_dir = latest.read_text(encoding="utf-8").strip()
            result = resume_run(run_dir, max_workers=args.max_workers)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "montecarlo-scan":
            run_root = Path(args.run_root) if args.run_root else None
            run_dir = run_montecarlo_scan(args.config, args.seed, run_root=run_root, max_workers=args.max_workers)
            print(f"Monte Carlo scan created: {run_dir}")
            return 0
        if args.command in ("status", "watch"):
            import subprocess
            import sys as _sys
            from pathlib import Path as _Path

            watcher = _Path(__file__).resolve().parent.parent / "scripts" / "watch_progress.py"
            cmd = [_sys.executable, str(watcher)]
            if args.run_dir:
                cmd += ["--run-dir", args.run_dir]
            if args.command == "status":
                cmd += ["--once"]
            else:
                cmd += ["--interval", str(args.interval)]
            return subprocess.call(cmd)
        if args.command == "leave-one-out":
            print(f"Leave-one-out written to: {leave_one_out(args.from_run, args.top, max_workers=args.max_workers)}")
            return 0
        if args.command == "convergence":
            print(f"Convergence written to: {convergence(args.from_run, args.top, max_workers=args.max_workers)}")
            return 0
        if args.command == "validate-top":
            print(f"IAS15 validation written to: {validate_top(args.from_run, args.top, args.integrator, max_workers=args.max_workers)}")
            return 0
        if args.command == "null-models":
            print(f"Null models written to: {null_models(args.from_run, args.top, args.n_shuffles, args.models, max_workers=args.max_workers)}")
            return 0
        if args.command == "diagnose-scoring":
            print(f"Scoring diagnosis written to: {diagnose_scoring(args.from_run)}")
            return 0
        if args.command == "diagnose-null-models":
            print(f"Null model diagnosis written to: {diagnose_null_models(args.from_run)}")
            return 0
        if args.command == "candidate-families":
            print(f"Candidate families written to: {candidate_families(args.from_run, args.top)}")
            return 0
        if args.command == "selection-bias-check":
            print(f"Selection bias check written to: {run_selection_bias_check(args.from_run, args.config)}")
            return 0
        if args.command == "report":
            print(f"Report refreshed: {refresh_v2_report(args.from_run)}")
            return 0
        if args.command == "megno":
            from .engine import ReboundEngine
            from .loaders import (
                included_etnos,
                load_budget,
                load_candidates,
                load_etnos,
                load_giants,
            )
            from .megno import run_megno
            from .run import default_paths

            paths = default_paths()
            budget = load_budget(args.budget)
            giants = load_giants(str(paths["giants_catalog"]))
            engine = ReboundEngine(budget, args.seed, giants, args.allow_analytical_fallback)
            etnos = included_etnos(load_etnos(str(paths["etno_catalog"])))
            candidates = {c.candidate_id: c for c in load_candidates(str(paths["candidate_catalog"]))}
            if args.candidate not in candidates:
                raise ValueError(f"unknown candidate_id '{args.candidate}'; available: {sorted(candidates)}")
            integration_years = args.years if args.years is not None else budget.integration_years
            result = run_megno(engine, etnos, candidates[args.candidate], integration_years, seed=args.seed)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "circular-stats":
            from .circular_report import circular_stats_report

            result = circular_stats_report(args.from_run, alpha=args.alpha)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
    except ReboundUnavailable as exc:
        print(str(exc))
        return 2
    parser.error("Unknown command")
    return 2


def print_plan(plan: dict) -> None:
    print("Planet9 Screening Lab V1 plan")
    print(f"candidates: {plan['candidate_count']}")
    print(f"integration_years: {plan['integration_years']}")
    print(f"seeds: {plan['seeds']}")
    print(f"integrator: {plan['integrator']}")
    print(f"allow_analytical_fallback: {plan['allow_analytical_fallback']}")
    print("input_files:")
    for name, path in plan["input_files"].items():
        print(f"  {name}: {path}")
    print("pre_run_blockers:")
    if plan["pre_run_blockers"]:
        for blocker in plan["pre_run_blockers"]:
            print(f"  {blocker['blocker_id']}: {blocker['message']}")
    else:
        print("  none")
    print("cost_estimate:")
    for key, value in plan["cost_estimate"].items():
        print(f"  {key}: {value}")
    print("files_to_generate:")
    for file_name in plan["generated_files"]:
        print(f"  {file_name}")
