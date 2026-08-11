from planet9lab.policy import classify_candidate, observational_bias_blockers, validate_claim_policy
from planet9lab.schemas import ALLOWED_CLAIMS

WEIGHTS = {"min_survival_rate": 0.8, "min_delta_of_interest": 0.08, "bad_delta_threshold": 0.0}


def test_bias_none_creates_blocker():
    blockers = observational_bias_blockers({"bias_model": "none", "blocker_if_none": True})
    assert blockers[0]["blocker_id"] == "no_observational_bias_model"


def test_nan_delta_invalid():
    assert classify_candidate(float("nan"), 1, WEIGHTS)[0] == "invalid"


def test_missing_control_invalid():
    assert classify_candidate(0.1, 1, WEIGHTS, control_complete=False)[0] == "invalid"


def test_low_delta_rejected():
    assert classify_candidate(-0.1, 1, WEIGHTS)[0] == "rejected"


def test_good_delta_candidate_of_interest():
    assert classify_candidate(0.2, 1, WEIGHTS)[0] == "candidate_of_interest"


def test_claim_policy_blocks_discovery_terms():
    validate_claim_policy()
    for claim in ALLOWED_CLAIMS:
        if claim == "no_candidate_found":
            continue
        assert "confirmed" not in claim
        assert "found" not in claim
        assert "discovered" not in claim
        assert "proved" not in claim

