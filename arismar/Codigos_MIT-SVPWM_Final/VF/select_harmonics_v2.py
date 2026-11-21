''' ============================================================================
    Select spectral components above a relative amplitude threshold.

    Intended use: steady-state voltage, current and electromagnetic torque
    spectra from V/f and FOC induction-motor drives.

    Optional fundamental removal (voltage/current only):
      1. Locate the largest AC peak up to f_max (assumed fundamental).
      2. Refine its frequency by maximizing the fitted sinusoidal energy
         near that FFT peak; alternatively use a supplied f1.
      3. Fit sine, cosine and offset by least squares, subtract ONLY the sine.
      4. Recompute the residual FFT using the same window and zero-padding.
      5. Select peaks using the ORIGINAL amplitude reference and reinsert
         the fitted fundamental with its estimated peak amplitude.

    Arguments:
      freq, mag      : original one-sided FFT frequencies [Hz] and peak magnitudes
      thrs           : relative amplitude threshold [%], e.g. 0.1
      f_max          : upper frequency limit [Hz]
      signal_type    : 'voltage', 'current' or 'torque'
      remove_fundamental : enable the optional procedure (default False)
      signal, Fs     : time samples and sampling frequency; required if enabled
      f1             : optional known fundamental frequency [Hz]
      padding, window : MUST match the original windowed_fft() settings

    Returns: freq_sel, mag_sel (ascending frequency; peak amplitudes).

    Notes:
      - For voltage/current, the reference is the largest original AC peak.
      - For torque, the reference is the DC component, which is included.
      - The removed fundamental is reinserted in the result; the PSD should
        still be computed from the ORIGINAL signal.
      - This rejects sidelobes of the fitted fundamental, not sidelobes of
        other components; it cannot guarantee that every peak is physical.
      - Requires fft_analysis.py in the same project directory.
    ============================================================================ '''

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks
from fft_analysis_v2 import windowed_fft


def select_harmonics(freq, mag, thrs, f_max, signal_type,
                     remove_fundamental=False, signal=None, Fs=None,
                     f1=None, padding=8, window='hann'):
    freq = np.asarray(freq, dtype=float)
    mag = np.asarray(mag, dtype=float)
    if (freq.ndim != 1 or mag.shape != freq.shape or freq.size < 3
            or not np.all(np.isfinite(freq)) or not np.all(np.isfinite(mag))
            or np.any(np.diff(freq) <= 0) or np.any(mag < 0) or freq[0] < 0):
        raise ValueError('Invalid freq/mag vectors.')
    if not np.isfinite(thrs) or not 0 <= thrs <= 100:
        raise ValueError('thrs must be between 0 and 100%.')
    if not np.isfinite(f_max) or not 0 < f_max <= freq[-1]:
        raise ValueError('Invalid f_max.')
    if signal_type not in ('voltage', 'current', 'torque'):
        raise ValueError('Invalid signal_type.')
    if signal_type == 'torque' and not np.isclose(freq[0], 0):
        raise ValueError('Torque spectrum must include DC.')

    reference = mag[0] if signal_type == 'torque' else mag[freq > 0].max()
    threshold = thrs * reference / 100
    f_work, m_work = freq, mag
    fitted = None

    if remove_fundamental:
        if signal_type == 'torque':
            raise ValueError('Fundamental removal applies only to voltage/current.')
        if signal is None or Fs is None or not np.isfinite(Fs) or Fs <= 0:
            raise ValueError('Provide signal and positive Fs.')
        x = np.asarray(signal, dtype=float)
        if x.ndim != 1 or x.size < 3 or not np.all(np.isfinite(x)):
            raise ValueError('Invalid time-domain signal.')
        t = np.arange(x.size) / Fs
        y = x - x.mean()

        # Sinusoidal fit with a DC intercept, implemented by centering bases.
        def fit(f):
            angle = 2 * np.pi * f * t
            s = np.sin(angle); c = np.cos(angle)
            s -= s.mean(); c -= c.mean()
            a, b = np.linalg.lstsq(
                np.array([[s @ s, s @ c], [s @ c, c @ c]]),
                np.array([s @ y, c @ y]), rcond=None)[0]
            return a, b, float(a * (s @ y) + b * (c @ y))

        if f1 is None:
            candidates = np.flatnonzero((freq > 0) & (freq <= min(f_max, Fs / 2)))
            if candidates.size == 0:
                raise ValueError('No AC frequencies available for estimation.')
            k = candidates[np.argmax(mag[candidates])]
            f0 = freq[k]
            df = freq[1] - freq[0]
            lo, hi = max(1e-12, f0 - df), min(Fs / 2 * (1 - 1e-10), f0 + df)
            f1 = (minimize_scalar(lambda f: -fit(f)[2], bounds=(lo, hi),
                                  method='bounded').x if hi > lo else f0)
        if not np.isfinite(f1) or not 0 < f1 < Fs / 2:
            raise ValueError('Invalid fundamental frequency.')
        a, b, _ = fit(f1)
        amplitude = float(np.hypot(a, b))
        residual = x - a * np.sin(2 * np.pi * f1 * t) - b * np.cos(2 * np.pi * f1 * t)
        f_work, fft_residual = windowed_fft(residual, Fs, padding=padding, window=window)
        # A FFT retorna coeficientes complexos; a seleção exige magnitudes reais.
        m_work = np.abs(fft_residual)
        if f_work.shape != freq.shape or not np.allclose(f_work, freq, rtol=1e-9, atol=1e-8):
            raise ValueError('Original FFT and residual FFT grids differ.')
        fitted = (float(f1), amplitude)

    # scipy.signal.find_peaks handles ordinary peaks and flat plateaus.
    idx, _ = find_peaks(m_work)
    f_min = f_work[1] if signal_type == 'torque' else 0.0
    idx = idx[(f_work[idx] > f_min) & (f_work[idx] <= f_max)
              & (m_work[idx] > threshold)]
    selected_f, selected_m = f_work[idx], m_work[idx]

    if signal_type == 'torque':
        selected_f = np.r_[0., selected_f]
        selected_m = np.r_[mag[0], selected_m]
    if fitted is not None and fitted[0] <= f_max and fitted[1] > threshold:
        # Only suppress a residual duplicate within half a physical FFT bin.
        guard = Fs / len(signal) / 2
        keep = abs(selected_f - fitted[0]) > guard
        selected_f = np.r_[selected_f[keep], fitted[0]]
        selected_m = np.r_[selected_m[keep], fitted[1]]
        order = np.argsort(selected_f)
        selected_f, selected_m = selected_f[order], selected_m[order]
    return selected_f, selected_m
