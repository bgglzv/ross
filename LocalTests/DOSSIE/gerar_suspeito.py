"""Regenera, com a mesma análise/anotações do teste original, as saídas do "SUSPEITO".

O "suspeito" é o estado arquivado da branch local-tests-sync (tag
arquivo/local-tests-sync-suspeito): biblioteca com a correção de fase do
InverterVF e sintonia nova do FOC (InverterFOCNovo). Este script deve ser
executado com PYTHONPATH apontando para um checkout (worktree) dessa tag e a
partir de um diretório fora do repositório principal — senão o Python importa a
biblioteca do repositório atual em vez da arquivada:

    PYTHONPATH=<worktree> python gerar_suspeito.py <worktree>
"""

import inspect
import os
import sys
import time
from pathlib import Path

WORKTREE = Path(sys.argv[1]).resolve()
LOCALTESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCALTESTS))
sys.path.append(str(WORKTREE / "LocalTests"))

from ross.motors.inverters import InverterVF

assert "frequency * t / 2" in inspect.getsource(InverterVF), (
    "A biblioteca importada NÃO é a do suspeito (falta a correção de fase do V/F)."
)

from ross.motors.utils import line_to_dc_bus, phase_to_line
from ross.units import Q_

import inverter_foc_novo as novo
from comum import executar, motores

PASTA = LOCALTESTS / "DOSSIE" / "suspeito"
os.makedirs(PASTA, exist_ok=True)
os.chdir(PASTA)

sim = motores.SIM_PEQUENO
motor = motores.motor_pequeno()
t = sim.vetor_tempo()
freq_ref = Q_(motores.FREQ_REFERENCIA_HZ, "Hz")


def cron(rotulo, fn, **kw):
    print(f"Simulando: {rotulo} ...")
    t0 = time.perf_counter()
    r = fn(t, **kw)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    return r


resultados = {
    "Fonte CA (partida direta)": cron(
        "Fonte CA (partida direta)", motor.run_direct_on_line,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0),
    "Inversor V/F": cron(
        "Inversor V/F", motor.run_with_inverter_vf,
        time_step=sim.time_step, frequency_s=sim.frequencia_chaveamento,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0,
        time_ramp=sim.rampa, frequency_ref=freq_ref),
    "Inversor FOC (regra antiga)": cron(
        "Inversor FOC (regra antiga)", motor.run_with_inverter_foc,
        time_step=sim.time_step, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=sim.rampa,
        frequency_s=sim.frequencia_chaveamento, frequency_ref=freq_ref),
}

vnl = phase_to_line(motor.voltage_nom)
inversor_novo = novo.InverterFOCNovo(
    voltage_dc=line_to_dc_bus(vnl), frequency_s=sim.frequencia_chaveamento, voltage_nom=vnl,
    frequency_nom=motor.frequency_nom, n_poles=motor.n_poles, speed_nom=motor.speed_nom,
    torque_nom=motor.Tnom, stator_resistance=motor.stator_resistance,
    rotor_resistance=motor.rotor_resistance, stator_reactance=motor.stator_reactance,
    rotor_reactance=motor.rotor_reactance, mutual_reactance=motor.mutual_reactance,
    Ip_motor=motor.Ip_motor, time_ramp=sim.rampa, frequency_ref=freq_ref,
)
print("Simulando: Inversor FOC (regra nova) ...")
t0 = time.perf_counter()
resultados["Inversor FOC (regra nova)"] = motor.run(
    t, time_step=sim.time_step, load_torque_entrance_time=sim.t_carga,
    load_torque_ratio=1.0, element=inversor_novo)
print(f"  concluído em {time.perf_counter() - t0:.1f} s; proteção disparou: {inversor_novo.tripped}")

executar.gerar_saidas(resultados, motor, sim, str(PASTA), rotulo="Motor P (1,5 hp) — suspeito")
print("\nSuspeito regenerado.")
