from sibyl.pr_analysis.adapters.checks_notifier import _conclusion_for, _title_for


def test_low_score_maps_to_success():
    assert _conclusion_for(0.1, explanation_unavailable=False) == "success"


def test_mid_score_maps_to_neutral():
    assert _conclusion_for(0.5, explanation_unavailable=False) == "neutral"


def test_high_score_maps_to_action_required():
    assert _conclusion_for(0.9, explanation_unavailable=False) == "action_required"


def test_explanation_unavailable_always_maps_to_neutral_regardless_of_score():
    assert _conclusion_for(0.0, explanation_unavailable=True) == "neutral"
    assert _conclusion_for(0.95, explanation_unavailable=True) == "neutral"


def test_title_for_each_conclusion():
    assert _title_for("success") == "Low risk"
    assert _title_for("neutral") == "Moderate risk"
    assert _title_for("action_required") == "High risk — review recommended"
