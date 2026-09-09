"""Testes do dashboard (Tarefa D) — contrato científico e restrições de escopo.

Cobre:
- schema de comandos: todo comando do dashboard existe de fato no parser de
  ``cli.py`` e o argv gerado pelo formulário é aceito pelo argparse (o
  dashboard nunca inventa subcomando nem argumento);
- ``runstore``: leitura read-only dos artefatos canônicos (status.json na
  raiz, audit/, results/, diagnostics/, checkpoints);
- ``report``: CONTRATO NÃO NEGOCIÁVEL — todo ``caveats``/``interpretation``
  dos JSONs de diagnóstico aparece NA ÍNTEGRA no HTML (substring exata após
  reversão de escape; escape aplicado para não injetar tags), o JSON inteiro
  é embutido verbatim, e números vêm do arquivo sem recálculo;
- ``runner``: duplo guardião (bloqueados/desconhecidos/incompletos são
  recusados), lançamento detached real de um subcomando do cli.py
  (``physics-check``) e sobrevivência de processo desacoplado;
- restrições de escopo: bind exclusivo em localhost.
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import time
from pathlib import Path

import pytest

from dashboard import app as app_module
from dashboard import commands, config, report, runner, runstore


def _make_fake_run(root: Path) -> Path:
    """Run mínima com os artefatos canônicos nas pastas certas."""
    run_dir = root / "screen_20260101T000000000000Z"
    (run_dir / "results").mkdir(parents=True)
    (run_dir / "audit").mkdir()
    (run_dir / "diagnostics").mkdir()
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "started_at": "2026-01-01T00:00:00Z",
                "ended_at": "2026-01-01T00:10:00Z",
                "global_result_status": "candidato de interesse dentro do protocolo",
                "candidates_done": 2,
                "candidates_total": 8,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "audit" / "blockers.json").write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "blocker_id": "etno_catalog_not_fully_validated",
                        "message": "O catalogo de ETNOs contem objetos parciais ou nao validados.",
                        "severity": "science_limit",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "audit" / "run_manifest.json").write_text(
        json.dumps({"seed": 12345, "kind": "screen"}), encoding="utf-8"
    )
    (run_dir / "results" / "ranking.csv").write_text(
        "candidate_id,score,verdict\nCAND-001,0.91,weak\nCAND-002,0.42,inconclusivo\n",
        encoding="utf-8",
    )
    caveats = [
        "Modelo angle-only (omega, Omega, M): nao modela geometria de footprint "
        "real nem cadencia real do survey.",
        "Comparação com R > 0,05 & V < 24 — caracteres <especiais> & \"aspas\" "
        "para travar o escape e a íntegra.",
    ]
    diag = {
        "bias_model": "h_prior_from_catalog",
        "caveats": caveats,
        "interpretation": (
            "O catalogo real tem concentracao angular (R) maior que a populacao "
            "sintetica sujeita ao mesmo modelo de seleção — clustering real NÃO é "
            "trivialmente explicado (triagem exploratória, não confirmação)."
        ),
        "real_exceeds_synthetic_R": True,
        "surviving_fraction": 0.1918,
    }
    (run_dir / "diagnostics" / "selection_bias.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return run_dir


# ---------------------------------------------------------------------------
# commands: o dashboard só dispara o que existe de fato no cli.py
# ---------------------------------------------------------------------------


def _cli_subcommand_choices() -> set[str]:
    from planet9lab.cli import build_parser

    parser = build_parser()
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return set(action.choices)


def test_schema_commands_exist_in_cli_parser():
    choices = _cli_subcommand_choices()
    for name in commands.COMMAND_NAMES:
        assert name in choices, f"comando do schema não existe no cli.py: {name}"


def test_build_argv_produces_parseable_args_for_every_command(tmp_path):
    from planet9lab.cli import build_parser

    parser = build_parser()
    run_dir = _make_fake_run(tmp_path)
    for cmd in commands.COMMANDS:
        values: dict = {}
        for arg in cmd["args"]:
            flag = arg["flag"]
            if arg["kind"] == "flag":
                values[flag] = flag == "--allow-analytical-fallback"
            elif arg.get("required"):
                values[flag] = str(run_dir) if arg["kind"] == "path_run" else "1"
            else:
                values[flag] = arg.get("default")
        argv = commands.build_argv(cmd["name"], values)
        ns = parser.parse_args([cmd["name"], *argv])  # SystemExit se inválido
        assert ns.command == cmd["name"]


def test_blocked_commands_are_never_launchable():
    assert "watch" in commands.BLOCKED_COMMANDS
    launchable = set(commands.COMMAND_NAMES) - commands.BLOCKED_COMMANDS
    assert "watch" not in launchable


def test_validate_requires_mandatory_fields(tmp_path):
    problems = commands.validate("selection-bias-check", {})
    assert any("--from-run" in p for p in problems)
    fake = _make_fake_run(tmp_path)
    assert commands.validate("selection-bias-check", {"--from-run": str(fake)}) == []
    missing = commands.validate(
        "selection-bias-check", {"--from-run": str(tmp_path / "nao_existe")}
    )
    assert any("não existe" in p for p in missing)


# ---------------------------------------------------------------------------
# report: CONTRATO NÃO NEGOCIÁVEL — caveats/interpretation NA ÍNTEGRA
# ---------------------------------------------------------------------------


def test_report_embeds_caveats_and_interpretation_verbatim(tmp_path):
    """Todo caveat/interpretation do JSON aparece como substring exata no HTML
    (após escape reversível) — sem paráfrase, resumo ou corte."""
    run_dir = _make_fake_run(tmp_path)
    page = report.render_run_report(run_dir)
    diag = json.loads(
        (run_dir / "diagnostics" / "selection_bias.json").read_text(encoding="utf-8")
    )
    for i, caveat in enumerate(diag["caveats"]):
        assert html.escape(caveat) in page, f"caveat {i} não está íntegro no HTML"
        assert f'data-verbatim="diagnostics/selection_bias.json#caveats[{i}]"' in page
    assert html.escape(diag["interpretation"]) in page
    assert 'data-verbatim="diagnostics/selection_bias.json#interpretation"' in page


def test_report_embeds_whole_json_and_numbers_from_files(tmp_path):
    """O JSON canônico inteiro é embutido (serialização canônica) e números
    exibidos vêm dos arquivos — nada recalculado na camada de UI."""
    run_dir = _make_fake_run(tmp_path)
    page = report.render_run_report(run_dir)
    diag = json.loads(
        (run_dir / "diagnostics" / "selection_bias.json").read_text(encoding="utf-8")
    )
    canonical = json.dumps(diag, ensure_ascii=False, sort_keys=True, indent=2)
    assert html.escape(canonical) in page
    assert "0.1918" in page  # surviving_fraction, direto do JSON
    assert "0.91" in page  # score do ranking.csv, célula crua
    assert html.escape("CAND-001") in page


def test_report_escapes_special_characters_in_caveats(tmp_path):
    """Caracteres especiais nos caveats são escapados (não viram tags)."""
    run_dir = _make_fake_run(tmp_path)
    page = report.render_run_report(run_dir)
    assert "&lt;especiais&gt;" in page
    assert "<especiais>" not in page
    assert "&amp;" in page  # o "&" do caveat escapado


# ---------------------------------------------------------------------------
# runstore: leitura read-only dos artefatos canônicos
# ---------------------------------------------------------------------------


def test_list_runs_surfaces_status_blockers_and_result(tmp_path):
    run_dir = _make_fake_run(tmp_path)
    runs = runstore.list_runs(tmp_path)
    assert [info["run_id"] for info in runs] == [run_dir.name]
    info = runs[0]
    assert info["status"] == "completed"
    assert info["started_at"] == "2026-01-01T00:00:00Z"
    assert info["ended_at"] == "2026-01-01T00:10:00Z"
    assert info["global_result_status"] == "candidato de interesse dentro do protocolo"
    assert len(info["blockers"]) == 1
    assert info["blockers"][0]["blocker_id"] == "etno_catalog_not_fully_validated"


def test_list_runs_ignores_non_run_folders(tmp_path):
    _make_fake_run(tmp_path)
    (tmp_path / "nao_eh_run").mkdir()
    assert [info["run_id"] for info in runstore.list_runs(tmp_path)] == [
        "screen_20260101T000000000000Z"
    ]


def test_lifecycle_status_running_lock_without_marker(tmp_path):
    run_dir = _make_fake_run(tmp_path)
    assert runstore.lifecycle_status(run_dir) == "completed"
    (run_dir / "status.json").unlink()
    (run_dir / "RUNNING.lock").write_text("", encoding="utf-8")
    assert runstore.lifecycle_status(run_dir) == "running"


def test_candidate_progress_prefers_status_then_heartbeat(tmp_path):
    run_dir = _make_fake_run(tmp_path)
    progress = runstore.candidate_progress(run_dir)
    assert progress["source"] == "status.json"
    (run_dir / "status.json").unlink()
    (run_dir / "heartbeat.json").write_text(
        json.dumps({"candidates_done": 2, "candidates_total": 8}), encoding="utf-8"
    )
    progress = runstore.candidate_progress(run_dir)
    assert progress["source"] == "heartbeat.json"
    assert progress["candidates_done"] == 2


def test_progress_info_computes_series_percent_from_checkpoints(tmp_path):
    """A porcentagem da série vem de t_years/integration_years — estimativa
    derivada dos MESMOS arquivos que scripts/watch_progress.py lê."""
    run_dir = _make_fake_run(tmp_path)
    (run_dir / "config.resolved.yaml").write_text(
        "budget:\n  integration_years: 1000.0\n", encoding="utf-8"
    )
    (run_dir / "montecarlo_checkpoints").mkdir()
    (run_dir / "montecarlo_checkpoints" / "cand1_drift_series.csv").write_text(
        "t_years,delta_varpi_deg\n250.0,1.1\n500.0,2.2\n", encoding="utf-8"
    )
    info = runstore.progress_info(run_dir)
    assert info["series"][0]["pct"] == pytest.approx(50.0)
    assert info["heartbeat_present"] is False
    assert info["heartbeat_age_s"] is None


# ---------------------------------------------------------------------------
# restrição de escopo: bind exclusivo em localhost
# ---------------------------------------------------------------------------


def test_server_bind_is_localhost_only(monkeypatch):
    assert config.DEFAULT_HOST == "127.0.0.1"
    assert app_module.HOST == "127.0.0.1"
    app_module._assert_localhost_bind()  # não levanta
    monkeypatch.setattr(app_module, "HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="localhost"):
        app_module._assert_localhost_bind()


# ---------------------------------------------------------------------------
# runner: duplo guardião + lançamento desacoplado (requisito runs longas)
# ---------------------------------------------------------------------------


def test_runner_refuses_blocked_unknown_and_incomplete_launches():
    with pytest.raises(ValueError, match="não permitido"):
        runner.launch("watch")  # bloqueado (visualização de terminal)
    with pytest.raises(ValueError, match="não permitido"):
        runner.launch("comando_inventado")  # fora do schema curado
    with pytest.raises(ValueError, match="--from-run"):
        runner.launch("selection-bias-check", {})  # faltam campos obrigatórios


def test_runner_launches_detached_cli_process_full_lifecycle():
    """Abordagem A (evidência): Popen detached de um subcomando real do
    cli.py (`physics-check`, rápido e sem efeito colateral em runs). O
    processo não pertence ao job object/console do pai (DETACHED_PROCESS |
    CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) — a sobrevivência
    ao fechamento da UI segue dessa criação e é exercida aqui pelo ciclo
    completo: record em `.dashboard/jobs/`, log do processo e `poll`
    marcando finished pelo desaparecimento do PID.
    """
    record = runner.launch("physics-check")
    job_id = record["job_id"]
    try:
        assert Path(record["log_path"]).exists()
        deadline = time.time() + 90.0
        polled: dict = {}
        while time.time() < deadline:
            polled = runner.poll(job_id)
            if polled["finished"]:
                break
            time.sleep(0.5)
        assert polled.get("finished"), "processo detached não terminou no prazo"
        assert "exit code não capturável" in polled["note"]
    finally:
        if not runner.read_job(job_id).get("finished"):
            subprocess.run(  # noqa: S603 - PID fixo do record, sem shell
                ["taskkill", "/PID", str(record["pid"]), "/F"],
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    assert runner.tail(job_id) != "(job não encontrado)"
