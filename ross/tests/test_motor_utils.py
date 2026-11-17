"""Tests for the signal processing functions of ``ross.motors.utils``.

The reference values are analytical:

- a sine has no distortion;
- a square wave has only odd harmonics of amplitude ``1 / k``, so its
  distortion up to harmonic ``n`` is ``sqrt(sum(1 / k**2))`` over the odd
  ``k`` from 3 to ``n``, and tends to ``sqrt(pi**2 / 8 - 1) = 0.4834``;
- a sum of sines has the distortion given by its amplitudes.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ross.motors.utils import fundamental_frequency, total_harmonic_distortion

DT = 1e-5


def time_vector(cycles, frequency):
    return np.arange(0.0, cycles / frequency, DT)


def test_pure_sine_has_no_distortion():
    t = time_vector(12, 60.0)
    thd, f1 = total_harmonic_distortion(np.sin(2 * np.pi * 60 * t), DT, frequency=60.0)
    assert thd < 1e-4
    assert f1 == 60.0


@pytest.mark.parametrize("n_harmonics", [9, 25, 49])
def test_square_wave_distortion_follows_the_odd_harmonics(n_harmonics):
    t = time_vector(12, 60.0)
    signal = np.sign(np.sin(2 * np.pi * 60 * t))
    odd = np.arange(3, n_harmonics + 1, 2)
    expected = np.sqrt(np.sum(1.0 / odd**2))
    thd, _ = total_harmonic_distortion(
        signal, DT, frequency=60.0, n_harmonics=n_harmonics
    )
    assert_allclose(thd, expected, rtol=2e-2)


@pytest.mark.parametrize(
    "amplitudes, orders",
    [([0.1], [5]), ([0.05, 0.03], [5, 7]), ([0.2, 0.1, 0.05], [3, 5, 11])],
)
def test_distortion_of_a_sum_of_sines(amplitudes, orders):
    f1 = 50.0
    t = time_vector(15, f1)
    signal = 3.0 * np.sin(2 * np.pi * f1 * t)
    for a, k in zip(amplitudes, orders, strict=True):
        signal += 3.0 * a * np.sin(2 * np.pi * k * f1 * t + 0.4)
    thd, _ = total_harmonic_distortion(signal, DT, frequency=f1)
    assert_allclose(thd, np.sqrt(np.sum(np.square(amplitudes))), rtol=1e-2)


def test_distortion_ignores_the_offset_and_the_amplitude_scale():
    t = time_vector(12, 60.0)
    base = np.sin(2 * np.pi * 60 * t) + 0.1 * np.sin(2 * np.pi * 300 * t)
    thd_base, _ = total_harmonic_distortion(base, DT, frequency=60.0)
    thd_scaled, _ = total_harmonic_distortion(7.0 * base + 2.0, DT, frequency=60.0)
    assert_allclose(thd_scaled, thd_base, rtol=1e-9)


@pytest.mark.parametrize("frequency", [3.0, 17.3, 60.0, 65.21, 73.3])
def test_fundamental_frequency_is_resolved_below_the_fft_resolution(frequency):
    t = np.arange(0.0, 1.0, DT)
    signal = np.sin(2 * np.pi * frequency * t) + 0.1 * np.sin(
        2 * np.pi * 5 * frequency * t
    )
    assert_allclose(
        fundamental_frequency(signal, DT, search_range=(1.0, 200.0)),
        frequency,
        atol=0.02,
    )


def test_distortion_estimates_the_fundamental_when_it_is_not_given():
    t = time_vector(12, 61.37)
    signal = np.sin(2 * np.pi * 61.37 * t) + 0.1 * np.sin(2 * np.pi * 5 * 61.37 * t)
    thd, f1 = total_harmonic_distortion(signal, DT)
    assert_allclose(f1, 61.37, atol=0.02)
    assert_allclose(thd, 0.1, rtol=2e-2)
