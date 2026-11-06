"""Reroda só o cenário V/F (DOL e FOC não usam o trecho de código corrigido)
para as 8 combinações de motor x frequência, depois da correção do bug de
integração do ângulo de fase na rampa do V/F (reaplicada em
ross/motors/inverters.py — ver commit 3055ef3a no branch local-tests-sync,
que não estava presente neste branch).

    python resimular_vf.py
"""

from pathlib import Path

from ross.units import Q_
from simular import MOTORES, TIME_STEP, _com_barramento, _salvar

FREQS = (60.0, 55.0, 45.0, 30.0)

for motor_id in ("P", "G"):
    sim, construir_motor = MOTORES[motor_id]
    motor = construir_motor()
    t = sim.vetor_tempo()
    for freq_hz in FREQS:
        print(f"[{motor_id} @ {freq_hz:g} Hz] Simulando inversor V/F (re-simulação pós-correção)...")
        r = _com_barramento(
            motor.run_with_inverter_vf, t, frequency_s=sim.frequencia_chaveamento,
            time_step=TIME_STEP, load_torque_entrance_time=sim.t_carga,
            load_torque_ratio=1.0, time_ramp=sim.rampa, frequency_ref=Q_(freq_hz, "Hz"),
        )
        _salvar(motor_id, freq_hz, "vf", r)
