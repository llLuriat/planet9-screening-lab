"""Contratos do empacotamento de download (dashboard/artifacts.py).

O zip "Baixar resultados" é um INVENTÁRIO de conveniência: contém os
artefatos canônicos de auditoria + relatorio.html (o MESMO HTML da UI) +
MANIFESTO.txt (o que entrou e o que ficou de fora); NUNCA contém
checkpoints pesados, cache volátil ou locks. Nada em runs/ é alterado.
"""

from __future__ import annotations

import zipfile

from dashboard import artifacts, report


def _make_run(root) -> object:
    """Run mínima com artefatos canônicos + coisas que DEVEM ficar de fora."""
    run_dir = root / "screen_20260101T000000000000Z"
    (run_dir / "results").mkdir(parents=True)
    (run_dir / "audit").mkdir()
    (run_dir / "diagnostics").mkdir()
    (run_dir / "checkpoints").mkdir()
    (run_dir / "status.json").write_text('{"status": "completed"}', encoding="utf-8")
    (run_dir / "config.resolved.yaml").write_text("budget: low\n", encoding="utf-8")
    (run_dir / "SUCCESS.marker").write_text("ok", encoding="utf-8")
    (run_dir / "candidates_results_cache.json").write_text("{}", encoding="utf-8")
    (run_dir / "RUNNING.lock").write_text("pid", encoding="utf-8")
    (run_dir / "results" / "ranking.csv").write_text("candidate_id\n", encoding="utf-8")
    (run_dir / "audit" / "run_manifest.json").write_text("{}", encoding="utf-8")
    diag = {"caveats": ["triagem exploratória, não confirmação"], "interpretation": "x"}
    (run_dir / "diagnostics" / "selection_bias.json").write_text(
        str(diag), encoding="utf-8"
    )
    (run_dir / "checkpoints" / "series.csv").write_text("t_years\n", encoding="utf-8")
    return run_dir


def _names(zip_path) -> set[str]:
    with zipfile.ZipFile(zip_path) as bundle:
        return set(bundle.namelist())


def test_zip_contains_canonical_artifacts_and_excludes_heavy(tmp_path):
    run_dir = _make_run(tmp_path)
    zip_path = artifacts.build_results_zip(run_dir, dest_dir=tmp_path / "out")
    assert zip_path.is_file()
    summary = artifacts.zip_summary(zip_path)
    assert summary["n_files"] == len(summary["names"])
    names = set(summary["names"])
    assert {
        "status.json",
        "config.resolved.yaml",
        "SUCCESS.marker",
        "results/ranking.csv",
        "audit/run_manifest.json",
        "diagnostics/selection_bias.json",
        "relatorio.html",
        "MANIFESTO.txt",
    } <= names
    # Ficam de fora (decisão documentada):
    assert not any(name.startswith("checkpoints/") for name in names)
    assert "candidates_results_cache.json" not in names
    assert "RUNNING.lock" not in names


def test_relatorio_html_is_exactly_the_report_rendered_by_the_ui(tmp_path):
    run_dir = _make_run(tmp_path)
    zip_path = artifacts.build_results_zip(run_dir, dest_dir=tmp_path / "out")
    with zipfile.ZipFile(zip_path) as bundle:
        bundled = bundle.read("relatorio.html").decode("utf-8")
    assert bundled == report.render_run_report(run_dir)


def test_manifesto_documents_what_is_included_and_excluded(tmp_path):
    run_dir = _make_run(tmp_path)
    zip_path = artifacts.build_results_zip(run_dir, dest_dir=tmp_path / "out")
    with zipfile.ZipFile(zip_path) as bundle:
        manifesto = bundle.read("MANIFESTO.txt").decode("utf-8")
    assert "checkpoints" in manifesto
    assert "candidates_results_cache.json" in manifesto
    assert "INVENTÁRIO" in manifesto
    assert "triagem exploratória" in manifesto


def test_zip_is_overwritten_and_missing_dirs_are_tolerated(tmp_path):
    run_dir = tmp_path / "smoke_20260101T000000000000Z"
    (run_dir / "results").mkdir(parents=True)
    (run_dir / "results" / "ranking.csv").write_text("a\n", encoding="utf-8")
    first = artifacts.build_results_zip(run_dir, dest_dir=tmp_path / "out")
    first_bytes = first.read_bytes()
    (run_dir / "results" / "ranking.csv").write_text("a,b\n", encoding="utf-8")
    second = artifacts.build_results_zip(run_dir, dest_dir=tmp_path / "out")
    assert first == second
    assert second.read_bytes() != first_bytes

    bare = tmp_path / "smoke_20260102T000000000000Z"
    bare.mkdir()
    zip_path = artifacts.build_results_zip(bare, dest_dir=tmp_path / "out")
    assert {"relatorio.html", "MANIFESTO.txt"} <= _names(zip_path)
