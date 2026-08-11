from planet9lab.metrics import (
    anti_alignment_score,
    circular_resultant_length,
    dynamic_score,
    ranking_summary,
)


def test_clustering_identical_angles_near_one():
    assert circular_resultant_length([10, 10, 10]) > 0.999


def test_clustering_spread_angles_lower():
    assert circular_resultant_length([0, 90, 180, 270]) < 0.01


def test_anti_alignment_180_high():
    assert anti_alignment_score([180], 0) > 0.99


def test_alignment_zero_low():
    assert anti_alignment_score([0], 0) < 0.01


def test_score_between_zero_and_one():
    score = dynamic_score(
        {
            "apsidal_clustering_R": 0.5,
            "anti_alignment_score": 0.5,
            "survival_rate": 1,
            "stability_score": 1,
            "numerical_health_score": 1,
        },
        {
            "apsidal_clustering": 0.2,
            "anti_alignment": 0.25,
            "survival_rate": 0.2,
            "stability": 0.2,
            "numerical_health": 0.15,
        },
    )
    assert 0 <= score <= 1


def test_delta_summary_uses_with_minus_without():
    rows = [{"operational_status": "completed", "scientific_status": "weak_candidate", "delta_dynamic_score": "0.2"}]
    assert ranking_summary(rows)["top1_delta_score"] == 0.2


def test_ranking_summary_detects_least_bad_only():
    rows = [
        {"operational_status": "completed", "scientific_status": "rejected", "delta_dynamic_score": "-0.1"},
        {"operational_status": "completed", "scientific_status": "rejected", "delta_dynamic_score": "-0.2"},
    ]
    assert ranking_summary(rows)["top1_distinctness"] == "least_bad_only"

