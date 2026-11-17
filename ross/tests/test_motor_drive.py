"""Tests for the options of the V/f and FOC inverters.

The reference values are analytical or taken from the machine theory:

- the synchronous speed is ``120 f / p`` rpm;
- the flux angle is the time integral of the frequency;
- above the rated frequency the flux decreases as ``f_rated / f`` (field
  weakening), so that the slip needed for the same torque grows in the same
  proportion.

All tests use the parameters of ``motor_example()``.
"""

from copy import deepcopy

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ross.bearing_seal_element import BearingElement
from ross.motors.motor_drive import InverterFOC, InverterVF
from ross.motors.motor_element import motor_example
from ross.rotor_assembly import Rotor, rotor_example
from ross.units import Q_

VDC = 296.96


def hz(value):
    return Q_(value, "Hz").to("rad/s").m


def rpm(speed):
    return np.mean(speed) * 60.0 / (2.0 * np.pi)


def make_vf(**kwargs):
    return InverterVF(
        voltage_dc=VDC,
        frequency_s=Q_(5000, "Hz"),
        voltage_rated=220.0,
        frequency_rated=Q_(60, "Hz"),
        frequency_ref=Q_(66, "Hz"),
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
        torque_rated=6.25,
        stator_resistance=2.5,
        rotor_resistance=1.8,
        stator_reactance=1.3,
        rotor_reactance=1.3,
        mutual_reactance=43.08,
        Ip_motor=0.0372,
        time_ramp=0.1,
        frequency_ref=hz(66),
    )
    options.update(kwargs)
    return InverterFOC(**options)


@pytest.fixture(scope="module")
def motor():
    return motor_example()


def test_vf_voltage_boost_and_frequency_limit():
    inverter = make_vf(frequency_max=Q_(66, "Hz"), voltage_boost=20.0)
    rated_peak = inverter.voltage_phase_peak_rated
    assert_allclose(inverter.speed_control(0.0), 20.0)
    assert_allclose(inverter.speed_control(inverter.frequency_rated), rated_peak)
    assert inverter.speed_control(1.1 * inverter.frequency_rated) == rated_peak

    t_end = inverter.time_ramp
    assert_allclose(inverter.get_frequency(t_end), hz(66))
    assert inverter.get_frequency(2 * t_end, frequency_ref=hz(132)) == pytest.approx(
        inverter.frequency_max
    )


def test_vf_voltage_is_proportional_to_frequency_without_boost():
    inverter = make_vf()
    rated_peak = inverter.voltage_phase_peak_rated
    for fraction in (0.1, 0.5, 0.9):
        assert_allclose(
            inverter.speed_control(fraction * inverter.frequency_rated),
            fraction * rated_peak,
        )


def test_vf_default_frequency_limit_is_the_rated_frequency():
    inverter = make_vf()
    assert_allclose(inverter.get_frequency(10.0), inverter.frequency_rated)


@pytest.mark.parametrize("t", [0.1, 0.3, 0.6667, 1.0, 2.5])
def test_vf_flux_angle_is_the_integral_of_the_frequency(t):
    """The angle equals the trapezoidal integral of the instantaneous frequency."""
    inverter = make_vf(frequency_max=Q_(66, "Hz"))
    grid = np.linspace(0.0, t, 200001)
    frequency = np.array([inverter.get_frequency(tk) for tk in grid])
    expected = np.sum(0.5 * (frequency[1:] + frequency[:-1]) * np.diff(grid))
    angle = inverter.get_flux_angle(t, inverter.get_frequency(t))
    assert_allclose(angle, expected, rtol=1e-6)


def test_vf_flux_angle_is_continuous_at_the_end_of_the_ramp():
    inverter = make_vf(frequency_max=Q_(66, "Hz"))
    end = inverter.time_ramp
    before = inverter.get_flux_angle(end, inverter.get_frequency(end))
    after = inverter.get_flux_angle(end + 1e-9, inverter.get_frequency(end + 1e-9))
    assert_allclose(before, after, atol=1e-6)


def test_foc_speed_limit_is_the_rated_speed_by_default():
    inverter = make_foc()
    assert_allclose(inverter.speed_control(10.0, hz(66)), inverter.speed_rated)


def test_foc_speed_limit_follows_the_maximum_frequency():
    inverter = make_foc(frequency_max=hz(66))
    assert_allclose(inverter.speed_control(10.0, hz(66)), hz(66) / inverter.np_pairs)


def test_foc_field_weakening_increases_slip_above_rated_frequency():
    """At 1.05 times the base speed the flux drops to 1 / 1.05, and the slip
    for the same speed error grows by 1.05."""
    plain = make_foc(frequency_max=hz(66))
    weakened = make_foc(frequency_max=hz(66), field_weakening=True)
    rotor_speed = 1.05 * plain.frequency_rated / plain.np_pairs
    slips = []
    for inverter in (plain, weakened):
        inverter.initialize_control_state(dt=1e-5)
        w_sync, *_ = inverter.get_current_state(1.0, 1e-5, rotor_speed, 0.0, 0.0, 0.0)
        slips.append(w_sync - plain.np_pairs * rotor_speed)
    assert slips[0] > 0
    assert_allclose(slips[1] / slips[0], 1.05, rtol=1e-9)


def test_foc_field_weakening_does_not_act_below_the_rated_frequency():
    plain = make_foc(frequency_max=hz(66))
    weakened = make_foc(frequency_max=hz(66), field_weakening=True)
    rotor_speed = 0.8 * plain.frequency_rated / plain.np_pairs
    slips = []
    for inverter in (plain, weakened):
        inverter.initialize_control_state(dt=1e-5)
        w_sync, *_ = inverter.get_current_state(1.0, 1e-5, rotor_speed, 0.0, 0.0, 0.0)
        slips.append(w_sync - plain.np_pairs * rotor_speed)
    assert_allclose(slips[1], slips[0])


def run_idle_controller(inverter, rotor_speed, steps, dt=1e-5):
    inverter.initialize_control_state(dt=dt)
    for k in range(steps):
        inverter.get_current_state(1.0 + k * dt, dt, rotor_speed, 0.0, 0.0, 0.0)
    return inverter.control_state["ids_programmed"]


def test_flux_programming_is_off_by_default():
    inverter = make_foc()
    assert not inverter.flux_programming
    assert_allclose(
        run_idle_controller(inverter, inverter.speed_rated, 10), inverter.ids_ref
    )


def test_flux_programming_reduces_the_flux_without_load():
    """With no speed error the torque current is zero, so the flux settles at
    `flux_min_ratio` times its rated value."""
    inverter = make_foc(flux_programming=True, flux_min_ratio=0.3)
    ids = run_idle_controller(inverter, inverter.speed_rated, 200000)
    assert_allclose(ids, 0.3 * inverter.ids_ref, rtol=2e-2)


def test_flux_programming_restores_the_flux_under_load():
    """A large speed error saturates the torque current, which asks for the rated
    flux after a few filter time constants."""
    inverter = make_foc(flux_programming=True, flux_time_constant=0.01)
    ids = run_idle_controller(inverter, 0.0, 20000)
    assert_allclose(ids, inverter.ids_ref, rtol=1e-3)


def test_flux_programming_follows_the_filter_time_constant():
    inverter = make_foc(
        flux_programming=True, flux_min_ratio=0.3, flux_time_constant=0.05
    )
    steps = 5000
    ids = run_idle_controller(inverter, inverter.speed_rated, steps)
    elapsed = steps * 1e-5
    target = 0.3 * inverter.ids_ref
    expected = target + (inverter.ids_ref - target) * np.exp(-elapsed / 0.05)
    assert_allclose(ids, expected, rtol=1e-3)


def test_vf_above_rated_frequency_reaches_the_synchronous_speed(motor):
    """With `frequency_max`, the V/f drive runs at 66 Hz: 1980 rpm at no load."""
    t = np.arange(0, 1.5 + 1e-3, 1e-3)
    results = motor.run_with_inverter_vf(
        t,
        frequency_s=Q_(5000, "Hz"),
        time_step=1e-5,
        load_torque_entrance_time=10.0,
        load_torque_ratio=0.0,
        time_ramp=0.3,
        frequency_ref=Q_(66, "Hz"),
        inverter_options={"frequency_max": Q_(66, "Hz"), "voltage_boost": 20.0},
    )
    steady = len(results.speed) * 4 // 5
    assert_allclose(rpm(results.speed[steady:]), 120 * 66 / 4, atol=15.0)


def test_foc_above_rated_frequency_with_field_weakening_tracks_the_speed(motor):
    t = np.arange(0, 1.5 + 1e-3, 1e-3)
    results = motor.run_with_inverter_foc(
        t,
        frequency_s=Q_(5000, "Hz"),
        time_step=1e-5,
        load_torque_entrance_time=0.9,
        load_torque_ratio=1.0,
        time_ramp=0.3,
        frequency_ref=Q_(66, "Hz"),
        inverter_options={
            "frequency_max": Q_(66, "Hz"),
            "field_weakening": True,
            "flux_programming": True,
        },
    )
    steady = len(results.speed) * 4 // 5
    assert_allclose(rpm(results.speed[steady:]), 120 * 66 / 4, atol=15.0)


@pytest.fixture(scope="module")
def rotor_with_motor(motor):
    base_rotor = rotor_example()
    bearings = [
        BearingElement(n=bearing.n, kxx=1e6, cxx=2e3)
        for bearing in base_rotor.bearing_elements
    ]
    return Rotor(
        base_rotor.shaft_elements,
        base_rotor.disk_elements,
        bearings,
        motor_element=deepcopy(motor),
    )


@pytest.mark.parametrize(
    "drive_mode, options, expected_rpm, tolerance",
    [
        # open loop: the speed droops by the rated slip (1800 - 1710 rpm)
        (
            "VFD_VF",
            {"voltage_boost": 20.0, "frequency_max": Q_(60, "Hz")},
            1710.0,
            30.0,
        ),
        # closed loop: the speed is held at the synchronous speed of 60 Hz
        (
            "VFD_FOC",
            {"flux_programming": True, "frequency_max": Q_(60, "Hz")},
            1800.0,
            15.0,
        ),
    ],
)
def test_run_with_motor_forwards_inverter_options(
    rotor_with_motor, drive_mode, options, expected_rpm, tolerance
):
    t = np.arange(0, 1.5 + 1e-3, 1e-3)
    results = rotor_with_motor.run_with_motor(
        t=t,
        node=[2],
        unbalance_magnitude=[5e-4],
        unbalance_phase=[0.0],
        drive_mode=drive_mode,
        load_torque_entrance_time=0.8,
        load_torque_ratio=1.0,
        time_step=1e-5,
        time_ramp=0.4,
        frequency_ref=Q_(60, "Hz"),
        inverter_options=options,
    )
    speed = results.motor_results.sample_at("speed", results.t)
    assert_allclose(rpm(speed[len(speed) * 4 // 5 :]), expected_rpm, atol=tolerance)
