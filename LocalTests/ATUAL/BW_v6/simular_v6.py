"""Simula o FOC com InverterFOCv6 (BW_v6) — ganhos motor-aware do BW_v5 +
filtro síncrono de iqs/ids (média móvel de um período de chaveamento) —
para um motor (P ou G), numa frequência de referência dada.

    python simular_v6.py P 30
    python simular_v6.py G 60
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from inverter_foc_v6 import InverterFOCv6
from ross.motors import motor_element
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"

FATOR_BARRAMENTO = 1.414
TIME_STEP = 1e-6

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno), "G": (motores.SIM_GRANDE, motores.motor_grande)}


def _com_barramento_e_foc_v6(fn, *args, **kwargs):
    original_bus = motor_element.line_to_dc_bus
    original_foc = motor_element.InverterFOC
    motor_element.line_to_dc_bus = lambda v_line: v_line * FATOR_BARRAMENTO
    motor_element.InverterFOC = InverterFOCv6
    try:
        return fn(*args, **kwargs)
    finally:
        motor_element.line_to_dc_bus = original_bus
        motor_element.InverterFOC = original_foc


def _salvar(motor_id, freq_hz, r):
    DADOS.mkdir(parents=True, exist_ok=True)
    caminho = DADOS / f"{motor_id}_{freq_hz:g}Hz_foc_v6.npz"
    np.savez_compressed(
        caminho, t=r.t, velocidade_rpm=r.speed * 60.0 / (2.0 * np.pi),
        conjugado=r.electric_torque, conjugado_carga=r.load_torque,
        iq=r.currents["q"], id=r.currents["d"],
    )
    print(f"  [OK] {caminho}")


def simular(motor_id, freq_hz):
    sim, construir_motor = MOTORES[motor_id]
    motor = construir_motor()
    t = sim.vetor_tempo()
    freq_ref = Q_(freq_hz, "Hz")
    rampa_foc = sim.rampa_foc if sim.rampa_foc is not None else sim.rampa

    print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando FOC com filtro sincrono iqs/ids (BW_v6)...")
    r = _com_barramento_e_foc_v6(
        motor.run_with_inverter_foc, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=rampa_foc, frequency_ref=freq_ref,
    )
    _salvar(motor_id, freq_hz, r)


if __name__ == "__main__":
    simular(sys.argv[1], float(sys.argv[2]))
