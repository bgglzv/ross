"""Windowed Fast Fourier Transform (FFT)

Computes the FFT spectrum of a sampled signal using a window function.
"""

import numpy as np

def windowed_fft(signal, Fs):

    """
    Input parameters:
        signal : array_like
            Time domain signal.
        Fs : float
            Sample frequency [Hz].

    Output parameters:
        freq : ndarray
            Frequency array.
        mag : ndarray
            FFT magnitude.
    """

    signal = np.asarray(signal)

    N = len(signal)

    window = np.hanning(N)

    signal_windowed = signal * window

    fft_values = np.fft.fft(signal_windowed)

    freq = np.fft.fftfreq(N, d=1/Fs)

    coherent_gain = np.mean(window)

    mag = np.abs(fft_values) / (N * coherent_gain)

    idx = freq >= 0

    freq = freq[idx]
    mag = mag[idx]

    # Internal components duplicated
    if len(mag) > 2:
        mag[1:-1] *= 2

    return freq, mag