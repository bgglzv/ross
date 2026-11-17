"""Utility functions for electric motor simulation and signal processing."""

import numpy as np
from numba import njit


@njit
def phase_to_line(v_phase):
    """Convert phase voltage to line-to-line voltage.

    For a balanced three-phase system, the line-to-line voltage magnitude is
    related to the phase voltage by a factor of :math:`\\sqrt{3}`.

    Parameters
    ----------
    v_phase : float
        Phase voltage [V].

    Returns
    -------
    float
        Line-to-line voltage [V].

    Examples
    --------
    >>> phase_to_line(127.0)  # doctest: +ELLIPSIS
    219.9...
    """
    return v_phase * np.sqrt(3)


def line_to_dc_bus(v_line):
    """Convert line-to-line voltage to DC bus voltage.

    For a three-phase rectifier, the DC bus voltage is related to the
    line-to-line voltage by a factor of :math:`1.35`.

    Parameters
    ----------
    v_line : float
        Line-to-line voltage [V].

    Returns
    -------
    float
        DC bus voltage [V].

    Examples
    --------
    >>> line_to_dc_bus(219.9)  # doctest: +ELLIPSIS
    296.8...
    """
    return v_line * 1.35


@njit
def clarke_transform(a, b, c):
    """Apply the Clarke (alpha-beta) transform to three-phase quantities.

    Transforms instantaneous phase values ``(a, b, c)`` into the stationary
    two-axis reference frame ``(alpha, beta)``. The transform uses the
    amplitude-invariant convention with a 2/3 scaling factor.

    Parameters
    ----------
    a : float
        Instantaneous value of phase a.
    b : float
        Instantaneous value of phase b.
    c : float
        Instantaneous value of phase c.

    Returns
    -------
    alpha : float
        Alpha-axis component.
    beta : float
        Beta-axis component.

    Examples
    --------
    >>> alpha, beta = clarke_transform(1.0, -0.5, -0.5)
    >>> alpha
    1.0
    >>> beta
    0.0
    """
    alpha = 2 / 3 * (a - b / 2 - c / 2)
    beta = 2 / 3 * (b - c) * np.sqrt(3) / 2
    return alpha, beta


@njit
def inverse_clarke_transform(alpha, beta):
    """Apply the inverse Clarke (alpha-beta) transform to two-axis quantities.

    Reconstructs the three-phase quantities ``(a, b, c)`` from the stationary
    two-axis reference frame ``(alpha, beta)``, assuming a null zero-sequence
    component. Uses the same amplitude-invariant convention (2/3 scaling) as
    :func:`clarke_transform`, so that ``inverse_clarke_transform`` is its
    exact inverse.

    Parameters
    ----------
    alpha : float
        Alpha-axis component.
    beta : float
        Beta-axis component.

    Returns
    -------
    a : float
        Instantaneous value of phase a.
    b : float
        Instantaneous value of phase b.
    c : float
        Instantaneous value of phase c.

    Examples
    --------
    >>> a, b, c = inverse_clarke_transform(1.0, 0.0)
    >>> np.round([a, b, c], 4)
    array([ 1. , -0.5, -0.5])
    """
    a = alpha
    b = -alpha / 2 + beta * np.sqrt(3) / 2
    c = -alpha / 2 - beta * np.sqrt(3) / 2
    return a, b, c


@njit
def park_transform(alpha, beta, theta):
    """Apply the Park (d-q) transform to alpha-beta quantities.

    Rotates the stationary ``(alpha, beta)`` frame into the synchronous
    ``(d, q)`` reference frame using the electrical angle ``theta``.

    Parameters
    ----------
    alpha : float
        Alpha-axis component.
    beta : float
        Beta-axis component.
    theta : float
        Electrical angle of the synchronous reference frame [rad].

    Returns
    -------
    d : float
        Direct-axis component.
    q : float
        Quadrature-axis component.

    Examples
    --------
    >>> d, q = park_transform(1.0, 0.0, 0.0)
    >>> d
    1.0
    >>> q
    0.0
    """
    d = alpha * np.cos(theta) + beta * np.sin(theta)
    q = -alpha * np.sin(theta) + beta * np.cos(theta)
    return d, q


def windowed_dfft(signal, dt):
    """Compute the windowed Discrete Fast Fourier Transform (DFFT) of a signal.

    The input signal is multiplied by a Hanning window before computing the FFT.
    Magnitudes are normalized by the window coherent gain, and one-sided
    spectrum scaling is applied to interior frequency bins.

    Parameters
    ----------
    signal : array_like
        Time domain signal.
    dt : float
        Sampling interval [s].

    Returns
    -------
    freq : ndarray
        Frequency range [Hz].
    mag : ndarray
        Magnitude of response in frequency domain.

    Examples
    --------
    >>> t = np.linspace(0, 1, 1000, endpoint=False)
    >>> signal = np.sin(2 * np.pi * 60 * t)
    >>> freq, mag = windowed_dfft(signal, dt=t[1] - t[0])
    >>> np.argmax(mag)  # doctest: +ELLIPSIS
    60
    """
    signal = np.asarray(signal)

    N = len(signal)
    window = np.hanning(N)

    signal_windowed = signal * window
    fft_values = np.fft.fft(signal_windowed)

    freq = np.fft.fftfreq(N, d=dt)

    coherent_gain = np.mean(window)
    mag = np.abs(fft_values) / (N * coherent_gain)

    idx = freq >= 0
    freq = freq[idx]
    mag = mag[idx]

    # Internal components duplicated
    if len(mag) > 2:
        mag[1:-1] *= 2

    return freq, mag


def _amplitude_at(signal, t, window, frequency):
    """Return the amplitude of a windowed signal at an arbitrary frequency."""
    phasor = np.sum(signal * window * np.exp(-2j * np.pi * frequency * t))
    return 2 * np.abs(phasor) / np.sum(window)


def fundamental_frequency(signal, dt, search_range=None):
    """Estimate the fundamental frequency of a periodic signal.

    The Hanning-windowed spectrum is scanned for its largest peak, which is then
    refined by a fine frequency search around it, so that the result is not
    limited to the frequency resolution of the FFT.

    Parameters
    ----------
    signal : array_like
        Time domain signal.
    dt : float
        Sampling interval [s].
    search_range : tuple of float, optional
        Lower and upper frequency [Hz] of the search. Default is None, which
        searches from 1 Hz to the Nyquist frequency.

    Returns
    -------
    float
        Fundamental frequency [Hz].

    Examples
    --------
    >>> t = np.arange(0, 1, 1e-4)
    >>> round(fundamental_frequency(np.sin(2 * np.pi * 63.7 * t), 1e-4), 2)
    63.7
    """
    signal = np.asarray(signal, dtype=float)
    signal = signal - signal.mean()
    freq, mag = windowed_dfft(signal, dt)
    low, high = search_range or (1.0, freq[-1])
    valid = (freq >= low) & (freq <= high)
    f_peak = freq[valid][np.argmax(mag[valid])]

    t = np.arange(len(signal)) * dt
    window = np.hanning(len(signal))
    df = freq[1] - freq[0]
    grid = np.linspace(f_peak - df, f_peak + df, 201)
    amplitudes = [_amplitude_at(signal, t, window, f) for f in grid]
    return float(grid[int(np.argmax(amplitudes))])


def total_harmonic_distortion(signal, dt, frequency=None, n_harmonics=50):
    """Compute the total harmonic distortion of a periodic signal.

    The amplitude of each harmonic is evaluated at the exact multiple of the
    fundamental frequency, with a Hanning window. The distortion is the root sum
    of squares of the harmonics from 2 to `n_harmonics`, divided by the
    amplitude of the fundamental. Components that are not multiples of the
    fundamental, such as the switching frequency sidebands of an inverter, are
    not counted.

    Parameters
    ----------
    signal : array_like
        Time domain signal. It should span several periods of the fundamental.
    dt : float
        Sampling interval [s].
    frequency : float, optional
        Fundamental frequency [Hz]. Default is None, which estimates it with
        :py:func:`fundamental_frequency`.
    n_harmonics : int, optional
        Highest harmonic order included. Default is 50.

    Returns
    -------
    thd : float
        Total harmonic distortion, as a ratio of the fundamental (0.1 is 10 %).
    frequency : float
        Fundamental frequency used [Hz].

    Examples
    --------
    A 60 Hz signal with a 5th harmonic of 10 % of the fundamental:

    >>> t = np.arange(0, 1, 1e-4)
    >>> signal = np.sin(2 * np.pi * 60 * t) + 0.1 * np.sin(2 * np.pi * 300 * t)
    >>> thd, f1 = total_harmonic_distortion(signal, 1e-4, frequency=60.0)
    >>> round(thd, 3), f1
    (0.1, 60.0)
    """
    signal = np.asarray(signal, dtype=float)
    signal = signal - signal.mean()
    if frequency is None:
        frequency = fundamental_frequency(signal, dt)

    t = np.arange(len(signal)) * dt
    window = np.hanning(len(signal))
    fundamental = _amplitude_at(signal, t, window, frequency)
    nyquist = 0.5 / dt
    orders = [k for k in range(2, n_harmonics + 1) if k * frequency < nyquist]
    harmonics = [_amplitude_at(signal, t, window, k * frequency) for k in orders]
    return float(np.sqrt(np.sum(np.square(harmonics))) / fundamental), float(frequency)


@njit
def rk4_step(func, dt, y0, args):
    """Perform a single Runge-Kutta 4 (RK4) integration step.

    Parameters
    ----------
    func : callable
        Function that computes derivatives. Must accept the state variables
        followed by additional arguments, i.e. ``func(*y, *args)``.
    dt : float
        Time step size [s].
    y0 : np.ndarray
        Initial state vector at the beginning of the step.
    args : np.ndarray
        Additional arguments passed to ``func``.

    Returns
    -------
    np.ndarray
        Updated state vector after one RK4 step.

    Examples
    --------
    >>> import numpy as np
    >>> from numba import njit

    >>> @njit
    ... def dydt(y, args):
    ...     return y

    >>> y1 = rk4_step(dydt, dt=0.1, y0=np.array([1.0]), args=np.array([]))
    >>> y1[0]  # doctest: +ELLIPSIS
    1.105...
    """
    k1 = func(y0, args)

    k2 = func(y0 + 0.5 * dt * k1, args)

    k3 = func(y0 + 0.5 * dt * k2, args)

    k4 = func(y0 + dt * k3, args)

    return y0 + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
