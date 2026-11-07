"""Teste a 60 Hz — motor de pequeno porte (1,5 hp), biblioteca ROSS original.

Simula, com a biblioteca exatamente como está na branch feature-motor, os três
acionamentos à frequência nominal de 60 Hz, com degrau de carga nominal:

    1. Fonte CA (partida direta)   run_direct_on_line
    2. Inversor V/F                run_with_inverter_vf
    3. Inversor FOC                run_with_inverter_foc  (sintonia padrão da biblioteca)

Saídas (nesta pasta): figuras/, anotadas/, metricas/, o relatório .docx e a
apresentação .pptx.

Uso:  python teste_60Hz.py
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ross.units import Q_

from comum import executar, motores
from comum import relatorios

PASTA = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA)

sim = motores.SIM_PEQUENO
motor = motores.motor_pequeno()
t = sim.vetor_tempo()
freq_ref = Q_(motores.FREQ_REFERENCIA_HZ, "Hz")


def _cronometrar(rotulo, fn, **kw):
    print(f"Simulando: {rotulo} ...")
    t0 = time.perf_counter()
    r = fn(t, **kw)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    return r


resultados = {
    "Fonte CA (partida direta)": _cronometrar(
        "Fonte CA (partida direta)", motor.run_direct_on_line,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0),
    "Inversor V/F": _cronometrar(
        "Inversor V/F", motor.run_with_inverter_vf,
        time_step=sim.time_step, frequency_s=sim.frequencia_chaveamento,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0,
        time_ramp=sim.rampa, frequency_ref=freq_ref),
    "Inversor FOC": _cronometrar(
        "Inversor FOC", motor.run_with_inverter_foc,
        time_step=sim.time_step, load_torque_entrance_time=sim.t_carga,
        load_torque_ratio=1.0, time_ramp=sim.rampa,
        frequency_s=sim.frequencia_chaveamento, frequency_ref=freq_ref),
}

metricas, resumo = executar.gerar_saidas(
    resultados, motor, sim, PASTA, rotulo="Motor P (1,5 hp)")

relatorios.gerar_relatorio_docx(PASTA, "Motor de pequeno porte (1,5 hp)", motor, sim, metricas, resumo,
                                "Relatorio_MIT_P_60Hz.docx")
relatorios.gerar_apresentacao_pptx(PASTA, "Motor de pequeno porte (1,5 hp)", motor, sim, metricas,
                                   "Apresentacao_MIT_P_60Hz.pptx")
print("\nTeste concluído.")
