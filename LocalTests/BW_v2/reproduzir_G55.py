"""Refaz MIT_G a 55 Hz isoladamente (FOC original e FOC com ki_iqs+anti-
windup), para checar se a instabilidade relatada (velocidade negativa por
volta de t=18s) reproduz de forma determinística, fora do contexto de
execução em paralelo com outras simulações em que foi observada pela
primeira vez.

Salva com sufixo "_repro" (não sobrescreve os dados originais), e imprime
uma comparação lado a lado.

    python reproduzir_G55.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from inverter_foc_v2 import InverterFOCv2
from ross.motors import motor_element
from ross.motors.inverters import InverterFOC
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"

FATOR_BARRAMENTO = 1.414
TIME_STEP = 1e-6
FREQ_HZ = 55.0


def _com_barramento(fn, classe_foc, *args, **kwargs):
    original_bus = motor_element.line_to_dc_bus
    original_foc = motor_element.InverterFOC
    motor_element.line_to_dc_bus = lambda v_line: v_line * FATOR_BARRAMENTO
    motor_element.InverterFOC = classe_foc
    try:
        return fn(*args, **kwargs)
    finally:
        motor_element.line_to_dc_bus = original_bus
        motor_element.InverterFOC = original_foc


def _rodar(classe_foc, sufixo):
    sim, construir_motor = motores.SIM_GRANDE, motores.motor_grande
    motor = construir_motor()
    t = sim.vetor_tempo()
    freq_ref = Q_(FREQ_HZ, "Hz")
    rampa_foc = sim.rampa_foc if sim.rampa_foc is not None else sim.rampa

    print(f"[G @ {FREQ_HZ:g} Hz] Simulando FOC ({classe_foc.__name__})...")
    r = _com_barramento(
        motor.run_with_inverter_foc, classe_foc, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=rampa_foc, frequency_ref=freq_ref,
    )
    caminho = DADOS / f"G_{FREQ_HZ:g}Hz_{sufixo}.npz"
    np.savez_compressed(
        caminho, t=r.t, velocidade_rpm=r.speed * 60.0 / (2.0 * np.pi),
        conjugado=r.electric_torque, conjugado_carga=r.load_torque,
    )
    print(f"  [OK] {caminho}")
    return caminho


def _resumo(caminho):
    d = np.load(caminho)
    t, v, c = d["t"], d["velocidade_rpm"], d["conjugado"]
    m = t >= 13.0
    idx = np.argmin(v[m])
    mrip = t >= t[-1] - 1.0
    rip = c[mrip].max() - c[mrip].min()
    return dict(min_vel=float(v[m][idx]), t_min_vel=float(t[m][idx]), ripple_p2p=float(rip))


if __name__ == "__main__":
    c_base = _rodar(InverterFOC, "foc_repro")
    c_v2 = _rodar(InverterFOCv2, "foc_v2_repro")

    print("\n=== Comparação (rodada anterior vs. reprodução) ===")
    anteriores = dict(
        base=dict(min_vel=-697.54, t_min_vel=18.635, ripple_p2p=74902.1),
        v2=dict(min_vel=-2199.33, t_min_vel=17.816, ripple_p2p=1035911.5),
    )
    for nome, caminho in (("base", c_base), ("v2", c_v2)):
        novo = _resumo(caminho)
        ant = anteriores[nome]
        print(f"{nome}: anterior min_vel={ant['min_vel']:.2f} @ t={ant['t_min_vel']:.3f}, "
              f"ripple_p2p={ant['ripple_p2p']:.1f}")
        print(f"{nome}: reprod.  min_vel={novo['min_vel']:.2f} @ t={novo['t_min_vel']:.3f}, "
              f"ripple_p2p={novo['ripple_p2p']:.1f}")
