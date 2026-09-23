"""pi_robustness_common.py — Métricas de resposta ao degrau (protocolo "Robustez da Sintonia PI").

Implementa apenas a camada de **análise** do protocolo de ensaios descrito
no documento "Robustez da Sintonia PI" (comparação V/F vs. FOC, degrau de
carga com referência de velocidade constante — seções "06" e "07" do
protocolo): tempo de acomodação, erro de regime permanente, sobressinal e
classificação de convergência, a partir de resultados já simulados.

Este módulo **não constrói nem modifica inversores**: os cenários devem
ser gerados normalmente, motor a motor, através da API pública já usada em
`MIT_RePlan_Comparativo1.py` / `MIT_RePlan_Comparativo2.py`
(`motor.run_direct_on_line()`, `motor.run_with_inverter_vf()`,
`motor.run_with_inverter_foc()`) — cada inversor sempre usa sua própria
sintonia PI auto-calculada pelo método de bandwidth já implementado em
`ross.motors.inverters.InverterFOC`. Este módulo nunca lê nem sobrescreve
ganhos PI.

Não é executado diretamente — apenas importado pelos scripts de estudo de
caso (ex.: `pi_robustness_case_study.py`, `TPIM_Comparativo1.py`).
"""

import numpy as np
import pandas as pd

# =============================================================================
# Métricas de resposta ao degrau (seção "07 — Métricas" do protocolo)
# =============================================================================

#: Janela padrão (tempo) do filtro de média móvel aplicado antes de medir
#: acomodação/sobressinal. O sinal bruto de torque carrega, além do ripple
#: de chaveamento SVPWM (kHz), uma pulsação de torque de baixa ordem
#: inerente ao próprio acionamento (poucas centenas de Hz) que persiste
#: mesmo em regime saudável — nenhuma das duas é a "oscilação de malha"
#: que o protocolo quer detectar (seção "06": dinâmica com constantes de
#: tempo de dezenas de ms a ~1 s). 50 ms filtra ambas sem borrar essa
#: dinâmica, mais lenta.
DEFAULT_SMOOTH_TIME = 0.05

#: Faixa padrão de acomodação, em fração de |y_final| (seção "07" do
#: protocolo sugere ±2% ou ±5% "a definir e manter fixo"). Testado
#: empiricamente neste projeto: mesmo depois de filtrado (ver
#: `DEFAULT_SMOOTH_TIME`), o torque eletromagnético instantâneo de um
#: motor pequeno (ripple relativamente maior, em % do torque nominal, do
#: que um motor industrial de grande porte) raramente entra numa faixa de
#: ±2-5% de forma sustentada mesmo em regime saudável — 10% é o menor
#: valor que não classifica falsamente um cenário bem-comportado como "não
#: acomoda". Ajuste por motor/sinal se necessário, documentando a escolha.
DEFAULT_BAND = 0.10


def _smooth(t, y, smooth_time=DEFAULT_SMOOTH_TIME):
    """Filtro de média móvel (janela em tempo, não em amostras)."""
    if smooth_time <= 0:
        return y

    dt = np.median(np.diff(t))
    window = max(1, int(round(smooth_time / dt)))
    if window <= 1:
        return y

    kernel = np.ones(window) / window
    pad_left = window // 2
    pad_right = window - 1 - pad_left
    y_padded = np.pad(y, (pad_left, pad_right), mode="edge")
    return np.convolve(y_padded, kernel, mode="valid")


def settling_time(t, y, y_final, band=DEFAULT_BAND, t_start=0.0, smooth_time=DEFAULT_SMOOTH_TIME):
    """Tempo, a partir de `t_start`, até `y` (após filtragem do ripple de
    chaveamento — ver `_smooth`) entrar e permanecer dentro de
    `±band * |y_final|` até o final do registro. `np.inf` se nunca
    permanecer dentro da faixa até o fim."""
    y = _smooth(t, y, smooth_time)
    mask = t >= t_start
    tt, yy = t[mask], y[mask]
    if len(tt) == 0:
        return np.nan

    tol = band * abs(y_final) if y_final != 0 else band
    within = np.abs(yy - y_final) <= tol

    if within.all():
        return 0.0

    bad_idx = np.where(~within)[0]
    last_bad = bad_idx[-1]
    if last_bad == len(tt) - 1:
        return np.inf

    return tt[last_bad + 1] - t_start


def steady_state_error(t, y, y_final, t_start, tail_fraction=0.1):
    """Erro de regime permanente: média de `(y - y_final)` na fração final
    (`tail_fraction`) da janela de observação `[t_start, t[-1]]`."""
    mask = t >= t_start
    tt, yy = t[mask], y[mask]
    if len(tt) == 0:
        return np.nan

    window_start = tt[-1] - tail_fraction * (tt[-1] - tt[0])
    tail = yy[tt >= window_start]
    return float(np.mean(tail) - y_final)


def overshoot_and_oscillation(t, y, y_final, t_start, smooth_time=DEFAULT_SMOOTH_TIME):
    """Sobressinal (maior desvio absoluto em relação a `y_final`, em % de
    `y_final`) e número de cruzamentos pela referência, medidos sobre o
    sinal filtrado (ver `_smooth`). O número de cruzamentos é apenas
    informativo (útil para comparar cenários entre si) — ver
    `classify_convergence` para o porquê de não ser usado como limiar de
    classificação."""
    y = _smooth(t, y, smooth_time)
    mask = t >= t_start
    yy = y[mask]
    if len(yy) == 0:
        return {"overshoot_pct": np.nan, "n_crossings": 0}

    dev = yy - y_final
    peak = dev[np.argmax(np.abs(dev))]
    overshoot_pct = 100.0 * peak / y_final if y_final != 0 else np.nan
    n_crossings = int(np.count_nonzero(np.diff(np.sign(dev))))

    return {"overshoot_pct": float(overshoot_pct), "n_crossings": n_crossings}


def classify_convergence(
    t, y, y_final, band=DEFAULT_BAND, t_start=0.0, divergence_factor=5.0,
    smooth_time=DEFAULT_SMOOTH_TIME,
):
    """Classificação qualitativa (seção "06 — Ensaio 3" do protocolo):
    ``"converges"`` (entra e permanece na faixa de acomodação),
    ``"diverges"`` (não acomoda e ultrapassa `divergence_factor *
    |y_final|`), ou ``"does_not_settle"`` (não acomoda, mas sem
    crescimento explosivo)."""
    mask = t >= t_start
    if not mask.any():
        return "unknown"

    ts = settling_time(t, y, y_final, band=band, t_start=t_start, smooth_time=smooth_time)
    if np.isfinite(ts):
        return "converges"

    y_smooth = _smooth(t, y, smooth_time)
    max_abs = np.max(np.abs(y_smooth[mask]))
    if max_abs > divergence_factor * max(abs(y_final), 1e-9):
        return "diverges"
    return "does_not_settle"


def pre_step_baseline(t, y, t_start, window=0.05):
    """Valor médio de `y` na janela imediatamente anterior ao degrau
    (`[t_start - window, t_start)`). Útil como "valor final esperado" em
    ensaios de rejeição de distúrbio (degrau de carga com referência
    constante): o alvo não é um valor de placa idealizado, é o próprio
    regime em que o sinal já estava antes da perturbação — especialmente
    relevante para a velocidade, que tem um escorregamento (slip) próprio
    de cada tipo de acionamento (V/F em malha aberta x FOC em malha
    fechada) mesmo antes do degrau de carga.
    """
    mask = (t >= t_start - window) & (t < t_start)
    if not mask.any():
        idx = max(int(np.searchsorted(t, t_start)) - 1, 0)
        return float(y[idx])
    return float(np.mean(y[mask]))


def summarize_step_response(t, y, y_final, t_start, band=DEFAULT_BAND, smooth_time=DEFAULT_SMOOTH_TIME):
    """Agrega as quatro métricas do protocolo para uma única curva."""
    ov = overshoot_and_oscillation(t, y, y_final, t_start, smooth_time=smooth_time)
    return {
        "settling_time_s": settling_time(
            t, y, y_final, band=band, t_start=t_start, smooth_time=smooth_time
        ),
        "steady_state_error": steady_state_error(t, y, y_final, t_start),
        "overshoot_pct": ov["overshoot_pct"],
        "n_crossings": ov["n_crossings"],
        "convergence": classify_convergence(
            t, y, y_final, band=band, t_start=t_start, smooth_time=smooth_time
        ),
    }


# =============================================================================
# Tabela comparativa (Ensaio 3 do protocolo)
# =============================================================================


def build_comparison_table(scenarios, get_signal, y_final_by_scenario, test_name, t_start, band=DEFAULT_BAND):
    """Constrói a tabela comparativa do Ensaio 3 (métrica x cenário).

    Parameters
    ----------
    scenarios : dict[str, MotorResponseResults]
        Nome do cenário (ex.: "V/F Inverter", "FOC Inverter") -> resultado.
    get_signal : callable
        Recebe um `MotorResponseResults` e devolve o sinal a analisar
        (ex.: `lambda r: r.electric_torque`).
    y_final_by_scenario : dict[str, float]
        Valor final esperado do sinal, por cenário (ex.: torque de carga
        de referência de cada motor).
    test_name : str
        Rótulo do ensaio (ex.: "Degrau de carga - Torque").
    t_start : float
        Instante do degrau, usado como origem para as métricas.
    """
    rows = []
    for name, results in scenarios.items():
        y_final = y_final_by_scenario[name]
        summary = summarize_step_response(
            results.t, get_signal(results), y_final, t_start, band=band
        )
        rows.append({"Ensaio": test_name, "Cenário": name, **summary})
    return pd.DataFrame(rows)
