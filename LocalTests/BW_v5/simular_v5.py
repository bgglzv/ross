"""Simula só o FOC com InverterFOCv5 — kp/ki de iqs e ids recalculados a
partir dos parâmetros físicos do motor (polo elétrico da planta), não de
uma constante achada por varredura — para um motor (P ou G), a 60 Hz
(escopo desta rodada).

    python simular_v5.py P
    python simular_v5.py G
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from inverter_foc_v5 import InverterFOCv5
from ross.motors import motor_element
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"

FATOR_BARRAMENTO = 1.414
TIME_STEP = 1e-6

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno), "G": (motores.SIM_GRANDE, motores.motor_grande)}


def _com_barramento_e_foc_v5(fn, *args, **kwargs):
    original_bus = motor_element.line_to_dc_bus
    original_foc = motor_element.InverterFOC
    motor_element.line_to_dc_bus = lambda v_line: v_line * FATOR_BARRAMENTO
    motor_element.InverterFOC = InverterFOCv5
    try:
        return fn(*args, **kwargs)
    finally:
        motor_element.line_to_dc_bus = original_bus
        motor_element.InverterFOC = original_foc


def _salvar(motor_id, freq_hz, r):
    DADOS.mkdir(parents=True, exist_ok=True)
    caminho = DADOS / f"{motor_id}_{freq_hz:g}Hz_foc_v5.npz"
    np.savez_compressed(
        caminho, t=r.t, velocidade_rpm=r.speed * 60.0 / (2.0 * np.pi),
        conjugado=r.electric_torque, conjugado_carga=r.load_torque,
        iq=r.currents["q"], id=r.currents["d"],
    )
    print(f"  [OK] {caminho}")


def simular(motor_id, freq_hz=60.0):
    sim, construir_motor = MOTORES[motor_id]
    motor = construir_motor()
    t = sim.vetor_tempo()
    freq_ref = Q_(freq_hz, "Hz")
    rampa_foc = sim.rampa_foc if sim.rampa_foc is not None else sim.rampa

    print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando FOC com ganhos motor-aware (BW_v5)...")
    r = _com_barramento_e_foc_v5(
        motor.run_with_inverter_foc, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=rampa_foc, frequency_ref=freq_ref,
    )
    _salvar(motor_id, freq_hz, r)


if __name__ == "__main__":
    freq_arg = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    simular(sys.argv[1], freq_arg)
