"""Model three-phase electrical sources and motor drives.

This module provides an ideal three-phase AC source with support for harmonic
distortion and voltage unbalance, as well as voltage-source inverters (VSIs)
using Space Vector PWM (SVPWM) modulation. Inverter control is available through
scalar V/f control (:class:`InverterVF`) and indirect Field-Oriented Control
(:class:`InverterFOC`).

The source and inverter classes expose phase-voltage and operating-state methods
that can be used by motor simulations.

References
----------
Wu, B. & Narimani, M. (2016). High-Power Converters and AC Drives. Wiley.
Novotny, D. & Lipo, T. (1996). Vector Control and Dynamics of AC Drives.
"""

from functools import lru_cache

import numpy as np

from ross.units import check_units, Q_

from .results import PhaseResults
from .utils import clarke_transform, inverse_clarke_transform, park_transform


class SourceAC:
    """Create an ideal 3-phase AC source with harmonics and voltage unbalance support.

    Supports arbitrary harmonic orders and amplitudes, per-phase voltage magnitude
    unbalance, and per-phase voltage angle deviation.

    Parameters
    ----------
    voltage_net : float
        RMS phase voltage [V].
    frequency_net : float, pint.Quantity
        Fundamental frequency [rad/s].
    initial_phase_angle : float, pint.Quantity, optional
        Initial phase angle [rad]. Default is 0.
    harmonic_enable : bool, optional
        Whether to enable harmonics. Default is False.
    harmonic_orders : list of int, optional
        Harmonic orders (e.g., [5, 7, 11] for 5th, 7th, and 11th harmonics).
    harmonic_amplitudes : list of float, optional
        Harmonic amplitudes as percentage of voltage_net
        (e.g., [10, 5, 2] for 10%, 5%, and 2%).
    unbalance_enable : bool, optional
        Whether to enable unbalances. Default is False.
    unbalance_voltage_percent : list of float, optional
        Voltage magnitude deviation per phase (A, B, C) relative to rated [%].
        Must contain exactly 3 elements.
        Positive → higher voltage; Negative → lower voltage.
    unbalance_angle_deviation : list of float, pint.Quantity, optional
        Angle deviation per phase (A, B, C) [rad].
        Must contain exactly 3 elements.

    Notes
    -----
    Harmonics and unbalances can be configured via `.set_harmonics()` and `.set_unbalances()`.

    Examples
    --------
    >>> src = SourceAC(voltage_net=220.0, frequency_net=Q_(60.0, "Hz"), initial_phase_angle=0.0)

    Configure harmonics
    >>> src.set_harmonics(
    ...    harmonic_orders=[5, 7, 11, 13],
    ...    harmonic_amplitudes=[10.0, 5.0, 3.0],
    ...    enable=True,
    ... )  # harmonic_amplitudes shorter → 13th = 0%

    Configure unbalances
    >>> src.set_unbalances(
    ...    voltage_percent=[5.0, 0.0, -3.0],
    ...    angle_deviation=Q_([2.0, 0.0, -2.0], "deg"),
    ...    enable=True,
    ... )

    Compute a few voltages
    >>> t_samples = np.linspace(0, 1 / 60, 5)
    >>> resp = src.run(t_samples)
    >>> fig = resp.plot()

    Disable harmonics
    >>> src.harmonics["enable"] = False

    >>> va, vb, vc = src.get_phase_voltages(t=0.001)
    >>> np.round([va, vb, vc], 2)
    array([ 299.36,  -45.45, -242.91])

    >>> f, va, vb, vc = src.get_current_state(t=0.5)
    >>> np.round(f, 2)
    376.99
    """

    # Phase angle offsets for a balanced 3-phase system [rad]
    # [phase_A, phase_B, phase_C]
    _PHASE_OFFSET = [0.0, -2 * np.pi / 3, +2 * np.pi / 3]
    _PHASE_LABEL = ["A", "B", "C"]

    @check_units
    def __init__(
        self,
        voltage_net,
        frequency_net,
        initial_phase_angle=0.0,
        harmonic_enable=False,
        harmonic_orders=None,
        harmonic_amplitudes=None,
        unbalance_enable=False,
        unbalance_voltage_percent=None,
        unbalance_angle_deviation=None,
    ):
        self.voltage_net = voltage_net
        self.frequency_net = frequency_net
        self.initial_phase_angle = initial_phase_angle

        if harmonic_orders:
            self.set_harmonics(
                harmonic_orders,
                harmonic_amplitudes,
                harmonic_enable,
            )
        else:
            self.set_harmonics(None, None, False)

        self.set_unbalances(
            unbalance_voltage_percent,
            unbalance_angle_deviation,
            unbalance_enable,
        )

    def set_harmonics(self, harmonic_orders, harmonic_amplitudes=None, enable=True):
        """Set harmonic orders and amplitudes for the AC source.

        Parameters
        ----------
        harmonic_orders : list of int
            Harmonic orders (e.g., [5, 7, 11] for 5th, 7th, and 11th harmonics).
        harmonic_amplitudes : list of float, optional
            Harmonic amplitudes as percentage of voltage_net (e.g., [10, 5, 2] for 10%, 5%, and 2%).
            If shorter than harmonic_orders, remaining amplitudes are set to 0.
        enable : bool, optional
            Enable harmonics. Default is True.
        """
        if harmonic_orders is not None:
            harmonic_orders = list(harmonic_orders)
            n = len(harmonic_orders)

            # Adjust harmonic_amplitudes vector to the harmonic_orders length
            if harmonic_amplitudes is None:
                harmonic_amplitudes = [0.0] * n
            else:
                harmonic_amplitudes = list(harmonic_amplitudes)
                if len(harmonic_amplitudes) < n:
                    harmonic_amplitudes += [0.0] * (
                        n - len(harmonic_amplitudes)
                    )  # filling up to the harmonic_orders length
                else:
                    harmonic_amplitudes = harmonic_amplitudes[
                        :n
                    ]  # truncate to harmonic_orders length

            # Clamp amplitudes to [0, 100]
            harmonic_amplitudes = [
                float(np.clip(a, 0.0, 100.0)) for a in harmonic_amplitudes
            ]

            # Truncate harmonic_orders to integer numbers
            harmonic_orders = [int(h) for h in harmonic_orders]

        self.harmonics = {
            "enable": enable or False,
            "orders": harmonic_orders,
            "amplitudes": harmonic_amplitudes,
        }

    @staticmethod
    def _parse_3vec(v, default):
        """Parse input into a 3-element list, filling missing entries with default.

        Parameters
        ----------
        v : list or None
            Input vector (may have fewer than 3 elements).
        default : float
            Default value for missing entries.

        Returns
        -------
        list
            3-element list with float entries.
        """
        if v is None:
            return [default, default, default]

        v = list(v)

        if len(v) < 3:
            v += [default] * (3 - len(v))
        elif len(v) > 3:
            v = v[:3]

        return [float(x) for x in v]

    @check_units
    def set_unbalances(self, voltage_percent, angle_deviation, enable=True):
        """Set voltage magnitude unbalance and angle deviation for the AC source.

        Parameters
        ----------
        voltage_percent : list of float
            Voltage magnitude deviation per phase (A, B, C) relative to rated [%].
            Must contain exactly 3 elements. Positive → higher voltage; Negative → lower voltage.
        angle_deviation : list of float, pint.Quantity
            Angle deviation per phase (A, B, C) [rad].
            Must contain exactly 3 elements.
        enable : bool, optional
            Enable unbalances. Default is True.
        """
        voltage_percent = self._parse_3vec(voltage_percent, 0.0)
        angle_deviation = self._parse_3vec(angle_deviation, 0.0)

        self.unbalances = {
            "enable": enable or False,
            "voltage_percent": voltage_percent,
            "angle_deviation": angle_deviation,
        }

    def __repr__(self):
        return (
            f"SourceAC(voltage_net={self.voltage_net} V, frequency_net={Q_(self.frequency_net, 'rad/s').to('Hz').m} Hz, "
            f"initial_phase_angle={self.initial_phase_angle:.4f} rad, "
            f"harmonics={'ON' if self.harmonics['enable'] else 'OFF'}, "
            f"unbalances={'ON' if self.unbalances['enable'] else 'OFF'})"
        )

    def _build_phase_voltage(self, t, phase_id):
        """Compute instantaneous voltage for one phase at time t.

        Parameters
        ----------
        t : float
            Time [s].
        phase_id : int
            Phase identifier: 0 → A, 1 → B, 2 → C.

        Returns
        -------
        float
            Instantaneous voltage [V] with harmonics, unbalance, and angle deviations applied.
        """
        phi = self._PHASE_OFFSET[phase_id]  # nominal phase shift
        w = self.frequency_net

        if self.unbalances["enable"]:
            vd_pct = self.unbalances["voltage_percent"][phase_id]
            angle_offset = self.unbalances["angle_deviation"][phase_id]
        else:
            vd_pct = 0.0
            angle_offset = 0.0

        mag_factor = (100.0 + vd_pct) / 100.0  # amplitude scale

        # Phase A gets +angle_deviation, Phase B neutral, Phase C gets –angle_deviation
        # (mirrors the sign convention used in the original snippet)
        sign = [+1.0, 0.0, -1.0][phase_id]
        angle_offset *= sign

        # --- Harmonics ---
        a_harm = 0.0
        v = 0.0

        if self.harmonics["enable"]:
            for h, a in zip(
                self.harmonics["orders"], self.harmonics["amplitudes"], strict=True
            ):
                a_harm += a

                v += (
                    np.sqrt(2)
                    * self.voltage_net
                    * mag_factor
                    * (a / 100.0)
                    * np.cos(h * w * t + self.initial_phase_angle + phi + angle_offset)
                )

        v += (
            np.sqrt(2)
            * self.voltage_net
            * mag_factor
            * (100 - a_harm)
            / 100
            * np.cos(w * t + self.initial_phase_angle + phi + angle_offset)
        )

        return v

    def get_phase_voltages(self, t):
        """Get instantaneous phase voltages at time `t`.

        Parameters
        ----------
        t : float
            Time [s].

        Returns
        -------
        vas, vbs, vcs : tuple of float
            Instantaneous phase voltages [V].
        """
        vas = self._build_phase_voltage(t, 0)
        vbs = self._build_phase_voltage(t, 1)
        vcs = self._build_phase_voltage(t, 2)

        return vas, vbs, vcs

    def get_current_state(self, t, *args):
        """Get the fundamental frequency and phase voltages of
        the source at time `t`.

        Parameters
        ----------
        t : float
            Time [s].
        *args : tuple
            Additional arguments (not used in this implementation).

        Returns
        -------
        frequency : float
            Fundamental frequency [rad/s].
        vas, vbs, vcs : tuple of float
            Instantaneous phase voltages [V].
        """
        frequency = self.frequency_net
        vas, vbs, vcs = self.get_phase_voltages(t)

        return frequency, vas, vbs, vcs

    def run(self, t):
        """Run the simulation for a series of time steps.

        Parameters
        ----------
        t : array_like
            Array of time steps.

        Returns
        -------
        results : ross.PhaseResults
            For more information on attributes and methods available see:
            :py:class:`ross.PhaseResults`
        """
        vas, vbs, vcs = np.vectorize(self.get_phase_voltages)(t)

        voltages = dict()
        voltages["a"] = vas
        voltages["b"] = vbs
        voltages["c"] = vcs

        results = PhaseResults(t, voltages, "V")

        return results


@lru_cache(maxsize=1)
def _bose_tables():
    """Tabulate the fundamental of the Bose overmodulation modes.

    The DC link voltage is normalized to 1 V. The tables relate the modulation
    index ``m = pi M / (2 sqrt(3))`` to the internal amplitude of mode 1 and to
    the holding angle of mode 2.

    Returns
    -------
    m_internal_tab, m_mode1_tab : numpy.ndarray
        Internal amplitude and the modulation index it produces in mode 1.
    alpha_h_tab, m_mode2_tab : numpy.ndarray
        Holding angle and the modulation index it produces in mode 2.
    m_limit : float
        Modulation index at the end of mode 1.
    """
    pi3 = np.pi / 3
    m_linear = np.pi / (2 * np.sqrt(3))

    # Midpoints of the angular intervals of a 60 degree sector
    n_angles = 4096
    alpha = (np.arange(n_angles) + 0.5) * pi3 / n_angles
    vertex = np.exp(1j * pi3)
    rotation = np.exp(-1j * alpha)

    m_internal_tab = np.linspace(1, 2 / np.sqrt(3), 1201)
    m_mode1_tab = np.zeros(m_internal_tab.size)
    for k, m_internal in enumerate(m_internal_tab):
        d1 = m_internal * np.sin(pi3 - alpha)
        d2 = m_internal * np.sin(alpha)
        factor = np.maximum(d1 + d2, 1.0)
        v_mean = (2 / 3) * (d1 / factor + d2 / factor * vertex)
        m_mode1_tab[k] = (np.pi / 2) * np.mean(np.real(v_mean * rotation))
    m_mode1_tab[0] = m_linear
    m_limit = m_mode1_tab[-1]

    alpha_h_tab = np.linspace(0, np.pi / 6, 1201)
    m_mode2_tab = np.zeros(alpha_h_tab.size)
    for k, alpha_h in enumerate(alpha_h_tab):
        if k == alpha_h_tab.size - 1:
            alpha_m = np.where(alpha < np.pi / 6, 0.0, pi3)
        else:
            alpha_m = np.clip((alpha - alpha_h) * pi3 / (pi3 - 2 * alpha_h), 0, pi3)
        d1 = (np.sqrt(3) * np.cos(alpha_m) - np.sin(alpha_m)) / (
            np.sqrt(3) * np.cos(alpha_m) + np.sin(alpha_m)
        )
        d1 = np.clip(d1, 0, 1)
        v_mean = (2 / 3) * (d1 + (1 - d1) * vertex)
        m_mode2_tab[k] = (np.pi / 2) * np.mean(np.real(v_mean * rotation))
    m_mode2_tab[0] = m_limit
    m_mode2_tab[-1] = 1.0

    return m_internal_tab, m_mode1_tab, alpha_h_tab, m_mode2_tab, m_limit


class Inverter:
    """Base class for three-phase voltage source inverters using SVPWM.

    Provides the shared Space Vector PWM modulator used by
    :class:`InverterVF` and :class:`InverterFOC`. The duty cycles are computed once
    per switching period, with the Bose overmodulation above the linear limit, and
    held until the next period. Subclasses implement the speed control.

    Parameters
    ----------
    voltage_dc : float
        DC link voltage [V].
    frequency_s : float or pint.Quantity
        IGBT switching frequency [rad/s].
    voltage_rated : float
        Rated line voltage [V].
    frequency_rated : float or pint.Quantity
        Rated operating frequency [rad/s].
    time_ramp : float, optional
        Acceleration ramp time [s]. Default is 0.6667.
    frequency_ref : float or pint.Quantity, optional
        Reference electrical frequency [rad/s]. Default is half the
        rated frequency.
    """

    def __init__(
        self,
        voltage_dc,
        frequency_s,
        voltage_rated,
        frequency_rated,
        time_ramp=0.6667,
        frequency_ref=None,
    ):

        self.voltage_dc = voltage_dc
        self.frequency_s = frequency_s
        self.Ts = 2 * np.pi / frequency_s

        self.voltage_rated = float(voltage_rated)
        self.frequency_rated = float(frequency_rated)
        self.time_ramp = float(time_ramp)
        self.frequency_ref = float(frequency_ref or frequency_rated / 2)

        # Switching SVPWM table, shared by every inverter implemented in this module.
        # Each column represents the states of the upper switches for the space
        # vectors V0, V1, V3, V2, V6, V4, V5 and V7
        self.sw_table = np.array(
            [
                [0, 1, 1, 0, 0, 0, 1, 1],
                [0, 0, 1, 1, 1, 0, 0, 1],
                [0, 0, 0, 0, 1, 1, 1, 1],
            ]
        )

        # Active vectors according to the sector, shared by every inverter implemented
        # in this module.
        self.actv_vet = np.array([[2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 2]])

        self.V0 = 1
        self.V7 = 8

        self.modulation_index = 0.0

    def initialize_control_state(self, dt, theta_0=0.0):
        """Initialize the discrete PWM carrier and the held duty cycles.

        The duty cycles are computed at the start of every switching period and
        held until the next one, while the carrier is compared with them at every
        simulation step. Must be called before the first time step of a simulation
        that uses the held duty cycles; without it, the duty cycles are recomputed
        at every call and the carrier is a function of the time.

        Parameters
        ----------
        dt : float
            Simulation time step [s]. The switching period should be a multiple
            of it.
        theta_0 : float, optional
            Initial flux angle [rad]. Default is 0.
        """
        n_samples = max(1, int(round(self.Ts / dt)))
        if n_samples > 1 and not np.isclose(self.Ts / dt, n_samples, rtol=1e-9):
            raise ValueError(
                "The switching period must be a multiple of the time step: "
                f"Ts / dt = {self.Ts / dt}."
            )
        self.control_state = {
            "carrier_index": 1,
            "n_samples": n_samples,
            "reference": np.zeros(3),
        }

    def _is_period_start(self):
        """Return True when the next call starts a new switching period."""
        state = getattr(self, "control_state", None)
        if state is None:
            return True
        return (state["carrier_index"] - 1) % state["n_samples"] == 0

    def _dwell_times(self, va_ref, vb_ref, vc_ref):
        """Compute the dwell times of the active and zero vectors (Bose method).

        In the linear region the dwell times are the usual ones. In overmodulation
        mode 1, the internal amplitude is raised to compensate the loss of
        fundamental and the vector is projected radially onto the hexagon. In
        mode 2, the angle is remapped and the vector is held at the vertices until
        the six-step operation.

        Parameters
        ----------
        va_ref, vb_ref, vc_ref : float
            Reference three-phase voltages [V].

        Returns
        -------
        sector : int
            SVPWM sector, from 1 to 6.
        T1, T2, T0 : float
            Dwell times of the first and second active vectors and of the zero
            vectors [s].
        M : float
            Modulation index, ``sqrt(3) |v| / V_dc``. The linear limit is 1.
        """
        m_internal_tab, m_mode1_tab, alpha_h_tab, m_mode2_tab, m_limit = _bose_tables()
        pi3 = np.pi / 3
        Ts = self.Ts

        v_alpha, v_beta = clarke_transform(va_ref, vb_ref, vc_ref)

        vr = np.sqrt(v_alpha**2 + v_beta**2)
        theta = np.arctan2(v_beta, v_alpha)
        if theta < 0:
            theta += 2 * np.pi

        S = int(np.floor(theta / pi3)) + 1
        S = max(1, min(S, 6))
        theta_k = theta - (S - 1) * pi3

        M = np.sqrt(3) * vr / self.voltage_dc
        m = min(np.pi * M / (2 * np.sqrt(3)), 1.0)

        if M <= 1:
            T1 = Ts * M * np.sin(pi3 - theta_k)
            T2 = Ts * M * np.sin(theta_k)
            T0 = max(Ts - T1 - T2, 0.0)
        elif m < m_limit:
            M_internal = np.interp(m, m_mode1_tab, m_internal_tab)
            T1 = Ts * M_internal * np.sin(pi3 - theta_k)
            T2 = Ts * M_internal * np.sin(theta_k)
            if T1 + T2 > Ts:
                factor = Ts / (T1 + T2)
                T1 *= factor
                T2 *= factor
            T0 = max(Ts - T1 - T2, 0.0)
        elif m < 1:
            alpha_h = np.interp(m, m_mode2_tab, alpha_h_tab)
            if theta_k <= alpha_h:
                theta_m = 0.0
            elif theta_k >= pi3 - alpha_h:
                theta_m = pi3
            else:
                theta_m = (theta_k - alpha_h) * pi3 / (pi3 - 2 * alpha_h)
            T1 = (
                Ts
                * (np.sqrt(3) * np.cos(theta_m) - np.sin(theta_m))
                / (np.sqrt(3) * np.cos(theta_m) + np.sin(theta_m))
            )
            T1 = np.clip(T1, 0, Ts)
            T2 = Ts - T1
            T0 = 0.0
        else:
            T1, T2 = (Ts, 0.0) if theta_k < pi3 / 2 else (0.0, Ts)
            T0 = 0.0

        return S, T1, T2, T0, M

    def _svpwm(self, t, va_ref, vb_ref, vc_ref):
        """Synthesize phase voltages via Space Vector PWM modulation.

        At the start of every switching period, the dwell times of the reference
        are converted into duty cycles, which are held until the next period.
        At every call, the held duty cycles are compared with a triangular carrier
        evaluated at the midpoint of the simulation step. The references of the
        calls that are not at the start of a period are ignored.

        Without a prior call to :py:meth:`initialize_control_state`, the duty cycles
        are recomputed at every call and the carrier is a function of `t`.

        Parameters
        ----------
        t : float
            Time [s].
        va_ref, vb_ref, vc_ref : float
            Reference three-phase voltages [V].

        Returns
        -------
        van, vbn, vcn : float
            Instantaneous phase voltages [V].
        """
        state = getattr(self, "control_state", None)

        if self._is_period_start():
            S, T1, T2, T0, self.modulation_index = self._dwell_times(
                va_ref, vb_ref, vc_ref
            )

            vetor_seq = (
                np.array(
                    [self.V0, self.actv_vet[S - 1, 0], self.actv_vet[S - 1, 1], self.V7]
                )
                - 1
            )
            S_bits = self.sw_table[:, vetor_seq]

            t_seq = np.array([T0 / 2, T1, T2, T0 / 2])
            D = np.clip((S_bits @ t_seq) / self.Ts, 0, 1)
            reference = 2 * D - 1
            if state is not None:
                state["reference"] = reference
        else:
            reference = state["reference"]

        carrier = self._get_carrier(t)

        Ss = (carrier <= reference).astype(float)

        vao, vbo, vco = (2 * Ss - 1) * (self.voltage_dc / 2)

        van = (2 / 3) * vao - (1 / 3) * (vbo + vco)
        vbn = (2 / 3) * vbo - (1 / 3) * (vao + vco)
        vcn = (2 / 3) * vco - (1 / 3) * (vbo + vao)

        return van, vbn, vcn

    def _get_carrier(self, t):
        """Return the triangular PWM carrier.

        With the control state initialized, the carrier is sampled at the midpoint
        of every simulation step, which avoids repeating its minimum at the
        boundary between two periods, and advanced by the counter stored in
        `control_state["carrier_index"]`. Otherwise, it is a function of `t`.

        Parameters
        ----------
        t : float
            Current simulation time [s].

        Returns
        -------
        float
            Carrier value in the [-1, 1] interval.
        """
        state = getattr(self, "control_state", None)

        if state is None:
            u = 0 if self.Ts == 0 else (t % self.Ts) / self.Ts
        else:
            n_in_period = (state["carrier_index"] - 1) % state["n_samples"]
            u = (n_in_period + 0.5) / state["n_samples"]
            state["carrier_index"] += 1

        return 1 - 4 * np.abs(u - 0.5)


class InverterVF(Inverter):
    """Simulate a three-phase voltage source inverter with V/f adjustment technique.

    This class implements a three-phase VSI using Space Vector PWM (SVPWM)
    modulation with V/f adjustment technique. The inverter generates three-phase
    output voltages based on a reference frequency and DC link voltage.

    Parameters
    ----------
    voltage_dc : float
        DC link voltage [V].
    frequency_s : float or pint.Quantity
        IGBT switching frequency [rad/s].
    voltage_rated : float
        Rated line voltage [V].
    frequency_rated : float or pint.Quantity
        Rated operating frequency [rad/s].
    time_ramp : float, optional
        Acceleration ramp time [s] for frequency ramping. Default is 0.6667.
    frequency_ref : float or pint.Quantity, optional
        Reference frequency for V/f adjustment [rad/s]. Default is half
        the rated frequency.

    References
    ----------
    Wu, B. & Narimani, M. (2016). High-Power Converters and AC Drives. Wiley.

    Examples
    --------
    >>> from ross.units import Q_

    >>> inverter = InverterVF(
    ...     voltage_dc=300, frequency_s=Q_(5000, "Hz"),
    ...     voltage_rated=220, frequency_rated=Q_(60, "Hz"),
    ...     time_ramp=1, frequency_ref=Q_(90, "Hz"),
    ... )

    >>> freq = Q_(100, "Hz").to("rad/s").m
    >>> Vp = inverter.speed_control(frequency=freq)
    >>> float(np.round(Vp, 2))
    179.63

    >>> van, vbn, vcn = inverter.get_phase_voltages(t=0.001, frequency=freq, theta=0.0)
    >>> np.round([van, vbn, vcn], 2)
    array([ 100., -200.,  100.])

    >>> f = inverter.get_frequency(t=0.05, frequency_ref=freq)
    >>> float(np.round(f, 2))
    31.42

    >>> f, van, vbn, vcn = inverter.get_current_state(t=0.5, theta_0=0.0, frequency_ref=freq)
    >>> float(np.round(f, 2))
    0.13
    """

    @check_units
    def __init__(
        self,
        voltage_dc,
        frequency_s,
        voltage_rated,
        frequency_rated,
        time_ramp=0.6667,
        frequency_ref=None,
    ):

        super().__init__(
            voltage_dc,
            frequency_s,
            voltage_rated,
            frequency_rated,
            time_ramp,
            frequency_ref,
        )

        # Rated phase voltage peak value
        self.voltage_phase_peak_rated = (voltage_rated / np.sqrt(3)) * np.sqrt(2)

        self.f_0 = 0.0

    def speed_control(self, frequency):
        """Calculate the phase voltage peak.

        Computes the peak voltage for the phase voltages based on the V/f ratio,
        ensuring proportional control between voltage and frequency.

        Parameters
        ----------
        frequency : float
            Operating frequency [rad/s].

        Returns
        -------
        Vp : float
            Peak phase voltage [V], saturated at rated value.
        """
        # Peak value of the phase voltage proportional to the V/f ratio
        Vp = self.voltage_phase_peak_rated * (frequency / self.frequency_rated)

        # Saturation at the rated value
        Vp = min(Vp, self.voltage_phase_peak_rated)
        return Vp

    def get_phase_voltages(self, t, frequency, theta):
        """Generate three-phase voltages using SVPWM modulation.

        Computes the phase voltages (A, B, C) using Space Vector PWM modulation
        for a reference with the amplitude given by the V/f law and the angle
        `theta`.

        Parameters
        ----------
        t : float
            Current simulation time [s].
        frequency : float
            Operating frequency [rad/s].
        theta : float
            Electrical angle of the voltage reference [rad].

        Returns
        -------
        van : float
            Phase A voltage with respect to neutral [V].
        vbn : float
            Phase B voltage with respect to neutral [V].
        vcn : float
            Phase C voltage with respect to neutral [V].
        """
        Vp = self.speed_control(frequency)

        va_ref = Vp * np.sin(theta)
        vb_ref = Vp * np.sin(theta - 2 * np.pi / 3)
        vc_ref = Vp * np.sin(theta + 2 * np.pi / 3)

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return van, vbn, vcn

    def get_frequency(self, t, frequency_ref=None):
        """Calculate the current operating frequency with acceleration ramp.

        Computes the frequency accounting for the acceleration ramp, which linearly
        increases the frequency from zero to the reference value over the ramp
        time. The reference is not limited to the rated frequency, so the inverter
        can operate in the field-weakening region, where the voltage stays at its
        rated value.

        Parameters
        ----------
        t : float
            Current simulation time [s].
        frequency_ref : float, optional
            Reference frequency [rad/s]. If None, uses `self.frequency_ref`.

        Returns
        -------
        f_curr : float
            Current operating frequency [rad/s].
        """
        if frequency_ref is None:
            frequency_ref = self.frequency_ref

        fref = max(frequency_ref, 0)

        f_curr = self.f_0 + fref / self.time_ramp * t
        f_curr = min(f_curr, fref)

        return f_curr

    def initialize_control_state(self, dt, theta_0=0.0):
        """Initialize the PWM carrier and the electrical angle of the reference.

        Parameters
        ----------
        dt : float
            Simulation time step [s]. The switching period should be a multiple
            of it.
        theta_0 : float, optional
            Initial flux angle [rad], unused: the voltage reference starts at the
            angle zero. Default is 0.
        """
        super().initialize_control_state(dt, theta_0)
        self.control_state["theta"] = 0.0
        self.control_state["frequency"] = 0.0
        self.control_state["period"] = 0

    def get_current_state(self, t, theta_0, frequency_ref=None):
        """Get the fundamental frequency and phase voltages at time `t`.

        At the start of every switching period, the frequency of the ramp is
        updated at the time of the end of the period, the electrical angle
        integrates it over the period and the references are sampled. They are held
        until the next period. When the control state was not initialized, every
        call is a period.

        Parameters
        ----------
        t : float
            Time [s].
        theta_0 : float
            Initial flux angle [rad], used only when the control state was not
            initialized.
        frequency_ref : float, optional
            Reference frequency [rad/s]. If None, uses `self.frequency_ref`.

        Returns
        -------
        frequency : float
            Fundamental frequency [rad/s].
        van : float
            Phase A voltage with respect to neutral [V].
        vbn : float
            Phase B voltage with respect to neutral [V].
        vcn : float
            Phase C voltage with respect to neutral [V].
        """
        if getattr(self, "control_state", None) is None:
            self.initialize_control_state(self.Ts, theta_0)

        state = self.control_state

        if self._is_period_start():
            state["period"] += 1
            state["frequency"] = self.get_frequency(
                state["period"] * self.Ts, frequency_ref
            )
            state["theta"] = (state["theta"] + state["frequency"] * self.Ts) % (
                2 * np.pi
            )
            Vp = self.speed_control(state["frequency"])
            theta = state["theta"]
            va_ref = Vp * np.sin(theta)
            vb_ref = Vp * np.sin(theta - 2 * np.pi / 3)
            vc_ref = Vp * np.sin(theta + 2 * np.pi / 3)
        else:
            va_ref = vb_ref = vc_ref = 0.0

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return state["frequency"], van, vbn, vcn


class InverterFOC(Inverter):
    """Simulate a three-phase voltage source inverter with indirect Field-Oriented Control.

    This class implements a three-phase VSI operating under indirect
    Field-Oriented Control (iFOC), synthesizing the output voltages through
    Space Vector PWM (SVPWM), analogous to :class:`InverterVF` but replacing
    scalar V/f control with closed-loop rotor-flux-oriented current control.

    Unlike :class:`InverterVF` and :class:`SourceAC`,
    this inverter is a closed-loop element: its output voltages depend on
    the instantaneous rotor speed and stator currents fed back from the
    motor at every time step. Therefore it cannot be pre-computed
    independently of the motor's state; it must be driven from within the
    motor's time-stepping loop through ``get_current_state``, one step at a
    time, with rotor speed and stator current feedback.

    Parameters
    ----------
    voltage_dc : float
        DC link voltage [V].
    frequency_s : float or pint.Quantity
        IGBT switching frequency [rad/s].
    voltage_rated : float
        Rated line voltage [V].
    frequency_rated : float or pint.Quantity
        Rated (synchronous) electrical frequency [rad/s].
    n_poles : int
        Number of machine poles.
    speed_rated : float or pint.Quantity
        Rated mechanical speed [rad/s].
    torque_rated : float
        Rated load torque [N.m].
    stator_resistance : float
        Stator resistance [Ohm].
    rotor_resistance : float
        Rotor resistance [Ohm].
    stator_reactance : float
        Stator leakage reactance at rated frequency [Ohm].
    rotor_reactance : float
        Rotor leakage reactance at rated frequency [Ohm].
    mutual_reactance : float
        Magnetizing (mutual) reactance at rated frequency [Ohm].
    Ip_motor : float
        Rotor polar moment of inertia [kg.m²].
    time_ramp : float, optional
        Acceleration ramp time [s] for the mechanical speed reference.
        Default is 1.
    frequency_ref : float or pint.Quantity, optional
        Synchronous electrical frequency reference [rad/s]. Default is
        half the rated frequency.
    ids_ref : float, optional
        Magnetizing (direct-axis) current reference [A]. Default is None, which
        uses the value computed from the rated operating point.

    Notes
    -----
    Gains for the speed and current PI controllers are computed with the
    bandwidth method, mirroring the design used for scalar control. The
    direct-axis current controller uses the equivalent leakage inductance
    ``Lss - Lm**2 / Lrr``. The bandwidth of the current controllers is
    ``fs / 8``, reduced by 20 % when the speed reference is above the synchronous
    speed of the rated frequency.

    The speed and current loops run once per switching period and the duty
    cycles are held until the next one. The speed reference is not limited to the
    rated speed, and the voltage reference is limited to ``2 V_dc / pi``, the
    fundamental in six-step operation, with anti-windup of the speed and
    direct-axis integrators.

    The q-axis (torque-producing) current reference is limited to 3 times the
    rated stator current magnitude, bounding the electrical and mechanical
    stress during start-up and large speed transients. The speed-loop
    integrator is frozen whenever either the voltage or the current limit is
    active and freezing would increase the saturation.

    References
    ----------
    Wu, B. & Narimani, M. (2016). High-Power Converters and AC Drives. Wiley.
    Novotny, D. & Lipo, T. (1996). Vector Control and Dynamics of AC Drives.
    """

    @check_units
    def __init__(
        self,
        voltage_dc,
        frequency_s,
        voltage_rated,
        frequency_rated,
        n_poles,
        speed_rated,
        torque_rated,
        stator_resistance,
        rotor_resistance,
        stator_reactance,
        rotor_reactance,
        mutual_reactance,
        Ip_motor,
        time_ramp=1.0,
        frequency_ref=None,
        ids_ref=None,
    ):

        super().__init__(
            voltage_dc,
            frequency_s,
            voltage_rated,
            frequency_rated,
            time_ramp,
            frequency_ref,
        )

        self.np_pairs = n_poles / 2
        self.speed_rated = float(speed_rated)

        self.Rs = float(stator_resistance)
        self.Rr = float(rotor_resistance)

        Lls = float(stator_reactance) / self.frequency_rated
        Llr = float(rotor_reactance) / self.frequency_rated
        self.Lm = float(mutual_reactance) / self.frequency_rated
        self.Lss = Lls + self.Lm
        self.Lrr = Llr + self.Lm

        self.taur = self.Lrr / self.Rr

        # Modified equivalent circuit rotor resistance
        rated_slip = 1 - self.np_pairs * self.speed_rated / self.frequency_rated
        Rr_eq = (self.Rr * (self.Lm / self.Lrr) ** 2) / rated_slip

        # Auxiliary variables for calculating Zeq
        Ls1 = self.Lss - (self.Lm**2 / self.Lrr)
        Lm1 = (self.Lm**2) / self.Lrr

        # Equivalent impedance
        Zeq = (self.Rs + 1j * self.frequency_rated * Ls1) + (
            1j * self.frequency_rated * Lm1 * Rr_eq
        ) / (1j * self.frequency_rated * Lm1 + Rr_eq)

        Vpeak = self.voltage_rated * (np.sqrt(2) / np.sqrt(3))
        Is = Vpeak / Zeq

        # Modified equivalent circuit voltage Er
        Er = Vpeak - (self.Rs + 1j * self.frequency_rated * Ls1) * Is
        self.ids_ref = abs(Er) / (self.frequency_rated * Lm1)
        if ids_ref is not None:
            self.ids_ref = float(ids_ref)

        # Rated stator current magnitude
        self.Is_rated = abs(Is)

        # PI controller gains (bandwidth method). The bandwidth of the current
        # controllers is reduced above the synchronous speed of the rated frequency
        BW_current = Q_(frequency_s, "rad/s").to("Hz").m / 8
        synchronous_speed = self.frequency_rated / self.np_pairs
        if self.frequency_ref / self.np_pairs > synchronous_speed * (1 + 1e-9):
            BW_current *= 0.8
        BWp_iqs = BW_current
        BWp_ids = BW_current
        BWi_ids = BW_current
        BWp_w = BWi_ids / 8
        BWi_w = BWp_w / 8

        KL = float(torque_rated) / (self.np_pairs * self.speed_rated)  # Load constant
        J = float(Ip_motor)

        # Proportional and integral controller gain
        self.kp_w = J * 2 * np.pi * (BWp_w + BWi_w) - KL
        self.ki_w = J * 4 * (np.pi**2) * BWp_w * BWi_w
        self.kp_ids = Ls1 * 2 * np.pi * (BWp_ids + BWi_ids)
        self.ki_ids = Ls1 * 4 * (np.pi**2) * BWp_ids * BWi_ids

        self.Lsline = (
            self.Lss - (self.Lm**2) / self.Lrr
        )  # Equivalent leakage inductance
        self.kp_iqs = 2 * np.pi * self.Lsline * BWp_iqs

    def initialize_control_state(self, dt, theta_0=0.0):
        """Initialize integrator states and the discrete PWM carrier.

        Stores the closed-loop runtime state in `self.control_state`.
        Must be called before the first time step of a closed-loop
        simulation.

        Parameters
        ----------
        dt : float
            Simulation time step [s], used to set the number of samples per
            switching period. The switching period should be a multiple of it.
        theta_0 : float, optional
            Initial flux angle [rad], unused: the synchronous angle starts at zero.
            Default is 0.
        """
        super().initialize_control_state(dt, theta_0)
        self.control_state.update(
            {
                "int_err_w": 0.0,
                "int_err_ids": 0.0,
                "theta": 0.0,
                "w_ramp": 0.0,
                "w_sync": 0.0,
            }
        )

    def speed_control(self, t, frequency_ref):
        """Compute the mechanical speed reference with acceleration ramp.

        Called once per switching period. The reference changes at the rate that
        would take the rated speed to be reached in `time_ramp`, until it reaches
        the reference. It is not limited to the rated speed.

        Parameters
        ----------
        t : float
            Current simulation time [s] (unused, kept for compatibility).
        frequency_ref : float, optional
            Desired synchronous electrical frequency reference [rad/s].
            If None, uses `self.frequency_ref`.

        Returns
        -------
        w_ramp : float
            Ramped mechanical speed reference [rad/s].
        """
        if frequency_ref is None:
            frequency_ref = self.frequency_ref

        wref = max(frequency_ref / self.np_pairs, 0)

        state = self.control_state
        dw_max = self.speed_rated * self.Ts / self.time_ramp

        if state["w_ramp"] < wref:
            state["w_ramp"] = min(state["w_ramp"] + dw_max, wref)
        elif state["w_ramp"] > wref:
            state["w_ramp"] = max(state["w_ramp"] - dw_max, wref)

        return state["w_ramp"]

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        """Run the iFOC control loop and synthesize phase voltages via SVPWM.

        At the start of every switching period, the speed and current loops
        sample the rotor speed and the stator currents and update the voltage
        reference, the synchronous angle and the duty cycles, which are held
        until the next period. The phase voltages are synthesized at every call.
        The q-axis current reference is limited to 3 times the rated stator
        current magnitude.

        Parameters
        ----------
        t : float
            Current simulation time [s].
        dt : float
            Time step [s] (unused, the loops integrate over the switching period).
        rotor_speed : float
            Measured (feedback) rotor mechanical speed [rad/s].
        ia, ib, ic : float
            Measured (feedback) stator phase currents [A].
        frequency_ref : float, optional
            Desired synchronous electrical frequency reference [rad/s].
            If None, uses `self.frequency_ref`.

        Returns
        -------
        w_sync : float
            Synchronous electrical speed [rad/s].
        van : float
            Phase A voltage with respect to neutral [V].
        vbn : float
            Phase B voltage with respect to neutral [V].
        vcn : float
            Phase C voltage with respect to neutral [V].
        """
        state = self.control_state

        if not self._is_period_start():
            van, vbn, vcn = self._svpwm(t, 0.0, 0.0, 0.0)
            return state["w_sync"], van, vbn, vcn

        dt_control = self.Ts

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        u_prop = self.kp_w * err_w
        u_int = self.ki_w * state["int_err_w"]
        iqs_ref_unsat = u_prop + u_int

        # Torque-producing (q-axis) current limit, bounding the start-up inrush
        iqs_max = 3.0 * self.Is_rated
        iqs_ref = np.clip(iqs_ref_unsat, -iqs_max, iqs_max)

        # Slip frequency
        wsl = (1 / self.taur) * (iqs_ref / self.ids_ref)

        # Synchronous electrical speed
        w_sync = wsl + self.np_pairs * rotor_speed
        state["w_sync"] = w_sync

        state["theta"] += w_sync * dt_control

        # q aligned with cosine (torque), d aligned with sine (flux), matching the iFOC
        # convention: d_std = iqs, q_std = -ids
        i_alpha, i_beta = clarke_transform(ia, ib, ic)
        d_std, q_std = park_transform(i_alpha, i_beta, state["theta"])

        iqs, ids = d_std, -q_std

        err_iqs = iqs_ref - iqs
        vqs_ref = self.kp_iqs * err_iqs + self.Rs * iqs + self.Lss * w_sync * ids

        err_ids = self.ids_ref - ids
        state["int_err_ids"] += err_ids * dt_control

        vds_ref = (
            self.kp_ids * err_ids
            + self.ki_ids * state["int_err_ids"]
            + self.Rs * ids
            - self.Lsline * w_sync * iqs
        )

        # The reference may exceed the linear limit V_dc / sqrt(3). Its magnitude
        # is limited to the fundamental in six-step operation, 2 V_dc / pi
        Vmax = 2 * self.voltage_dc / np.pi
        vds_unsat = vds_ref
        Vref = np.sqrt(vqs_ref**2 + vds_ref**2)

        saturated = Vref > Vmax

        if saturated:
            scale = Vmax / Vref
            vqs_ref *= scale
            vds_ref *= scale

            # Anti-windup of the d-axis integrator: undo the last increment when it
            # increases the voltage demand beyond what the inverter supplies
            if err_ids * (vds_unsat - vds_ref) > 0:
                state["int_err_ids"] -= err_ids * dt_control

        # Anti-windup of the speed integrator: freeze it whenever either the
        # voltage or the current limit is actively clipping the output
        current_saturated = abs(iqs_ref_unsat) > iqs_max
        any_saturated = saturated or current_saturated
        if (not any_saturated) or (np.sign(err_w) != np.sign(iqs_ref_unsat)):
            state["int_err_w"] += err_w * dt_control

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return w_sync, van, vbn, vcn
