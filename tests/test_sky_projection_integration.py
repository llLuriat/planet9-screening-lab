"""Integração da projeção orbital→céu no pipeline de viés de seleção.

Autorizada pelo usuário em 2026-09-26 (Rodada 2 — Tarefa B, item (a)).
Estes testes travam o NOVO contrato de
``generate_synthetic_population``/``selection_bias_check``:

- posição de céu = projeção orbital→céu REAL na época do catálogo
  (planet9lab.geometry.sky_projection), não o proxy uniforme antigo;
- convenção de elementos DECLARADA (varpi amostrado, Omega = varpi − omega,
  i prógrado-isotrópico, M uniforme) — ver docstring de
  ``generate_synthetic_population``;
- r_au/delta_au vindos da MESMA geometria projetada na MESMA época;
- ``use_ossos_footprint`` continua opt-in (default false, inalterado).

Nenhum teste aqui é relaxado em relação ao estado anterior: os testes
antigos de raio/ângulo/determinismo continuam no arquivo de origem.
"""

import inspect
import math
import random

from planet9lab.geometry.sky_projection import (
    DEFAULT_EPOCH_JD,
    orbital_elements_to_sky,
)
from planet9lab.loaders import load_etnos
from planet9lab.metrics import normalize_degrees
from planet9lab.selection_bias import (
    SKY_PROJECTION_EPOCH_JD,
    SKY_PROJECTION_EPOCH_UTC,
    generate_synthetic_population,
    load_bias_config,
    load_h_catalog,
    selection_bias_check,
)

REAL_ETNO_CATALOG = "data/etnos/catalog_validated.csv"
SEED = 20260926


def _population(n=3000):
    """População com os mesmos priors do run canônico (H do SBDB + q do catálogo)."""
    h_values = [h for _, h in load_h_catalog("data/etnos/h_values.csv")]
    from planet9lab.selection_bias import _load_q_prior

    q_values = _load_q_prior(REAL_ETNO_CATALOG)
    return generate_synthetic_population(
        random.Random(SEED), n, h_prior_values=h_values, q_prior_values=q_values
    )


def test_population_positions_equal_direct_projection_at_catalog_epoch():
    """Posição de céu de cada objeto É a projeção dos SEUS elementos na época
    escolhida (igualdade exata, bit-a-bit). Se qualquer caminho voltar a
    desenhar posição por sorteio (proxy uniforme) ou usar outra época, esta
    igualdade deixa de valer."""
    pop = _population(n=8)
    for row in pop:
        ra, dec, delta, r = orbital_elements_to_sky(
            row["a_au"],
            row["e"],
            row["i_deg"],
            row["omega_deg"],
            row["Omega_deg"],
            row["mean_anomaly_deg"],
            epoch_jd=SKY_PROJECTION_EPOCH_JD,
        )
        assert ra == row["ra_deg"]
        assert dec == row["dec_deg"]
        assert delta == row["delta_au"]
        assert r == row["r_au"]


def test_projection_epoch_is_the_catalog_epoch_constant():
    """Época da projeção = JD 2456800.5 = 2014-05-23, a época dos objetos
    validados do catálogo real (De la Fuente Marcos & De la Fuente Marcos
    2014, Tabela A1) — decisão documentada em selection_bias.py e no Log."""
    assert SKY_PROJECTION_EPOCH_JD == DEFAULT_EPOCH_JD
    assert SKY_PROJECTION_EPOCH_JD == 2456800.5
    assert SKY_PROJECTION_EPOCH_UTC == "2014-05-23"


def test_varpi_constraint_omega_plus_omega_exact():
    """Convenção de elementos (decisão 2026-09-26): varpi é a variável
    amostrada e Omega = (varpi − omega) mod 360 — a relação ω+Ω=varpi vale
    exatamente em cada linha até o erro de ponto flutuante do roundtrip
    subtração→adição (1 ULP; tolerância circular 1e-9 graus)."""
    pop = _population(n=500)
    for row in pop:
        recomputed = normalize_degrees(row["omega_deg"] + row["Omega_deg"])
        diff = abs(recomputed - row["varpi_deg"])
        assert min(diff, 360.0 - diff) < 1e-9
        assert 0.0 <= row["omega_deg"] < 360.0
        assert 0.0 <= row["Omega_deg"] < 360.0
        assert 0.0 <= row["varpi_deg"] < 360.0


def test_varpi_distribution_matches_uniform_null():
    """varpi (a grandeza sob teste) segue o nulo uniforme: R circular da
    amostragem grande fica perto de 0 (limiar folgado; seed fixa ⇒
    determinístico)."""
    pop = _population(n=3000)
    varpis = [row["varpi_deg"] for row in pop]
    sum_cos = sum(math.cos(math.radians(a)) for a in varpis)
    sum_sin = sum(math.sin(math.radians(a)) for a in varpis)
    resultant = math.hypot(sum_cos, sum_sin) / len(varpis)
    assert resultant < 0.05


def test_inclination_prograde_isotropic():
    """Convenção de elementos: i prógrado-isotrópico (cos i ~ U(0,1) →
    i ∈ [0, 90]). Todo i cai em [0, 90] e a média de cos(i) ≈ 0,5 (nula
    isotrópica, não um ajuste aos dados)."""
    pop = _population(n=1000)
    inclinations = [row["i_deg"] for row in pop]
    assert all(0.0 <= i <= 90.0 for i in inclinations)
    mean_cos_i = sum(math.cos(math.radians(i)) for i in inclinations) / len(inclinations)
    assert 0.40 <= mean_cos_i <= 0.60


def test_distances_coherent_with_projected_geometry():
    """r_au e delta_au vêm da MESMA geometria projetada: pela desigualdade
    triangular, |Δ − r| ≤ |Sol→Terra| na época (r_earth ≈ 1,0126 UA em
    2014-05-23). O stand-in antigo Δ = r + U(−1, 1) violaria este vínculo
    com a posição projetada (e era exatamente o que este teste pina)."""
    from planet9lab.geometry.sky_projection import _earth_heliocentric_ecliptic

    ex, ey, ez = _earth_heliocentric_ecliptic(SKY_PROJECTION_EPOCH_JD)
    r_earth = math.sqrt(ex**2 + ey**2 + ez**2)
    pop = _population(n=500)
    for row in pop:
        assert row["r_au"] > 0
        assert row["delta_au"] > 0
        assert abs(row["delta_au"] - row["r_au"]) <= r_earth + 1e-9


def test_sky_positions_always_present_and_no_proxy_flag():
    """Contrato novo: todo objeto carrega ra_deg/dec_deg (mesmo sem priors) e
    a assinatura NÃO tem mais o flag ``generate_sky_position`` — não sobrou
    caminho que desenhe o proxy uniforme."""
    pop = generate_synthetic_population(random.Random(SEED), n=50)
    for row in pop:
        assert 0.0 <= row["ra_deg"] < 360.0
        assert -90.0 <= row["dec_deg"] <= 90.0
    assert "generate_sky_position" not in inspect.signature(
        generate_synthetic_population
    ).parameters


def test_position_distribution_sanity_differs_from_uniform_dec_proxy():
    """Sanidade da distribuição de posições (seed fixa): RA cobre o círculo
    inteiro, Dec fica em faixa plausível e a MÉDIA de |Dec| ≈ 32,7° — bem
    abaixo dos 45° que o proxy uniforme em declinação antigo produziria
    (distingue projeção real do proxy estatisticamente, com folga)."""
    pop = _population(n=3000)
    decs = [row["dec_deg"] for row in pop]
    ras = [row["ra_deg"] for row in pop]
    mean_abs_dec = sum(abs(d) for d in decs) / len(decs)
    assert min(ras) < 20.0 and max(ras) > 340.0  # círculo cheio coberto
    assert 15.0 <= mean_abs_dec <= 40.0  # proxy uniforme em dec daria ≈ 45
    assert all(-90.0 <= d <= 90.0 for d in decs)


def test_footprint_opt_in_contract_intact():
    """Contrato do opt-in (item 4d da Rodada 2): default continua OFF na
    config e no YAML — a ativação continuaria colapsando a amostra
    (~0,07% da esfera) e agora também carrega a tensão de época declarada."""
    config = load_bias_config("configs/science/observational_bias.yaml")
    assert config.use_ossos_footprint is False
    yaml_text = open(
        "configs/science/observational_bias.yaml", encoding="utf-8"
    ).read()
    assert "use_ossos_footprint: false" in yaml_text


def test_selection_bias_check_reports_projection_provenance():
    """O resultado do check declara a projeção usada (método, época JD e
    data) e mantém o modo padrão uniform_filling_factor — proveniência
    auditável da integração dentro do próprio artefato."""
    etnos = load_etnos(REAL_ETNO_CATALOG)
    config = load_bias_config("configs/science/observational_bias.yaml")
    config = config.model_copy(update={"n_synthetic": 300})
    result = selection_bias_check(etnos, config, seed=12345)
    proj = result["sky_projection"]
    assert proj["epoch_jd"] == 2456800.5
    assert proj["epoch_utc"] == "2014-05-23"
    assert "orbital_elements_to_sky" in proj["method"]
    assert result["ossos_footprint_mode"] == "uniform_filling_factor"
