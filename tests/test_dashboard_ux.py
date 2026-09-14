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
