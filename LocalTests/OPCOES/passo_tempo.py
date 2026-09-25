"""Sensibilidade do FOC original (barramento padrão, 60 Hz) ao passo interno de simulação.

O passo interno define quantas amostras cabem em um período de chaveamento
(Ts / passo). O padrão da biblioteca é Ts/200; os testes usam 1e-5 (20 amostras
por período a 5 kHz).

    python passo_tempo.py <passo_s>
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comum_opcoes as co
from comum import motores
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "passo_dados"

passo = float(sys.argv[1])
sim = motores.SIM_PEQUENO
motor = motores.motor_pequeno()
t = sim.vetor_tempo()
print(f"Simulando FOC original com passo interno {passo:g} s ({2e-4 / passo:.0f} amostras por período)...")
t0 = time.perf_counter()
r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento, passo,
                                 Q_(motores.FREQ_REFERENCIA_HZ, "Hz"))
print(f"  concluído em {time.perf_counter() - t0:.1f} s")
os.makedirs(DADOS, exist_ok=True)
np.savez_compressed(DADOS / f"passo_{passo:g}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                    conjugado=r.electric_torque, corrente_a=r.currents["a"])
est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
est.update(passo=passo, conjugado_minimo=float(np.min(r.electric_torque)),
           conjugado_maximo=float(np.max(r.electric_torque)),
           corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
(DADOS / f"passo_{passo:g}.json").write_text(json.dumps(est, indent=2))
print(json.dumps(est, indent=2))
