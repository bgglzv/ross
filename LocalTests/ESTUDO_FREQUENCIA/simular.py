"""Simula DOL, V/F e FOC para um motor (P ou G) numa dada frequência de referência.

Usa os parâmetros já validados nos ensaios anteriores desta pasta de trabalho:
chaveamento a 5 kHz, passo interno de simulação de 1e-6 s (200 amostras por
período) e barramento CC de 1,414 x V_linha. A partida direta (DOL) só roda
para a frequência nominal (60 Hz): a fonte de rede não admite referência de
frequência reduzida.

    python simular.py P 60
    python simular.py P 55
    python simular.py G 30
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from ross.motors import motor_element
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"

FATOR_BARRAMENTO = 1.414
TIME_STEP = 1e-6

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno), "G": (motores.SIM_GRANDE, motores.motor_grande)}


def _com_barramento(fn, *args, **kwargs):
    """Roda `fn` com o fator de barramento substituindo, só durante a chamada,
    a conversão padrão da biblioteca (linha -> barramento CC)."""
    original = motor_element.line_to_dc_bus
    motor_element.line_to_dc_bus = lambda v_line: v_line * FATOR_BARRAMENTO
    try:
        return fn(*args, **kwargs)
    finally:
        motor_element.line_to_dc_bus = original


def _salvar(motor_id, freq_hz, cenario, r):
    DADOS.mkdir(parents=True, exist_ok=True)
    caminho = DADOS / f"{motor_id}_{freq_hz:g}Hz_{cenario}.npz"
    np.savez_compressed(
        caminho, t=r.t, velocidade_rpm=r.speed * 60.0 / (2.0 * np.pi),
        conjugado=r.electric_torque, conjugado_carga=r.load_torque,
        corrente_a=r.currents["a"],
    )
    print(f"  [OK] {caminho}")


def simular(motor_id, freq_hz):
    sim, construir_motor = MOTORES[motor_id]
    motor = construir_motor()
    t = sim.vetor_tempo()
    freq_ref = Q_(freq_hz, "Hz")
    nominal = abs(freq_hz - 60.0) < 1e-9

    if nominal:
        print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando partida direta (DOL)...")
        r = _com_barramento(
            motor.run_direct_on_line, t, time_step=sim.time_step_dol,
            load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0,
        )
        _salvar(motor_id, freq_hz, "dol", r)

    print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando inversor V/F...")
    r = _com_barramento(
        motor.run_with_inverter_vf, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=sim.rampa, frequency_ref=freq_ref,
    )
    _salvar(motor_id, freq_hz, "vf", r)

    print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando inversor FOC...")
    r = _com_barramento(
        motor.run_with_inverter_foc, t, frequency_s=sim.frequencia_chaveamento,
        time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=sim.rampa, frequency_ref=freq_ref,
    )
    _salvar(motor_id, freq_hz, "foc", r)


if __name__ == "__main__":
    simular(sys.argv[1], float(sys.argv[2]))
