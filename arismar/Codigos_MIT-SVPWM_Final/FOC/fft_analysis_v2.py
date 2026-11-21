''' ===========================================================================
                  Windowed Fast Fourier Transform (FFT)

Espectro unilateral de amplitudes de pico, com remoção da média e zero-padding.

Janelas disponíveis (parâmetro window, sem distinção entre maiúsculas/minúsculas):
  'rectangular' : lóbulo principal estreito (2*df entre primeiros zeros),
                  primeiro lóbulo lateral ~ -13,3 dB; apropriada para
                  amostragem coerente (número inteiro de ciclos) e padding=1.
                  Fora dessas condições pode ocorrer vazamento intenso.
  'hann'        : lóbulo principal de ~4*df; primeiro lateral ~ -31,5 dB;
                  bom compromisso geral; pode criar máximos laterais na FFT.
  'hamming'     : lóbulo principal de ~4*df; primeiro lateral ~ -42,7 dB;
                  boa supressão do primeiro lóbulo, mas queda assintótica lenta.
  'blackman'    : lóbulo principal de ~6*df; primeiro lateral ~ -58 dB;
                  maior supressão lateral, com menor resolução entre picos.

  df = Fs/N (resolução física do registro, sem padding).
  O zero-padding interpola o espectro; não aumenta a resolução física.
  Valores de rejeição/largura são aproximados para registros longos.
  Todas as janelas usam normalização pela soma dos seus coeficientes.
  O bin DC contém abs(média original), não o coeficiente AC janelado.
============================================================================ '''

import numpy as np


def get_window(N, window='hann'):
    """Retorna os coeficientes da janela escolhida, de comprimento N."""
    if not isinstance(N, (int, np.integer)) or N < 3:
        raise ValueError('N deve ser inteiro >= 3.')
    if not isinstance(window, str):
        raise ValueError('window deve ser uma string.')
    kind = window.strip().lower()
    if kind in ('rectangular', 'retangular', 'boxcar', 'none'):
        return np.ones(N)
    if kind in ('hann', 'hanning'):
        return np.hanning(N)
    if kind == 'hamming':
        return np.hamming(N)
    if kind == 'blackman':
        return np.blackman(N)
    raise ValueError("window deve ser 'rectangular', 'hann', 'hamming' ou 'blackman'.")


def windowed_fft(signal, Fs, padding=8, window='hann'):
    """Retorna (freq, coef) da FFT unilateral complexa em amplitude de pico.

    A magnitude para gráficos e seleção é np.abs(coef). O coeficiente
    em 0 Hz contém a média original (com sinal), preservando a fase.
    """
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1 or not np.all(np.isfinite(signal)):
        raise ValueError('signal deve ser vetor unidimensional finito.')
    N = len(signal)
    if N < 3 or not isinstance(padding, (int, np.integer)) or padding < 1:
        raise ValueError('Use pelo menos 3 amostras e padding inteiro >= 1.')
    if not np.isfinite(Fs) or Fs <= 0:
        raise ValueError('Fs deve ser positiva e finita.')

    media = np.mean(signal)
    weights = get_window(N, window)
    N_fft = padding*N
    fft_values = np.fft.rfft((signal-media)*weights, n=N_fft)
    freq = np.fft.rfftfreq(N_fft, d=1/Fs)
    coef = fft_values / np.sum(weights)

    if N_fft % 2 == 0:
        coef[1:-1] *= 2
    else:
        coef[1:] *= 2
    coef[0] = media
    return freq, coef
