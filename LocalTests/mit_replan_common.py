"""mit_replan_common.py — Parâmetros compartilhados do MIT M-C-5283001 (REPLAN).

Módulo auxiliar usado por ``MIT_RePlan.py`` e pelos scripts comparativos
``MIT_RePlan_Comparativo1.py`` / ``MIT_RePlan_Comparativo2.py`` para garantir
que todos usem exatamente os mesmos parâmetros elétricos e de simulação.

Não é executado diretamente — apenas importado.
"""

import numpy as np

from ross.motors.motor_element import MotorElement
from ross.units import Q_


# =============================================================================
# Conversão p.u. → Ω
# =============================================================================


def pu_to_ohm(r1_pu, X1_pu, r2_pu, X2_pu, Xm_pu, voltage_line, current_rated):
    """Converte parâmetros do circuito equivalente de p.u. para Ohm.

    Calcula a impedância base pelo método da potência aparente trifásica:

        Sbase = √3 · Uₙ · Iₙ
        Zbase = Uₙ² / Sbase

    Cada parâmetro em p.u. é multiplicado por Zbase.
    A tensão de fase (linha-neutro) também é retornada, pois é o valor
    esperado por ``MotorElement`` nos campos ``voltage_nom`` e ``voltage_net``.

    Parameters
    ----------
    r1_pu : float
        Resistência do estator [pu].
    X1_pu : float
        Reatância de dispersão do estator [pu].
    r2_pu : float
        Resistência do rotor referida ao estator [pu].
    X2_pu : float
        Reatância de dispersão do rotor referida ao estator [pu].
    Xm_pu : float
        Reatância de magnetização [pu].
    voltage_line : float
        Tensão de linha nominal Uₙ [V].
    current_rated : float
        Corrente nominal de linha Iₙ [A].

    Returns
    -------
    dict
        Chaves: ``Sbase``, ``Zbase``, ``r1``, ``X1``, ``r2``, ``X2``,
        ``Xm``, ``voltage_phase`` — todos em SI (VA, Ω ou V).
    """
    Sbase = np.sqrt(3.0) * voltage_line * current_rated
    Zbase = voltage_line ** 2 / Sbase
    voltage_phase = voltage_line / np.sqrt(3.0)

    return {
        "Sbase":         Sbase,
        "Zbase":         Zbase,
        "r1":            r1_pu  * Zbase,
        "X1":            X1_pu  * Zbase,
        "r2":            r2_pu  * Zbase,
        "X2":            X2_pu  * Zbase,
        "Xm":            Xm_pu  * Zbase,
        "voltage_phase": voltage_phase,
    }


# =============================================================================
# Dados do motor M-C-5283001 (datasheet I-FD-5270.00-52313-712-BI4-102)
# =============================================================================

# --- Dados nominais (folha 2) ---
UN_LINE   = 4000.0   # V    (campo 9)
IN        = 422.7    # A    (campo 15)
PN_W      = 2474e3   # W    (campo 8)
FN_HZ     = 60.0     # Hz   (campo 10)
N_POLES   = 4        #      (campo 12)
SPEED_RPM = 1791.0   # rpm  (campo 12)
JP_MOTOR  = 57.5     # kg·m² (campo 37)
JP_LOAD   = 0.0      # kg·m² — inércia da carga omitida (ver MIT_RePlan.py)

# --- Parâmetros em p.u. — coluna Sₙ (folha 4, campos 102–107) ---
R1_PU = 0.005
X1_PU = 0.131
R2_PU = 0.005
X2_PU = 0.105
XM_PU = 3.363

# --- Parâmetros de simulação (idênticos em todos os scripts MIT_RePlan_*) ---
TF        = 24.0   # s   — tempo total
DT        = 1e-3   # s   — passo de avaliação
TIME_STEP = 1e-4   # s   — passo interno do integrador (todos os acionamentos)
T_LOAD    = 16.0   # s   — instante de aplicação da carga nominal

# --- Parâmetros específicos dos inversores (InverterVF / InverterFOC) ---
#
# FREQUENCY_S não é só a frequência de chaveamento SVPWM: no InverterFOC ela
# também define, via o método de bandwidth, os ganhos de TODAS as malhas de
# controle em cascata (BWp_iqs = BWp_ids = BWi_ids = FREQUENCY_S/8,
# BWp_w = BWi_ids/8, BWi_w = BWp_w/8). Baixá-la para "resolver" a amostragem
# numérica também desafina o controle: a 500 Hz a malha de velocidade fica
# com BWi_w ≈ 1 Hz, lenta demais para amortecer a resposta desta máquina de
# alta inércia, e o conjugado diverge (picos > 1 000 000 N·m). 2000 Hz dá
# larguras de banda compatíveis com o motor M-C-5283001 (57,5 kg·m²).
#
# Por isso o passo interno é deixado em ``None`` (não informado) nas
# chamadas de ``run_with_inverter_vf``/``run_with_inverter_foc``: cada
# método usa então seu próprio default, Ts/200 (Ts = 1/FREQUENCY_S) — a
# resolução que a própria biblioteca considera adequada para a modulação
# SVPWM. É mais lento (sobretudo no FOC, cujo laço fechado não é compilado
# via numba) do que um passo mais grosseiro, mas evita a instabilidade
# numérica observada com passos maiores.
FREQUENCY_S = Q_(2000.0, "Hz")

TIME_RAMP = 8.0   # s — rampa de aceleração até a referência,
                   # concluída bem antes de T_LOAD = 16 s


def build_motor(tag="M-C-5283001"):
    """Instancia o MotorElement do M-C-5283001 com os parâmetros do datasheet.

    Parameters
    ----------
    tag : str, optional
        Tag do motor. Default é "M-C-5283001".

    Returns
    -------
    motor : MotorElement
        Instância pronta para simulação.
    p : dict
        Dicionário retornado por :func:`pu_to_ohm`, útil para impressão dos
        parâmetros convertidos no console.
    """
    p = pu_to_ohm(R1_PU, X1_PU, R2_PU, X2_PU, XM_PU, UN_LINE, IN)

    motor = MotorElement(
        n=0,
        tag=tag,
        power_nom=PN_W,
        voltage_nom=p["voltage_phase"],      # tensão de fase RMS [V]
        speed_nom=Q_(SPEED_RPM, "RPM"),
        frequency_nom=Q_(FN_HZ, "Hz"),
        n_poles=N_POLES,
        stator_resistance=p["r1"],
        rotor_resistance=p["r2"],
        stator_reactance=p["X1"],
        rotor_reactance=p["X2"],
        mutual_reactance=p["Xm"],
        Ip_motor=JP_MOTOR,
        viscosity_coeff=0.0,
        Ip_load=JP_LOAD,
        voltage_net=p["voltage_phase"],
        frequency_net=Q_(FN_HZ, "Hz"),
    )

    return motor, p


def time_vector():
    """Retorna o vetor de tempo de avaliação comum a todos os cenários."""
    return np.arange(0.0, TF + DT, DT)
