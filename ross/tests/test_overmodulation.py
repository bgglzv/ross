"""Tests for the Bose overmodulation of the two-level SVPWM.

The modulation index is ``m = |v| / (2 Vdc / pi)``. The linear region ends at
``M1 = pi / (2 sqrt(3))``, mode I at ``M2 = sqrt(3) / 2 ln(3)`` and mode II at
the six-step operation (``m = 1``). The reference values are analytical:

- the fundamental of the applied voltage equals the reference for any ``m``
  up to 1, which is the criterion that defines the method;
- in six-step operation the vector sits on the hexagon vertices, with module
  2/3 of the DC link voltage;
- the applied vector is continuous across the mode boundaries.

Reference: Mondal, Bose, Oleschuk and Pinto, IEEE Trans. Power Electron.,
18(2), 2003.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ross.motors.motor_drive import InverterVF
from ross.motors.overmodulation import (
    M1,
    M2,
    alpha_h_from_m,
    bose_vector,
    hexagon_radius,
    theta_from_m,
)
from ross.units import Q_

VDC = 540.0
SIX_STEP = 2 / np.pi


def fundamental_gain(m, n=7200):
    """Gain of the fundamental of the applied voltage for a circular reference."""
    theta = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    v = m * SIX_STEP * VDC
    applied = np.array(
        [bose_vector(v * np.cos(th), v * np.sin(th), VDC)[:2] for th in theta]
    )
    c1 = np.mean((applied[:, 0] + 1j * applied[:, 1]) * np.exp(-1j * theta))
    return abs(c1) / v


def make_inverter(**kwargs):
    return InverterVF(
        voltage_dc=296.96,
        frequency_s=Q_(5000, "Hz"),
        voltage_rated=220.0,
        frequency_rated=Q_(60, "Hz"),
        **kwargs,
    )


def test_boundaries_of_the_modes():
    assert_allclose(M1, np.pi / (2 * np.sqrt(3)))
    assert_allclose(M2, np.sqrt(3) / 2 * np.log(3))
    assert_allclose(theta_from_m(M1), np.pi / 6, atol=1e-6)
    assert_allclose(theta_from_m(M2), 0.0, atol=1e-6)
    assert_allclose(alpha_h_from_m(M2), 0.0, atol=1e-6)
    assert_allclose(alpha_h_from_m(1.0), np.pi / 6, atol=1e-6)


def test_hexagon_radius_at_vertex_and_side_midpoint():
    assert_allclose(hexagon_radius(0.0), 2 / 3)
    assert_allclose(hexagon_radius(np.pi / 6), 1 / np.sqrt(3))


def test_linear_region_is_unchanged():
    assert bose_vector(100.0, 0.0, VDC) == (100.0, 0.0, 0)


@pytest.mark.parametrize("m", [0.2, 0.5, 0.9, 0.91, 0.93, 0.95, 0.97, 0.99, 1.0])
def test_applied_fundamental_follows_the_reference(m):
    assert_allclose(fundamental_gain(m), 1.0, atol=5e-4)


def test_hexagon_clipping_loses_fundamental():
    """Without compensation the clipped vector gives a gain below one."""
    theta = np.linspace(0, 2 * np.pi, 7200, endpoint=False)
    v = 0.94 * SIX_STEP
    clipped = np.minimum(v, hexagon_radius(np.mod(theta, np.pi / 3)))
    assert np.mean(clipped) / v < 0.995


@pytest.mark.parametrize("boundary", [M1, M2])
def test_applied_voltage_is_continuous_at_mode_boundaries(boundary):
    theta = np.linspace(0.01, 2 * np.pi, 997)
    applied = []
    for dm in (-1e-10, 1e-10):
        v = (boundary + dm) * SIX_STEP * VDC
        applied.append(
            [bose_vector(v * np.cos(th), v * np.sin(th), VDC)[:2] for th in theta]
        )
    assert np.max(np.abs(np.array(applied[0]) - np.array(applied[1]))) < 0.01


@pytest.mark.parametrize("m, mode", [(0.5, 0), (0.93, 1), (0.97, 2), (1.3, 3)])
def test_mode_follows_the_modulation_index(m, mode):
    v = m * SIX_STEP * VDC
    assert bose_vector(v, 0.0, VDC)[2] == mode


def test_over_unity_reference_is_limited_to_six_step():
    theta = np.linspace(0, 2 * np.pi, 3600, endpoint=False)
    v = 1.3 * SIX_STEP * VDC
    for th in theta:
        va, vb, mode = bose_vector(v * np.cos(th), v * np.sin(th), VDC)
        assert mode == 3
        assert_allclose(np.hypot(va, vb), 2 / 3 * VDC, rtol=1e-9)
        angle = np.degrees(np.arctan2(vb, va)) % 60
        assert min(angle, 60 - angle) < 1e-6


def test_mode_two_holds_the_vector_at_the_vertex():
    """In mode II the vector stays at a vertex (module 2/3 of Vdc) while the
    reference angle is within the holding angle of the sector start."""
    m = 0.98
    hold = alpha_h_from_m(m)
    v = m * SIX_STEP * VDC
    for fraction in (0.1, 0.5, 0.9):
        th = fraction * hold
        va, vb, mode = bose_vector(v * np.cos(th), v * np.sin(th), VDC)
        assert mode == 2
        assert_allclose(np.hypot(va, vb), 2 / 3 * VDC, rtol=1e-9)
        assert_allclose(np.arctan2(vb, va), 0.0, atol=1e-9)


@pytest.mark.parametrize("m", [0.5, 0.93, 0.97, 1.0, 1.2])
def test_duty_cycles_are_feasible(m):
    inverter = make_inverter()
    v = m * SIX_STEP * 296.96
    theta = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    for th in theta:
        duty = inverter._duty_cycles(
            v * np.cos(th),
            v * np.cos(th - 2 * np.pi / 3),
            v * np.cos(th + 2 * np.pi / 3),
        )
        assert duty.min() >= 0 and duty.max() <= 1


def test_duty_cycles_do_not_depend_on_overmodulation_in_the_linear_region():
    with_bose = make_inverter()
    without_bose = make_inverter(overmodulation=False)
    v = 0.8 * SIX_STEP * 296.96
    for th in np.linspace(0, 2 * np.pi, 120, endpoint=False):
        refs = (
            v * np.cos(th),
            v * np.cos(th - 2 * np.pi / 3),
            v * np.cos(th + 2 * np.pi / 3),
        )
        assert_allclose(with_bose._duty_cycles(*refs), without_bose._duty_cycles(*refs))
