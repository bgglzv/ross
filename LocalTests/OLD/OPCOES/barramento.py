"""Teste do barramento CC — o limite de tensão explica a saturação do FOC a 60 Hz?

Motor pequeno (1,5 hp), FOC da biblioteca original, 60 Hz, rampa de 0,6667 s,
carga nominal em 1,5 s. Só muda o fator que converte a tensão de linha na
tensão do barramento CC (padrão da biblioteca: 1,35; o pico retificado ideal
seria 1,414). Sintonia e limite de corrente ficam como estão.

    python barramento.py simular <fator>
    python barramento.py montar
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
DADOS = PASTA / "barramento_dados"
FIGURAS = PASTA / "barramento_figuras"
FATORES = (1.35, 1.414, 1.7, 2.2)


def simular(fator):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    print(f"Simulando FOC com barramento CC = {fator} x V_linha...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"),
                                     fator_barramento=fator)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"fator_{fator}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(fator=fator, conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"fator_{fator}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        from montar_barramento import montar

        montar()
