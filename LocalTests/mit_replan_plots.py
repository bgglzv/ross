"""mit_replan_plots.py — Gráficos comparativos entre cenários de acionamento.

Módulo auxiliar usado pelos scripts ``MIT_RePlan_Comparativo1.py`` e
``MIT_RePlan_Comparativo2.py``. Constrói, para uma mesma grandeza física
(conjugado, velocidade, corrente de fase A, tensão de linha AB), uma única
figura Plotly sobrepondo um traço por cenário de acionamento (fonte AC direta,
inversor V/F, inversor FOC), tanto no domínio do tempo quanto da frequência.

Não é executado diretamente — apenas importado.
"""

import os
import shutil

import numpy as np
from plotly import graph_objects as go

from ross.motors.utils import windowed_dfft


# Traços no domínio do tempo vêm na resolução interna do integrador (ex.:
# Ts/200 do FOC, ~2,5e-6 s), o que produz milhões de pontos por cenário e
# estoura tanto o tamanho do HTML quanto o motor de exportação de PNG
# (Kaleido). Decimamos por min/max binning antes de plotar (preserva picos
# transitórios, ao contrário de um stride simples que poderia pular por
# cima de um spike estreito) — não afeta os resultados da simulação, só a
# resolução visual do gráfico.
MAX_TIME_POINTS = 20_000


def _decimate(x, y):
    n_bins = MAX_TIME_POINTS // 2
    if len(x) <= 2 * n_bins:
        return x, y

    bin_size = len(x) // n_bins
    n_trimmed = n_bins * bin_size
    y_bins = y[:n_trimmed].reshape(n_bins, bin_size)

    argmin = np.argmin(y_bins, axis=1)
    argmax = np.argmax(y_bins, axis=1)
    rows = np.arange(n_bins)
    lo, hi = np.minimum(argmin, argmax), np.maximum(argmin, argmax)

    idx = np.empty(2 * n_bins, dtype=np.intp)
    idx[0::2] = rows * bin_size + lo
    idx[1::2] = rows * bin_size + hi
    idx.sort()

    return x[:n_trimmed][idx], y[:n_trimmed][idx]


# =============================================================================
# Extratores de grandeza — cada um recebe um MotorResponseResults e devolve
# o sinal correspondente, já na unidade de interesse.
# =============================================================================


def get_electric_torque(results):
    """Conjugado eletromagnético [N·m]."""
    return results.electric_torque


def get_load_torque(results):
    """Conjugado de carga [N·m]."""
    return results.load_torque


def get_speed_rpm(results):
    """Velocidade do rotor [RPM]."""
    return results.speed * 60.0 / (2.0 * np.pi)


def get_current_a(results):
    """Corrente de estator na fase A [A]."""
    return results.currents["a"]


def get_line_voltage_ab(results):
    """Tensão de linha entre as fases A e B [V]."""
    return results.line_voltages["ab"]


# =============================================================================
# Construção das figuras comparativas
# =============================================================================


def _window(x, y, xlim):
    """Recorta `(x, y)` para o intervalo fechado `xlim = (x_min, x_max)`."""
    mask = (x >= xlim[0]) & (x <= xlim[1])
    return x[mask], y[mask]


def compare_time(results_by_scenario, get_signal, title, yaxis_title,
                  reference_signal=None, reference_name=None, xlim=None):
    """Sobrepõe, no domínio do tempo, o mesmo sinal para vários cenários.

    Parameters
    ----------
    results_by_scenario : dict[str, MotorResponseResults]
        Mapeia o nome do cenário (usado como legenda) ao seu resultado.
    get_signal : callable
        Função que recebe um ``MotorResponseResults`` e devolve o sinal
        (array 1D, mesmo comprimento de ``results.t``) a ser plotado.
    title : str
        Título da figura.
    yaxis_title : str
        Rótulo do eixo Y (com unidade).
    reference_signal : callable, optional
        Se informado, adiciona um traço tracejado único de referência
        (por exemplo, o conjugado de carga, igual em todos os cenários),
        computado a partir do primeiro cenário do dicionário.
    reference_name : str, optional
        Nome do traço de referência. Obrigatório se ``reference_signal``
        for informado.
    xlim : tuple[float, float], optional
        Se informado, recorta todos os traços a este intervalo de tempo
        antes de decimar e trava os eixos X e Y a essa janela (zoom real,
        com a escala vertical ajustada aos dados visíveis — não apenas um
        recorte visual sobre a figura inteira).

    Returns
    -------
    plotly.graph_objects.Figure
    """
    fig = go.Figure()
    windowed_y = []

    for scenario_name, results in results_by_scenario.items():
        t, y = results.t, get_signal(results)
        if xlim is not None:
            t, y = _window(t, y, xlim)
        x, y = _decimate(t, y)
        windowed_y.append(y)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name=scenario_name,
            )
        )

    if reference_signal is not None:
        first_results = next(iter(results_by_scenario.values()))
        t, y = first_results.t, reference_signal(first_results)
        if xlim is not None:
            t, y = _window(t, y, xlim)
        x, y = _decimate(t, y)
        windowed_y.append(y)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name=reference_name,
                line=dict(dash="dash", color="black"),
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Tempo (s)",
        yaxis_title=yaxis_title,
    )

    if xlim is not None:
        fig.update_xaxes(range=list(xlim))
        y_all = np.concatenate(windowed_y) if windowed_y else np.array([0.0])
        y_min, y_max = float(np.min(y_all)), float(np.max(y_all))
        pad = 0.05 * (y_max - y_min) if y_max > y_min else 1.0
        fig.update_yaxes(range=[y_min - pad, y_max + pad])

    return fig


def compare_frequency(results_by_scenario, get_signal, title, yaxis_title,
                       frequency_units="Hz"):
    """Sobrepõe, no domínio da frequência, o mesmo sinal para vários cenários.

    Usa :func:`ross.motors.utils.windowed_dfft`, a mesma rotina de FFT
    utilizada internamente pelos métodos ``plot_*(domain="frequency")`` de
    ``MotorResponseResults``, garantindo resultados consistentes com os
    demais gráficos do pacote (janela de Hanning, escala de espectro
    unilateral).

    Parameters
    ----------
    results_by_scenario : dict[str, MotorResponseResults]
        Mapeia o nome do cenário (usado como legenda) ao seu resultado.
    get_signal : callable
        Função que recebe um ``MotorResponseResults`` e devolve o sinal no
        domínio do tempo a ser transformado.
    title : str
        Título da figura.
    yaxis_title : str
        Rótulo do eixo Y (com unidade).
    frequency_units : str, optional
        Unidade do eixo X. Default é "Hz".

    Returns
    -------
    plotly.graph_objects.Figure
    """
    fig = go.Figure()

    for scenario_name, results in results_by_scenario.items():
        dt = results.t[1] - results.t[0]
        freq, mag = windowed_dfft(get_signal(results), dt)
        freq, mag = _decimate(freq, mag)
        fig.add_trace(
            go.Scatter(
                x=freq,
                y=mag,
                name=scenario_name,
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title=f"Frequência ({frequency_units})",
        yaxis_title=yaxis_title,
    )

    return fig


# =============================================================================
# Gravação em disco
# =============================================================================


def reset_output_dir(output_dir):
    """Apaga e recria ``output_dir``, garantindo que a execução não misture
    figuras de rodadas anteriores."""
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)


def save_figure(fig, output_dir, basename):
    """Grava ``fig`` como HTML e PNG em ``output_dir`` e confirma no console."""
    html_path = os.path.join(output_dir, f"{basename}.html")
    png_path = os.path.join(output_dir, f"{basename}.png")
    fig.write_html(html_path)
    fig.write_image(png_path)
    print(f"  [OK] {html_path}")
    print(f"  [OK] {png_path}")
