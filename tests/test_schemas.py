from pydantic import ValidationError

from planet9lab.schemas import ETNORecord, GiantPlanetRecord, P9Candidate


def raises_validation(factory):
    try:
        factory()
    except ValidationError:
        return True
    return False


def valid_candidate(**overrides):
    data = {
        "candidate_id": "c1",
        "mass_earth": 5,
        "a_au": 500,
        "e": 0.2,
        "i_deg": 20,
        "omega_deg": 150,
        "Omega_deg": 80,
        "mean_anomaly_deg": 0,
    }
    data.update(overrides)
    return P9Candidate.model_validate(data)


def valid_etno(**overrides):
    data = {
        "name": "Sedna",
        "a_au": 506,
        "e": 0.85,
        "i_deg": 12,
        "omega_deg": 311,
        "Omega_deg": 144,
        "mean_anomaly_deg": 3,
        "epoch": "J2000",
        "frame": "heliocentric_ecliptic",
        "source": "fixture",
        "validation_status": "partial",
        "selection_included": True,
        "selection_reason": "criterion",
        "selection_notes": "notes",
    }
    data.update(overrides)
    return ETNORecord.model_validate(data)


def test_candidate_mass_must_be_positive():
    assert raises_validation(lambda: valid_candidate(mass_earth=0))


def test_candidate_e_must_be_less_than_one():
    assert raises_validation(lambda: valid_candidate(e=1))


def test_candidate_angle_range_enforced():
    assert raises_validation(lambda: valid_candidate(omega_deg=360))


def test_etno_epoch_required():
    assert raises_validation(lambda: valid_etno(epoch=""))


def test_etno_frame_required():
    assert raises_validation(lambda: valid_etno(frame=""))


def test_etno_validation_status_enum():
    assert raises_validation(lambda: valid_etno(validation_status="unknown"))


def test_legacy_inc_deg_rejected():
    assert raises_validation(lambda: valid_etno(inc_deg=12))


def test_giant_mass_positive():
    assert raises_validation(
        lambda: GiantPlanetRecord.model_validate(
            {
                "name": "Jupiter",
                "mass_solar": 0,
                "a_au": 5.2,
                "e": 0.05,
                "i_deg": 1,
                "omega_deg": 10,
                "Omega_deg": 20,
                "mean_anomaly_deg": 30,
                "epoch": "J2000",
            }
        )
    )


def test_giant_a_positive():
    assert raises_validation(
        lambda: GiantPlanetRecord.model_validate(
            {
                "name": "Jupiter",
                "mass_solar": 0.001,
                "a_au": 0,
                "e": 0.05,
                "i_deg": 1,
                "omega_deg": 10,
                "Omega_deg": 20,
                "mean_anomaly_deg": 30,
                "epoch": "J2000",
            }
        )
    )

