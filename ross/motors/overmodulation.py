"""Overmodulation of the two-level space vector PWM (Bose method).

The reference voltage vector is replaced by the vector that the inverter can
apply on the hexagon of the two-level converter, such that the fundamental of
the applied voltage equals the reference. The linear region ends at
``M1 = pi / (2 sqrt(3))``, mode I ends at ``M2 = sqrt(3) / 2 * ln(3)`` and mode II
ends at the six-step operation (``m = 1``), where ``m = |v| / (2 Vdc / pi)``.

References
----------
Mondal, S. K., Bose, B. K., Oleschuk, V. and Pinto, J. O. P. (2003). Space
vector pulse width modulation of three-level inverter extending operation into
overmodulation region. IEEE Trans. Power Electron., 18(2), 604-611.

Pinto, J. O. P., Bose, B. K., da Silva, L. E. B. and Kazmierkowski, M. P.
(2000). A neural-network-based space-vector PWM controller for voltage-fed
inverter induction motor drive. IEEE Trans. Ind. Appl., 36(6), 1628-1636.
"""

import math

import numpy as np

SQRT3 = math.sqrt(3.0)
SECTOR = math.pi / 3.0
M1 = math.pi / (2.0 * SQRT3)
M2 = (SQRT3 / 2.0) * math.log(3.0)

_APOTHEM = 1.0 / SQRT3
_SIX_STEP = 2.0 / math.pi


def hexagon_radius(alpha):
    """Return the hexagon radius at a sector angle.

    Parameters
    ----------
    alpha : float or array_like
        Angle inside the 60 degree sector [rad].

    Returns
    -------
    float or numpy.ndarray
        Radius of the hexagon side normalized by the DC link voltage.

    Examples
    --------
    >>> round(float(hexagon_radius(0.0)), 6)  # vertex: 2/3 of the DC link voltage
    0.666667
    >>> round(float(hexagon_radius(np.pi / 6)), 6)  # side midpoint: 1 / sqrt(3)
    0.57735
    """
    return _APOTHEM / np.cos(math.pi / 6.0 - np.asarray(alpha, dtype=float))


def _m_from_theta(theta):
    """Return the modulation index of mode I for a crossing angle."""
    psi = math.pi / 6.0 - np.asarray(theta, dtype=float)
    return SQRT3 * (theta / np.cos(psi) + np.arcsinh(np.tan(psi)))


_GAUSS_X, _GAUSS_W = np.polynomial.legendre.leggauss(64)


def _m_from_alpha_h(alpha_h):
    """Return the modulation index of mode II for a holding angle."""
    ah = np.atleast_1d(np.asarray(alpha_h, dtype=float))
    lo, hi = ah, SECTOR - ah
    half = 0.5 * (hi - lo)
    alpha = 0.5 * (hi + lo)[:, None] + half[:, None] * _GAUSS_X[None, :]
    k = (math.pi / 6.0) / np.maximum(math.pi / 6.0 - ah, 1e-12)[:, None]
    alpha_m = k * (alpha - ah[:, None])
    integrand = hexagon_radius(alpha_m) * np.cos(alpha_m - alpha)
    middle = half * (integrand * _GAUSS_W[None, :]).sum(axis=1)
    hold = (4.0 / 3.0) * np.sin(ah)
    m = (3.0 / math.pi) * (hold + middle) / _SIX_STEP
    return np.where(ah >= math.pi / 6.0 - 1e-15, 1.0, m)


def _build_tables(n=4097):
    """Tabulate the mode I and mode II relations between index and angle."""
    u = np.linspace(0.0, 1.0, n)
    theta = (math.pi / 6.0) * (1.0 - u) ** 2
    alpha_h = (math.pi / 6.0) * (1.0 - (1.0 - u) ** 3)
    return _m_from_theta(theta), theta, _m_from_alpha_h(alpha_h), alpha_h


_M_MODE_I, _THETA_MODE_I, _M_MODE_II, _ALPHA_H_MODE_II = _build_tables()


def theta_from_m(m):
    """Return the crossing angle of mode I for a modulation index.

    Parameters
    ----------
    m : float
        Modulation index in the interval ``[M1, M2]``.

    Returns
    -------
    float
        Angle [rad] where the trajectory leaves the circle arc for the hexagon side.

    Examples
    --------
    >>> round(theta_from_m(M1), 6)  # the arc starts at the hexagon side midpoint
    0.523599
    >>> round(theta_from_m(M2), 6)  # and reduces to the vertex at the end of mode I
    0.0
    """
    return float(np.interp(m, _M_MODE_I, _THETA_MODE_I))


def alpha_h_from_m(m):
    """Return the holding angle of mode II for a modulation index.

    Parameters
    ----------
    m : float
        Modulation index in the interval ``[M2, 1]``.

    Returns
    -------
    float
        Angle [rad] during which the vector is held at the hexagon vertex.

    Examples
    --------
    >>> round(alpha_h_from_m(M2), 6)  # nothing is held at the start of mode II
    0.0
    >>> round(alpha_h_from_m(1.0), 6)  # six-step: held up to the middle of the sector
    0.523599
    """
    return float(np.interp(m, _M_MODE_II, _ALPHA_H_MODE_II))


def bose_vector(v_alpha, v_beta, voltage_dc, m_max=1.0):
    """Return the voltage vector applied by the overmodulated inverter.

    Parameters
    ----------
    v_alpha, v_beta : float
        Reference voltage in the stationary frame, amplitude-invariant [V].
    voltage_dc : float
        DC link voltage [V].
    m_max : float, optional
        Maximum modulation index. The value 1 allows six-step operation.

    Returns
    -------
    v_alpha, v_beta : float
        Average voltage actually applied [V].
    mode : int
        0 linear, 1 mode I, 2 mode II and 3 six-step.

    Examples
    --------
    >>> va, vb, mode = bose_vector(100.0, 0.0, 300.0)
    >>> (va, vb, mode)
    (100.0, 0.0, 0)
    >>> va, vb, mode = bose_vector(200.0, 0.0, 300.0)
    >>> mode
    3
    """
    magnitude = math.hypot(v_alpha, v_beta)
    m = magnitude / (_SIX_STEP * voltage_dc)
    if m <= M1:
        return v_alpha, v_beta, 0

    theta = math.atan2(v_beta, v_alpha) % (2.0 * math.pi)
    sector = min(int(theta // SECTOR), 5)
    alpha = theta - sector * SECTOR
    m = min(m, m_max)

    if m <= M2:
        mode = 1
        theta_c = theta_from_m(m)
        if alpha < theta_c or alpha > SECTOR - theta_c:
            radius = _APOTHEM / math.cos(math.pi / 6.0 - theta_c)
        else:
            radius = float(hexagon_radius(alpha))
        alpha_m = alpha
    else:
        mode = 2
        if m >= 1.0:
            mode = 3
            alpha_m = 0.0 if alpha < math.pi / 6.0 else SECTOR
        else:
            alpha_h = alpha_h_from_m(m)
            k = (math.pi / 6.0) / max(math.pi / 6.0 - alpha_h, 1e-12)
            if alpha < alpha_h:
                alpha_m = 0.0
            elif alpha > SECTOR - alpha_h:
                alpha_m = SECTOR
            else:
                alpha_m = k * (alpha - alpha_h)
        radius = float(hexagon_radius(alpha_m))

    angle = sector * SECTOR + alpha_m
    return (
        radius * voltage_dc * math.cos(angle),
        radius * voltage_dc * math.sin(angle),
        mode,
    )
