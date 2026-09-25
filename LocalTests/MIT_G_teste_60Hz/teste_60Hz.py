"""Teste a 60 Hz — motor de grande porte (MIT M-C-5283001, REPLAN).

Mesma estrutura do teste do motor pequeno (pasta MIT_P_teste_60Hz), aplicada ao
motor de 2474 kW. ESTE TESTE AINDA NÃO FOI EXECUTADO: com 24 s simulados e o
passo interno Ts/200 (frequência de chaveamento de 5 kHz), o cenário FOC roda em
Python puro e leva bastante tempo — rode-o na máquina mais rápida.

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

sim = motores.SIM_GRANDE
motor = motores.motor_grande()
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
        time_step=sim.time_step_dol,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0),
    "Inversor V/F": _cronometrar(
        "Inversor V/F", motor.run_with_inverter_vf,
        frequency_s=sim.frequencia_chaveamento,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0,
        time_ramp=sim.rampa, frequency_ref=freq_ref),
    "Inversor FOC": _cronometrar(
        "Inversor FOC", motor.run_with_inverter_foc,
        load_torque_entrance_time=sim.t_carga, load_torque_ratio=1.0,
        time_ramp=sim.rampa, frequency_s=sim.frequencia_chaveamento,
        frequency_ref=freq_ref),
}

metricas, resumo = executar.gerar_saidas(
    resultados, motor, sim, PASTA, rotulo="Motor G (2474 kW)")

relatorios.gerar_relatorio_docx(PASTA, "Motor de grande porte (M-C-5283001)", motor, sim, metricas, resumo,
                                "Relatorio_MIT_G_60Hz.docx")
relatorios.gerar_apresentacao_pptx(PASTA, "Motor de grande porte (M-C-5283001)", motor, sim, metricas,
                                   "Apresentacao_MIT_G_60Hz.pptx")
print("\nTeste concluído.")
