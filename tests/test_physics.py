from planet9lab.physics import run_physics_checks


def test_physics_check_reports_rebound_key():
    checks = run_physics_checks()
    assert "rebound_available" in checks


def test_physics_check_real_rebound_available_in_acceptance_env():
    checks = run_physics_checks()
    assert checks["rebound_available"] is True


def test_physics_check_core_sanity_passes():
    assert run_physics_checks()["overall_ok"] is True

