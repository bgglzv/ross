"""Simula só o FOC com InverterFOCv4(C) — kp/ki de iqs, ids e w escalados
por uma constante universal C que preserva o fator de amortecimento de cada
malha — para um motor (P ou G), numa frequência de referência dada
(default 60 Hz, usado na varredura de C; as demais frequências entram
depois de C estabilizado).

    python simular_v4.py P 1.2
    python simular_v4.py G 1.5
    python simular_v4.py G 4.0 30
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from inverter_foc_v4 import InverterFOCv4
from ross.motors import motor_element
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"

FATOR_BARRAMENTO = 1.414
TIME_STEP = 1e-6

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno), "G": (motores.SIM_GRANDE, motores.motor_grande)}


def _classe_com_C(C):
    """`isinstance(element, InverterFOC)` (usado em motor_element.py) exige
    que o nome monkeypatchado seja uma classe de verdade, não uma lambda —
    por isso uma subclasse com C fixo, em vez de uma factory function."""
    class _InverterFOCv4ComC(InverterFOCv4):
        def __init__(self, *a, **kw):
            kw.setdefault("C", C)
            super().__init__(*a, **kw)
    return _InverterFOCv4ComC


def _com_barramento_e_foc_v4(fn, C, *args, **kwargs):
    original_bus = motor_element.line_to_dc_bus
    original_foc = motor_element.InverterFOC
    motor_element.line_to_dc_bus = lambda v_line: v_line * FATOR_BARRAMENTO
    motor_element.InverterFOC = _classe_com_C(C)
    try:
        return fn(*args, **kwargs)
    finally:
        motor_element.line_to_dc_bus = original_bus
        motor_element.InverterFOC = original_foc


def _salvar(motor_id, freq_hz, C, r):
    DADOS.mkdir(parents=True, exist_ok=True)
    caminho = DADOS / f"{motor_id}_{freq_hz:g}Hz_foc_v4_C{C:g}.npz"
    np.savez_compressed(
        caminho, t=r.t, velocidade_rpm=r.speed * 60.0 / (2.0 * np.pi),
        conjugado=r.electric_torque, conjugado_carga=r.load_torque,
        iq=r.currents["q"], id=r.currents["d"],
    )
    print(f"  [OK] {caminho}")


def simular(motor_id, C, freq_hz=60.0):
    sim, construir_motor = MOTORES[motor_id]
    motor = construir_motor()
    t = sim.vetor_tempo()
    freq_ref = Q_(freq_hz, "Hz")
    rampa_foc = sim.rampa_foc if sim.rampa_foc is not None else sim.rampa

    print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando FOC com C={C:g} (BW_v4)...")
    r = _com_barramento_e_foc_v4(
        motor.run_with_inverter_foc, C, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=rampa_foc, frequency_ref=freq_ref,
    )
    _salvar(motor_id, freq_hz, C, r)


if __name__ == "__main__":
    freq_arg = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    simular(sys.argv[1], float(sys.argv[2]), freq_arg)
