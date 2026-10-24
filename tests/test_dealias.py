import pytest

from kampan.dealias import alias_of, best_next_rate, dealias


def test_alias_of_below_nyquist_is_identity():
    assert alias_of(50.0, 240.0) == pytest.approx(50.0)


def test_alias_of_above_nyquist_folds():
    assert alias_of(140.0, 240.0) == pytest.approx(100.0)
    assert alias_of(250.0, 240.0) == pytest.approx(10.0)


def test_two_rates_recover_true_frequency():
    true_f = 140.0
    obs = [(240.0, alias_of(true_f, 240.0)), (50.0, alias_of(true_f, 50.0))]
    result = dealias(obs, f_max=230.0, tol_hz=0.5)
    assert result.frequency_hz == pytest.approx(140.0, abs=0.5)
    assert not result.ambiguous


def test_divisor_rates_cannot_separate_mirror_frequencies():
    obs = [(240.0, alias_of(140.0, 240.0)), (120.0, alias_of(140.0, 120.0))]
    assert dealias(obs, f_max=230.0, tol_hz=0.5).ambiguous


def test_best_next_rate_picks_a_separating_rate():
    candidates = (100.0, 140.0)
    assert best_next_rate(candidates, (30.0, 60.0, 120.0, 50.0), tol_hz=1.0) == 50.0


def test_best_next_rate_none_when_no_rate_separates():
    assert best_next_rate((100.0, 140.0), (30.0, 60.0, 120.0), tol_hz=1.0) is None


def test_single_rate_is_ambiguous():
    result = dealias([(240.0, 100.0)], f_max=500.0, tol_hz=0.5)
    assert result.ambiguous
    assert result.frequency_hz == pytest.approx(100.0)


def test_inconsistent_observations_report_no_solution():
    result = dealias([(240.0, 100.0), (120.0, 37.0)], f_max=200.0, tol_hz=0.2)
    assert result.frequency_hz is None
