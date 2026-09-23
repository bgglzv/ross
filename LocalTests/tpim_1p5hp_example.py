"""tpim_1p5hp_example.py — Motor recuperado de tutorial_motor_part_1/2/3.ipynb.

Reempacota, como módulo importável (fora do notebook), o motor usado nas
Seções 2-4 dos tutoriais oficiais do pacote (`docs/user_guide/
tutorial_motor_part_1.ipynb` a `tutorial_motor_part_3.ipynb`): um motor de
indução trifásico de **1.5 hp / 127 V / 60 Hz / 4 polos**, velocidade
nominal **1710 RPM**, parâmetros de circuito equivalente informados
diretamente (não convertidos de p.u. como em `mit_replan_common.py` — os
tutoriais já usam valores em Ohm/H diretamente).

Same building-block role as `mit_replan_common.build_motor()`, mas para o
motor pequeno dos tutoriais, permitindo reutilizá-lo em outros scripts de
`LocalTests/` (ex.: `pi_robustness_study_replan_vs_tpim.py`) sem duplicar
os parâmetros a cada vez.

Não é executado diretamente — apenas importado.
"""

import numpy as np

from ross.motors.motor_element import MotorElement
from ross.units import Q_

# --- Dados nominais (tutorial_motor_part_1.ipynb, Seção 2.1) ---
POWER_NOM = Q_(1.5, "hp")
VOLTAGE_NOM = 127.0   # V (tensão de fase, RMS)
SPEED_RPM = 1710.0    # rpm
FN_HZ = 60.0          # Hz
N_POLES = 4

# --- Parâmetros de circuito equivalente (Ohm / kg.m²) ---
STATOR_RESISTANCE = 2.5    # Ohm
ROTOR_RESISTANCE = 1.8     # Ohm
STATOR_REACTANCE = 1.3     # Ohm (a frequência nominal)
ROTOR_REACTANCE = 1.3      # Ohm (a frequência nominal)
MUTUAL_REACTANCE = 43.08   # Ohm (a frequência nominal)
IP_MOTOR = 0.0372          # kg.m²
IP_LOAD = 0.0

# --- Parâmetros de inversor sugeridos pelos tutoriais (Seções 3-4) ---
# Fs=5000 Hz e time_step=1e-5 (Ts/20, mais grosseiro que o default Ts/200)
# já validados nos tutoriais para este motor pequeno — ao contrário do
# motor grande do MIT_RePlan, aqui esse passo não causa instabilidade
# numérica na malha FOC/V-F (ver `mit_replan_common.py` para o contraste).
FREQUENCY_S = Q_(5000.0, "Hz")
TUTORIAL_TIME_STEP = 1e-5
TIME_RAMP = 0.6667   # s

# --- Parâmetros de simulação (mesmos usados nos tutoriais, tf=3.0 s) ---
TF = 3.0             # s — tempo total
DT = 1e-3            # s — passo de avaliação (ver run() em motor_element.py:
                     #     a saída real fica na resolução de time_step, não em DT)
T_LOAD = 1.5         # s — instante de aplicação da carga nominal

# --- Janela de zoom (gráficos no tempo) em torno de T_LOAD ---
ZOOM_BEFORE_S = 0.1   # s — antes da entrada da carga
ZOOM_AFTER_S  = 0.2   # s — depois da entrada da carga


def build_motor(tag="TPIM_1p5hp"):
    """Instancia o `MotorElement` de 1.5 hp usado em
    `tutorial_motor_part_1/2/3.ipynb`.

    Parameters
    ----------
    tag : str, optional
        Tag do motor. Default é "TPIM_1p5hp".

    Returns
    -------
    motor : MotorElement
    """
    return MotorElement(
        n=0,
        tag=tag,
        power_nom=POWER_NOM,
        voltage_nom=VOLTAGE_NOM,
        speed_nom=Q_(SPEED_RPM, "RPM"),
        frequency_nom=Q_(FN_HZ, "Hz"),
        n_poles=N_POLES,
        stator_resistance=STATOR_RESISTANCE,
        rotor_resistance=ROTOR_RESISTANCE,
        stator_reactance=STATOR_REACTANCE,
        rotor_reactance=ROTOR_REACTANCE,
        mutual_reactance=MUTUAL_REACTANCE,
        Ip_motor=IP_MOTOR,
        viscosity_coeff=0.0,
        Ip_load=IP_LOAD,
        voltage_net=VOLTAGE_NOM,
        frequency_net=Q_(FN_HZ, "Hz"),
    )


def time_vector(tf=3.0, dt=1e-3):
    """Vetor de tempo de avaliação (default: mesmo usado nos tutoriais)."""
    return np.arange(0.0, tf + dt, dt)


if __name__ == "__main__":
    motor = build_motor()
    t = time_vector()
    results = motor.run_direct_on_line(
        t, load_torque_entrance_time=1.5, load_torque_ratio=1.0
    )
    print(f"Tnom = {motor.Tnom:.4f} N.m")
    print(f"Speed final = {results.speed[-1] * 60 / (2 * np.pi):.2f} RPM")
