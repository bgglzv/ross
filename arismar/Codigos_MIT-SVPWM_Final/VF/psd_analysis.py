"""Converte a FFT de amplitude de fft_analysis.windowed_fft para PSD.

Convenção exigida: média removida antes da janela escolhida; amplitudes
normalizadas por sum(window); espectro unilateral de PICO; DC/Nyquist
não duplicados; mag[0] substituído pelo módulo da média; padding inteiro.
Não é uma conversão genérica para qualquer normalização de FFT.
"""
import warnings
import numpy as np
from fft_analysis_v2 import get_window


def calculate_psd(freq, mag, N_janela, *, dc_ac=None, window='hann'):
    """Retorna PSD unilateral da parte AC [unidade²/Hz], na grade freq.

    freq, mag: resultados COMPLETOS de windowed_fft, até Nyquist.
    N_janela: número de amostras ORIGINAIS, antes do zero-padding.
    O passo freq[1]-freq[0] e o padding permitem inferir Fs e N_fft.
    Nenhuma FFT adicional é realizada.

    window: mesma janela usada em windowed_fft.

    dc_ac: módulo do coeficiente DC da FFT do sinal sem média, dividido
    por sum(get_window(N_janela, window)). windowed_fft sobrescreve este valor
    por abs(mean(signal)); por isso mag[0] sozinho não permite recuperá-lo.
    Para conversão exata, forneça:
        abs(sum((signal-mean(signal))*window))/sum(window)
    Se omitido, o bin DC da PSD é zerado com aviso; bins positivos
    continuam exatos. Não se inclui a média física nesta PSD AC.
    Informe a média separadamente, especialmente para torque.
    """
    f = np.asarray(freq, dtype=float)
    a = np.asarray(mag, dtype=float)
    if (f.ndim != 1 or a.shape != f.shape or f.size < 3
            or not np.all(np.isfinite(f)) or not np.all(np.isfinite(a))
            or np.any(a < 0)):
        raise ValueError('freq e mag devem ser vetores finitos de mesmo tamanho; mag >= 0.')
    if not isinstance(N_janela, (int, np.integer)) or N_janela < 3:
        raise ValueError('N_janela deve ser inteiro >= 3, sem zero-padding.')
    df = f[1]-f[0]
    if (df <= 0 or not np.isclose(f[0], 0, atol=1e-12)
            or not np.allclose(np.diff(f), df, rtol=1e-7, atol=1e-12)):
        raise ValueError('A grade deve ser uniforme e começar em zero.')
    # Unique parity/padding compatible with a full rFFT and integer padding.
    candidates = [n for n in (2*(f.size-1), 2*f.size-1)
                  if n >= N_janela and n % N_janela == 0]
    if len(candidates) != 1:
        raise ValueError('Use a FFT completa com padding inteiro, sem recortar freq/mag.')
    n_fft = candidates[0]
    Fs = df*n_fft
    weights = get_window(N_janela, window)
    factor = np.sum(weights)**2/(Fs*np.sum(weights**2))
    # mag is doubled on positive interior bins; power must be doubled only once.
    density = a*a*(factor/2)
    if n_fft % 2 == 0:
        density[-1] *= 2
    if dc_ac is None:
        warnings.warn('DC AC não fornecido: PSD[0]=0; a média não integra a PSD AC.',
                      RuntimeWarning, stacklevel=2)
        density[0] = 0.0
    else:
        if not np.isscalar(dc_ac) or not np.isfinite(dc_ac) or dc_ac < 0:
            raise ValueError('dc_ac deve ser escalar finito não negativo.')
        density[0] = dc_ac**2*factor
    return density


def psd_bands(freq, psd, band_width, f_max):
    """Retorna bordas, integral da PSD e RMS por faixas consecutivas.

    Sem limiar. [fi,ff), última faixa inclui ff. Cada bin é atribuído
    pelo centro; a faixa final pode ser menor. Faixas muito estreitas
    não melhoram a resolução efetiva do registro (aprox. Fs/N_janela).
    """
    f = np.asarray(freq, dtype=float)
    p = np.asarray(psd, dtype=float)
    if (f.ndim != 1 or f.size < 2 or p.shape != f.shape
            or not np.all(np.isfinite(f)) or not np.all(np.isfinite(p))
            or np.any(p < 0)):
        raise ValueError('freq e psd inválidos.')
    df = f[1]-f[0]
    if df <= 0 or not np.isclose(f[0], 0) or not np.allclose(np.diff(f), df):
        raise ValueError('A grade deve ser uniforme e começar em zero.')
    if not np.isfinite(band_width) or band_width <= 0:
        raise ValueError('band_width deve ser positiva.')
    if not np.isfinite(f_max) or not 0 < f_max <= f[-1]+df/2+1e-10*max(1.0, f[-1]):
        raise ValueError('f_max fora do intervalo disponível.')
    edges = np.r_[np.arange(0, f_max, band_width), f_max]
    mask = f <= f_max
    indices = np.searchsorted(edges, f[mask], side='right')-1
    indices = np.minimum(indices, len(edges)-2)
    ms = np.bincount(indices, weights=p[mask]*df, minlength=len(edges)-1)
    return edges, ms, np.sqrt(ms)
