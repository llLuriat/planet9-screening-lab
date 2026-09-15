"""Testes puros dos helpers do redesign do dashboard (UX em pt-BR).

Contratos cobertos:
- a estimativa de tempo usa o MESMO fator 2 do par com/sem P9 de
  ``engine.run_control_pair`` e de ``benchmark_integration_cost.py``
  (uma branch = horizon/rate; o par = 2 branches);
- o hint do campo ``--budget`` lê o YAML REAL e a taxa REAL de
  ``results/hardware_benchmark.json``; sem esses dados, diz honestamente
  que não há estimativa (nunca inventa número);
- números formatados em pt-BR (vírgula decimal, ponto de milhar).
"""

from __future__ import annotations

from dashboard import app as app_module


def test_pt_num_formats_pt_br():
    assert app_module._pt_num(15.251) == "15,3"
    assert app_module._pt_num(4e9, 0) == "4.000.000.000"
    assert app_module._pt_num(0.5) == "0,5"


def test_pair_hint_uses_the_same_factor_two_as_the_control_pair():
    """4 Gyr ÷ 145.708,8737 anos/s = 7,63 h por branch; o par = 15,25 h."""
    text = app_module._pair_hint_text(4e9, 145708.8737)
    assert "15,3 h" in text  # par com/sem P9, single-core
    assert "122 h" in text  # 8 candidatos em série


def test_time_hint_for_secular_budget_reads_real_repo_files():
    """Integração real: secular.yaml (4e9) + hardware_benchmark.json do repo."""
    text = app_module._time_hint_text("configs/budgets/secular.yaml")
    assert text.startswith("secular — 4 Gyr")
    assert "Horizonte de 4.000.000.000 anos" in text
    assert "Par com/sem P9" in text


def test_time_hint_without_measured_rate_is_honest(monkeypatch):
    monkeypatch.setattr(app_module, "_measured_years_per_second", lambda: None)
    text = app_module._time_hint_text("configs/budgets/secular.yaml")
    assert "Sem estimativa de tempo" in text
    assert "benchmark_integration_cost.py" in text


def test_time_hint_for_unknown_budget_has_no_invented_estimate():
    text = app_module._time_hint_text("configs/budgets/nao_existe.yaml")
    assert "não foi possível ler integration_years" in text
    assert "Horizonte de" not in text


# ---------------------------------------------------------------------------
# Proveniência obrigatória nas estimativas + montecarlo-scan (pior caso
# calculável; honesto quando não é) — requisito do Auditor, 2026-09-15.
# ---------------------------------------------------------------------------


def test_time_hint_carries_measurement_provenance():
    """Toda estimativa declara a fonte real: data da medição, taxa e o aviso
    de que não é número universal."""
    text = app_module._time_hint_text("configs/budgets/secular.yaml")
    assert "medição REAL desta máquina" in text
    assert "anos/s" in text
    assert "não é um número universal" in text


def test_screen_hint_differs_per_budget():
    """A estimativa recalcula por budget: low (< 1 min) vs secular (horas)."""
    low = app_module._time_hint_text("configs/budgets/low.yaml")
    secular = app_module._time_hint_text("configs/budgets/secular.yaml")
    assert low != secular
    assert "menos de 1 min" in low
    assert "Par com/sem P9" in secular


def test_montecarlo_hint_worst_case_from_real_yaml():
    """Cotas de pior caso VÊM DO YAML REAL (200/2) e do budget real
    (montecarlo_stage2 1e6 + secular 4e9), com multiplicador de 1 branch por
    amostra (do código) — e declaram que o total exato não é estimável."""
    text = app_module._montecarlo_scan_hint_text(
        "configs/montecarlo/parameter_space.yaml"
    )
    assert "PIOR CASO" in text
    assert "200 amostras" in text
    assert "2 amostra(s)" in text
    assert "fração de pontos" in text
    assert "não é estimável" in text
    assert "medição REAL desta máquina" in text


def test_montecarlo_hint_without_rate_is_honest(monkeypatch):
    monkeypatch.setattr(app_module, "_measured_years_per_second", lambda: None)
    text = app_module._montecarlo_scan_hint_text(
        "configs/montecarlo/parameter_space.yaml"
    )
    assert "Estimativa não disponível" in text
    assert "benchmark_integration_cost.py" in text


def test_montecarlo_hint_unknown_config_is_honest():
    text = app_module._montecarlo_scan_hint_text("configs/montecarlo/nao_existe.yaml")
    assert "Estimativa não disponível" in text
    assert "Horizonte" not in text
