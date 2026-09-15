"""Redesign 2 do dashboard — taxonomia, defaults inteligentes e fluxo real.

Critério de aceite do Auditor: "uma pessoa que não é quem fez o simulador
consegue usar isso sem explicação prévia?". Cobertura:
- Painel (/): 3 cartões principais em linguagem comum + benchmark +
  operações secundárias; NENHUM comando de diagnóstico listado ali;
- aba /testes: os 19 comandos de robustez/diagnóstico/utilidade agrupados;
- taxonomia: todo comando do schema aparece em EXATAMENTE um lugar;
- defaults: --max-workers (hardware real), --run-root e --budget já
  preenchidos — formulário pronto para o 2º clique disparar;
- fluxo completo REAL: /executar/smoke → run concluída → botão de download
  → zip verificado (results/, audit/, relatorio.html, MANIFESTO.txt).
"""

from __future__ import annotations

import asyncio
import io
import time
import zipfile
from pathlib import Path

from dashboard import app as app_module
from dashboard import commands, config, hardware

# ---------------------------------------------------------------------------
# Taxonomia (pura): nada duplicado, nada esquecido
# ---------------------------------------------------------------------------


def test_taxonomy_covers_every_schema_command_exactly_once():
    everywhere = set(app_module._home_command_names()) | set(app_module._tests_command_names())
    assert everywhere == set(commands.COMMAND_NAMES)
    duplicated = set(app_module._home_command_names()) & set(app_module._tests_command_names())
    assert not duplicated, f"comando em dois lugares: {sorted(duplicated)}"


def test_home_primary_uses_common_language_not_raw_cli_names():
    for name, label, _icon, tip in app_module._HOME_PRIMARY:
        assert name not in label, f"cartão {name} usa o nome cru do CLI no rótulo"
        assert len(tip) > 40, f"cartão {name} sem explicação de hover"
    labels = [label for _, label, _, _ in app_module._HOME_PRIMARY]
    assert labels == [
        "Rodar triagem de candidatos",
        "Comparar candidato com/sem Planeta Nove",
        "Varredura Monte Carlo",
    ]


def test_tests_tab_groups_match_the_approved_categorization():
    names = app_module._tests_command_names()
    assert len(names) == 19
    assert len(set(names)) == 19
    assert "smoke" in names and "physics-check" in names
    assert not ({"screen", "compare", "montecarlo-scan", "resume", "report"} & set(names))


# ---------------------------------------------------------------------------
# Defaults inteligentes (puros, sem UI)
# ---------------------------------------------------------------------------


def _args_by_flag(name: str) -> dict[str, dict]:
    return {arg["flag"]: arg for arg in commands.get_command(name)["args"]}


def test_initial_values_max_workers_run_root_budget():
    screen = _args_by_flag("screen")
    assert app_module._initial_value(screen["--max-workers"], []) == hardware.suggest_max_workers()
    assert app_module._initial_value(screen["--run-root"], []) == "runs"
    assert app_module._initial_value(screen["--budget"], []) == "configs/budgets/low.yaml"


def test_initial_values_schema_defaults_and_required_empty():
    screen = _args_by_flag("screen")
    assert app_module._initial_value(screen["--seed"], []) == 12345
    compare = _args_by_flag("compare")
    # obrigatório sem valor óbvio nasce vazio de propósito (nada inventado)
    assert app_module._initial_value(compare["--candidate"], []) is None
    families = _args_by_flag("candidate-families")
    assert app_module._initial_value(families["--top"], []) == 20
    montecarlo = _args_by_flag("montecarlo-scan")
    assert app_module._initial_value(montecarlo["--config"], []) == "configs/montecarlo/parameter_space.yaml"


def test_initial_value_run_selector_prefers_most_recent_run():
    arg = {"flag": "run_dir", "kind": "path_run", "default": None, "required": True, "help": ""}
    assert app_module._initial_value(arg, ["screen_x", "screen_a"]) == "screen_x"
    assert app_module._initial_value(arg, []) is None


# ---------------------------------------------------------------------------
# UI real via nicegui.testing.User (async)
# ---------------------------------------------------------------------------


async def test_home_shows_actions_and_hides_diagnostic_listing(user):
    await user.open("/")
    await user.should_see("O que você quer rodar?")
    await user.should_see("Rodar triagem de candidatos")
    await user.should_see("Comparar candidato com/sem Planeta Nove")
    await user.should_see("Varredura Monte Carlo")
    await user.should_see("Retomar run interrompida")
    await user.should_see("Regenerar relatório de uma run")
    await user.should_see("Rodar benchmark de hardware")
    # comandos de teste/diagnóstico NÃO aparecem no Painel
    await user.should_not_see("leave-one-out")
    await user.should_not_see("physics-check")


async def test_tests_tab_groups_the_diagnostic_commands(user):
    await user.open("/testes")
    await user.should_see("Robustez (7)")
    await user.should_see("Diagnóstico de candidatos e estatística (6)")
    await user.should_see("Sanidade e utilidades do pipeline (6)")


async def test_screen_form_opens_ready_to_run(user):
    await user.open("/executar/screen")
    await user.should_see("Rodar triagem de candidatos")
    await user.should_see("Executar screen")
    await user.should_see("--max-workers")
    await user.should_see("--run-root")
    await user.should_see("--budget")


async def test_benchmark_form_opens_from_home_button(user):
    await user.open("/executar/benchmark")
    await user.should_see("Rodar benchmark de hardware")
    await user.should_see("Executar benchmark")


# ---------------------------------------------------------------------------
# Fluxo completo REAL: disparar smoke → concluir → baixar zip
# ---------------------------------------------------------------------------


async def test_full_flow_launch_smoke_then_download_zip(user, tmp_path, monkeypatch):
    run_root = tmp_path / "runs"
    run_root.mkdir()
    # A listagem do app lê o destino A CADA CHAMADA (config.run_root()).
    monkeypatch.setenv(config.RUN_ROOT_ENV, str(run_root))
    # O campo --run-root pré-preenchido aponta para o tmp (na UI, qualquer
    # usuário sobrescreve; aqui evitamos tocar em runs/ real do repo).
    monkeypatch.setattr(hardware, "suggest_run_root", lambda: str(run_root))

    await user.open("/executar/smoke")
    await user.should_see("Executar smoke")
    user.find(marker="executar-smoke").click()

    # A run roda desacoplada (subprocesso real): esperar o SUCCESS.marker.
    deadline = time.time() + 300
    smoke_dir = None
    while time.time() < deadline:
        candidates = sorted(run_root.glob("smoke_*"))
        if candidates and all((d / "SUCCESS.marker").is_file() for d in candidates):
            smoke_dir = candidates[-1]
            break
        await asyncio.sleep(1.0)
    assert smoke_dir is not None, "run smoke não concluiu dentro do tempo limite"

    await user.open(f"/run/{smoke_dir.name}")
    await user.should_see("Baixar resultados (zip)")
    user.find(marker="download-results").click()
    response = await user.download.next(timeout=30)
    assert response.status_code == 200
    assert response.content[:2] == b"PK"  # assinatura de zip

    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        names = set(bundle.namelist())
        assert "results/ranking.csv" in names
        assert "audit/run_manifest.json" in names
        assert "relatorio.html" in names
        assert "MANIFESTO.txt" in names
        assert not any(name.startswith("checkpoints/") for name in names)

    # O zip também é persistido no estado próprio do dashboard.
    assert (config.DOWNLOADS_DIR / f"{smoke_dir.name}.zip").is_file()

# ---------------------------------------------------------------------------
# Correções dos bugs visuais de 2026-09-14 (evidência: screenshot de
# /run/smoke_...): CSS do relatório removido pelo sanitizador client-side
# e resultado de benchmark inacessível em Jobs.
# ---------------------------------------------------------------------------


def _fake_run_minimo(root: Path) -> Path:
    run_dir = root / "screen_20260101T000000000000Z"
    (run_dir / "results").mkdir(parents=True)
    (run_dir / "diagnostics").mkdir()
    (run_dir / "status.json").write_text(
        '{"status": "completed", "candidates_done": 1, "candidates_total": 2}',
        encoding="utf-8",
    )
    (run_dir / "results" / "ranking.csv").write_text(
        "candidate_id,score,verdict\nCAND-001,0.91,weak\n", encoding="utf-8"
    )
    return run_dir


def test_run_report_fragment_has_no_style_tag_and_wraps_tables(tmp_path):
    """<style> dentro de ui.html é removido pelo DOMPurify (sanitizador
    client-side) — o fragmento da UI não pode contê-lo; o CSS vai no
    <head> via REPORT_CSS (escopado em .p9-report) e as tabelas ficam em
    .table-wrap (scroll horizontal próprio). O doc standalone (zip de
    download) continua self-contained, com o CSS embutido."""
    from dashboard import report

    run_dir = _fake_run_minimo(tmp_path)
    fragment = report.render_run_report_fragment(run_dir)
    assert "<style" not in fragment
    assert 'class="p9-report"' in fragment
    assert 'class="table-wrap"' in fragment
    assert 'data-verbatim="candidate_progress"' in fragment
    doc = report.render_run_report(run_dir)
    assert "<style>" in doc
    assert "p9-report" in doc
    assert report.REPORT_CSS.startswith(".p9-report")


async def test_run_page_uses_fragment(user, tmp_path, monkeypatch):
    """A página /run injeta o fragmento (marcado) e abre sem erro — o
    relatório renderiza DENTRO da página Quasar, formatado pelo CSS do
    head, sem substituir o tema da página."""
    run_root = tmp_path / "runs"
    run_root.mkdir()
    monkeypatch.setenv(config.RUN_ROOT_ENV, str(run_root))
    run_dir = _fake_run_minimo(run_root)
    await user.open(f"/run/{run_dir.name}")
    await user.should_see("Relatório da run")
    await user.should_see("Resultados")
    assert user.find(marker="run-report-fragment") is not None


async def test_benchmark_job_result_is_viewable_in_jobs(user, tmp_path):
    """BUG 2: benchmark não é run de screening — o resultado (JSON) tem de
    ser visível a partir de Jobs, sem tentar aplicar o template científico.
    Dispara um benchmark REAL desacoplado com --output temporário."""
    from dashboard import runner

    output = tmp_path / "bench_result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")  # schema exige caminho existente
    record = runner.launch(
        "benchmark",
        {"--budget": "configs/budgets/low.yaml", "--output": str(output)},
    )
    deadline = time.time() + 180
    while time.time() < deadline and not runner.read_job(record["job_id"]).get(
        "finished"
    ):
        await asyncio.sleep(0.5)
    assert output.is_file(), "benchmark não escreveu o resultado no --output"

    await user.open("/jobs")
    await user.should_see("Resultados de benchmark")
    user.find(marker=f"benchmark-result-{record['job_id']}").click()
    await user.should_see(f"Resultado do benchmark — job {record['job_id']}")
    await user.should_see("simulated_years_per_second")
