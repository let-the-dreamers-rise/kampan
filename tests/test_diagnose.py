from kampan.diagnose import diagnose, order_of
from kampan.spectrum import Peak


def test_order_matching():
    assert order_of(40.4, 20.0) == 2.0
    assert order_of(30.0, 20.0) == 1.5
    assert order_of(27.0, 20.0) is None


def test_unbalance_when_one_x_dominates():
    assert diagnose((Peak(20.0, 1.0, 50), Peak(40.0, 0.1, 10)), 20.0).signature == "unbalance"


def test_misalignment_when_two_x_strong():
    assert diagnose((Peak(20.0, 1.0, 50), Peak(40.0, 0.8, 40)), 20.0).signature == "misalignment"


def test_looseness_with_half_orders():
    peaks = (Peak(20.0, 1.0, 50), Peak(30.0, 0.3, 20))
    assert diagnose(peaks, 20.0).signature == "looseness"


def test_unknown_without_running_speed():
    assert diagnose((Peak(20.0, 1.0, 50),), None).signature == "unknown"


def test_none_without_peaks():
    assert diagnose((), 20.0).signature == "none"


def test_unknown_when_no_one_x():
    assert diagnose((Peak(33.0, 1.0, 50),), 20.0).signature == "unknown"
