"""Tests for the held-duty SVPWM, the V/f and the FOC inverters.

The reference values are analytical:

- the average of the phase voltage over a switching period equals the reference
  (volt-second balance) in the linear region;
- with the Bose overmodulation, the fundamental of the period-average voltage of a
  circular reference equals the reference up to six-step operation, where it is
  ``2 V_dc / pi``;
- the V/f angle is the discrete integral of the frequency, which follows the
  continuous integral of the ramp;
- the PI gains follow the bandwidth method, ``kp = 2 pi L (BWp + BWi)``.

The motor is the one of ``motor_example()``.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ross.motors.motor_drive import InverterFOC, InverterVF
from ross.motors.motor_element import motor_example
from ross.units import Q_

VDC = 311.09
FS = Q_(5000, "Hz")
TS = 1 / 5000


def hz(value):
    return Q_(value, "Hz").to("rad/s").m


def make_vf(**kwargs):
    return InverterVF(
        voltage_dc=VDC,
        frequency_s=FS,
        voltage_rated=220.0,
        frequency_rated=Q_(60, "Hz"),
        **kwargs,
    )


def make_foc(**kwargs):
    options = dict(
        voltage_dc=VDC,
        frequency_s=hz(5000),
        voltage_rated=220.0,
        frequency_rated=hz(60),
        n_poles=4,
        speed_rated=Q_(1710, "RPM").to("rad/s").m,
        torque_rated=6.16,
        stator_resistance=2.5,
        rotor_resistance=1.8,
        stator_reactance=1.3,
        rotor_reactance=1.3,
        mutual_reactance=43.08,
        Ip_motor=0.0372,
        time_ramp=0.6667,
        frequency_ref=hz(60),
    )
    options.update(kwargs)
    return InverterFOC(**options)


def period_average(inverter, va_ref, vb_ref, vc_ref, n_samples):
    """Average pole-to-neutral voltages of one switching period."""
    inverter.initialize_control_state(dt=TS / n_samples)
    voltages = np.array(
        [
            inverter._svpwm(0.0, va_ref, vb_ref, vc_ref)
            if k == 0
            else inverter._svpwm(0.0, 0.0, 0.0, 0.0)
            for k in range(n_samples)
        ]
    )
    return voltages.mean(axis=0)


def three_phase(peak, angle):
    return (
        peak * np.cos(angle),
        peak * np.cos(angle - 2 * np.pi / 3),
        peak * np.cos(angle + 2 * np.pi / 3),
    )


@pytest.mark.parametrize("angle", np.linspace(0, 2 * np.pi, 13)[:-1])
def test_period_average_voltage_equals_the_reference_in_the_linear_region(angle):
    inverter = make_vf()
    refs = three_phase(0.8 * VDC / np.sqrt(3), angle)
    average = period_average(inverter, *refs, n_samples=1000)
    assert_allclose(average, refs, atol=0.6)


def test_duty_cycles_are_held_during_the_switching_period():
    """The references of the calls after the first one are ignored."""
    held = make_vf()
    changing = make_vf()
    n_samples = 50
    held.initialize_control_state(dt=TS / n_samples)
    changing.initialize_control_state(dt=TS / n_samples)
    refs = three_phase(0.7 * VDC / np.sqrt(3), 0.4)
    assert held._svpwm(0.0, *refs) == changing._svpwm(0.0, *refs)
    for k in range(1, n_samples):
        other = three_phase(0.1 + 0.2 * k, 2.0 + k)
        assert held._svpwm(0.0, 0.0, 0.0, 0.0) == changing._svpwm(0.0, *other)


def test_time_step_must_divide_the_switching_period():
    inverter = make_vf()
    with pytest.raises(ValueError, match="multiple of the time step"):
        inverter.initialize_control_state(dt=TS / 7.3)


@pytest.mark.parametrize("m", [0.5, 0.8, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0])
def test_bose_fundamental_equals_the_reference_up_to_six_step(m):
    """Fundamental of the period-average voltage of a circular reference.

    ``m = |v| / (2 V_dc / pi)``, with the six-step operation at ``m = 1``.
    """
    inverter = make_vf()
    angles = np.linspace(0, 2 * np.pi, 1440, endpoint=False)
    peak = m * 2 * VDC / np.pi
    S, T1, T2, T0, _ = zip(
        *[inverter._dwell_times(*three_phase(peak, angle)) for angle in angles],
        strict=True,
    )
    phase_a = []
    for angle, s, t1, t2, t0 in zip(angles, S, T1, T2, T0, strict=True):
        vectors = np.array([inverter.V0, *inverter.actv_vet[s - 1], inverter.V7]) - 1
        times = np.array([t0 / 2, t1, t2, t0 / 2])
        poles = VDC * (inverter.sw_table[:, vectors] @ times) / TS
        poles -= poles.mean()
        phase_a.append(poles[0])
    phase_a = np.array(phase_a)
    fundamental = 2 * np.mean(phase_a * np.cos(angles))
    assert_allclose(fundamental, peak, rtol=2e-3)


def test_six_step_fundamental_is_two_vdc_over_pi():
    inverter = make_vf()
    angles = np.linspace(0, 2 * np.pi, 1440, endpoint=False)
    peak = 1.4 * 2 * VDC / np.pi
    phase_a = []
    for angle in angles:
        s, t1, t2, t0, _ = inverter._dwell_times(*three_phase(peak, angle))
        assert t0 == 0
        assert np.isclose(t1, TS) or np.isclose(t2, TS)
        vectors = np.array([inverter.V0, *inverter.actv_vet[s - 1], inverter.V7]) - 1
        poles = VDC * (inverter.sw_table[:, vectors] @ np.array([0, t1, t2, 0])) / TS
        phase_a.append(poles[0] - poles.mean())
    fundamental = 2 * np.mean(np.array(phase_a) * np.cos(angles))
    assert_allclose(fundamental, 2 * VDC / np.pi, rtol=2e-3)


def test_vf_angle_is_the_integral_of_the_frequency():
    inverter = make_vf(frequency_ref=Q_(60, "Hz"), time_ramp=0.6667)
    inverter.initialize_control_state(dt=TS, theta_0=-np.pi / 2)
    f_ref = hz(60)
    n_periods = 6000
    for k in range(n_periods):
        inverter.get_current_state(k * TS, -np.pi / 2)
    ramp_periods = np.arange(1, n_periods + 1)
    frequency = np.minimum(ramp_periods * TS * f_ref / 0.6667, f_ref)
    expected = np.sum(frequency * TS)
    assert_allclose(inverter.control_state["theta"], expected % (2 * np.pi), atol=1e-9)

    time = n_periods * TS
    continuous = f_ref * (time - 0.6667 / 2)
    assert abs(expected - continuous) < f_ref * TS


def test_vf_does_not_limit_the_frequency_to_the_rated_one():
    inverter = make_vf(frequency_ref=Q_(66, "Hz"), time_ramp=0.5)
    assert_allclose(inverter.get_frequency(10.0), hz(66))
    assert inverter.speed_control(hz(66)) == inverter.voltage_phase_peak_rated


def test_foc_loops_run_once_per_switching_period():
    inverter = make_foc()
    n_samples = 20
    inverter.initialize_control_state(dt=TS / n_samples)
    speed = 100.0
    w_first, *_ = inverter.get_current_state(0.0, TS / n_samples, speed, 0.0, 0.0, 0.0)
    for k in range(1, n_samples):
        w_sync, *_ = inverter.get_current_state(
            k * TS / n_samples, TS / n_samples, speed + 5 * k, 1.0 * k, -2.0, 3.0
        )
        assert w_sync == w_first
    w_next, *_ = inverter.get_current_state(
        TS, TS / n_samples, speed + 200, 0.0, 0.0, 0.0
    )
    assert w_next != w_first


def test_foc_speed_reference_ramps_at_the_rated_speed_rate_without_a_limit():
    inverter = make_foc()
    inverter.initialize_control_state(dt=TS)
    step = inverter.speed_rated * TS / 0.6667
    first = inverter.speed_control(0.0, hz(60))
    assert_allclose(first, step)
    for _ in range(20000):
        w_ramp = inverter.speed_control(0.0, hz(60))
    assert_allclose(w_ramp, hz(60) / 2)
    assert w_ramp > inverter.speed_rated


def test_foc_speed_reference_ramps_down():
    inverter = make_foc()
    inverter.initialize_control_state(dt=TS)
    for _ in range(20000):
        inverter.speed_control(0.0, hz(60))
    step = inverter.speed_rated * TS / 0.6667
    assert_allclose(inverter.speed_control(0.0, hz(30)), hz(60) / 2 - step, rtol=1e-12)


def test_foc_d_axis_gains_use_the_equivalent_leakage_inductance():
    motor = motor_example()
    inverter = make_foc()
    Lm = 43.08 / hz(60)
    Lss = 1.3 / hz(60) + Lm
    Lrr = Lss
    Ls1 = Lss - Lm**2 / Lrr
    bandwidth = 5000 / 8
    assert_allclose(inverter.kp_ids, Ls1 * 2 * np.pi * 2 * bandwidth)
    assert_allclose(inverter.ki_ids, Ls1 * 4 * np.pi**2 * bandwidth**2)
    assert_allclose(inverter.kp_iqs, 2 * np.pi * Ls1 * bandwidth)
    assert motor.T_rated > 0


def test_foc_current_bandwidth_is_reduced_above_the_rated_frequency():
    base = make_foc(frequency_ref=hz(60))
    above = make_foc(frequency_ref=hz(66))
    assert_allclose(above.kp_ids / base.kp_ids, 0.8)
    assert_allclose(above.ki_ids / base.ki_ids, 0.8**2)
    assert_allclose(above.kp_iqs / base.kp_iqs, 0.8)
    assert_allclose(above.ki_w / base.ki_w, 0.8**2)


def test_foc_magnetizing_current_is_an_input():
    assert make_foc(ids_ref=3.2).ids_ref == 3.2
    default = make_foc()
    assert default.ids_ref != 3.2 and default.ids_ref > 0


def test_foc_q_axis_current_is_limited_to_three_times_rated_current():
    """Start-up current limit, ported from ``feature-motor``/``feature-motor-
    bose``: the q-axis (torque-producing) current reference is clipped to
    3x the rated stator current magnitude, bounding the inrush current and
    the electromagnetic torque during start-up and large speed transients."""
    inverter = make_foc(frequency_ref=hz(60), time_ramp=0.1)
    inverter.initialize_control_state(dt=TS)
    iqs_max = 3.0 * inverter.Is_rated
    rotor_speed = 0.0
    for k in range(2000):
        w_sync, *_ = inverter.get_current_state(k * TS, TS, rotor_speed, 0.0, 0.0, 0.0)
        wsl = w_sync - inverter.np_pairs * rotor_speed
        iqs_ref = wsl * inverter.taur * inverter.ids_ref
        assert abs(iqs_ref) <= iqs_max * (1 + 1e-9)
    assert abs(iqs_ref) >= iqs_max * (1 - 1e-6)


def test_foc_voltage_reference_is_limited_to_the_six_step_fundamental():
    """With a large speed error the controllers saturate: the modulation index of
    the held reference stays at ``2 sqrt(3) / pi``, the six-step fundamental."""
    inverter = make_foc()
    inverter.initialize_control_state(dt=TS)
    indices = []
    for k in range(300):
        inverter.get_current_state(k * TS, TS, 0.0, 0.0, 0.0, 0.0)
        indices.append(inverter.modulation_index)
    six_step = 2 * np.sqrt(3) / np.pi
    assert max(indices) <= six_step * (1 + 1e-9)
    assert max(indices) >= six_step * (1 - 1e-6)
