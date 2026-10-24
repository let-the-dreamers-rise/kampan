import math

import pytest

from kampan.severity import iso_zone, velocity_rms_mm_s
from kampan.spectrum import Peak


def test_velocity_from_displacement_peaks():
    # 0.01 mm peak displacement at 25 Hz -> v_peak = 2*pi*25*0.01 mm/s, rms = /sqrt(2)
    peaks = (Peak(25.0, 0.01, 50.0),)
    expected = 2 * math.pi * 25 * 0.01 / math.sqrt(2)
    assert velocity_rms_mm_s(peaks, f_min=10.0, f_max=1000.0) == pytest.approx(expected)


def test_velocity_ignores_out_of_band_peaks():
    peaks = (Peak(5.0, 1.0, 50.0), Peak(25.0, 0.01, 50.0))
    in_band_only = velocity_rms_mm_s((Peak(25.0, 0.01, 50.0),), 10.0, 1000.0)
    assert velocity_rms_mm_s(peaks, 10.0, 1000.0) == pytest.approx(in_band_only)


@pytest.mark.parametrize("v,zone", [(0.5, "A"), (1.0, "B"), (3.0, "C"), (6.0, "D")])
def test_class_one_zones(v, zone):
    assert iso_zone(v, machine_class="I").zone == zone


def test_large_machine_class_has_higher_limits():
    assert iso_zone(3.0, machine_class="III").zone == "B"


def test_unknown_class_rejected():
    with pytest.raises(ValueError):
        iso_zone(1.0, machine_class="V")
