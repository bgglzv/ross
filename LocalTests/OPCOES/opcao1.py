"""Opção 1 — Reduzir a demanda de corrente na origem (alongar a rampa de aceleração).

Motor pequeno (1,5 hp), FOC da biblioteca original, 60 Hz, sem alterar sintonia
nem limites. Só a rampa muda; o instante da carga acompanha a rampa para manter
o mesmo intervalo de acomodação em vazio (0,833 s) e de observação da carga (1,5 s).

    python opcao1.py simular <rampa_s>     # simula uma rampa e grava opcao1_dados/
    python opcao1.py montar                # figuras + documento com as rampas já simuladas
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
DADOS = PASTA / "opcao1_dados"
FIGURAS = PASTA / "opcao1_figuras"
RAMPAS = (0.6667, 1.0, 1.5, 2.0)
FOLGA_VAZIO = 1.5 - 0.6667
DURACAO_CARGA = 1.5


def parametros(rampa):
    t_carga = rampa + FOLGA_VAZIO
    return t_carga, t_carga + DURACAO_CARGA


def simular(rampa):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t_carga, tf = parametros(rampa)
    t = np.arange(0.0, tf + sim.dt, sim.dt)
    print(f"Simulando FOC com rampa de {rampa} s (carga em {t_carga:.4f} s, fim em {tf:.4f} s)...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, rampa, t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"))
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    rpm = r.speed * 60 / (2 * np.pi)
    np.savez_compressed(DADOS / f"rampa_{rampa}.npz", t=r.t, velocidade_rpm=rpm,
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, rampa, t_carga)
    est.update(rampa=rampa, t_carga=t_carga, tf=tf,
               conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"rampa_{rampa}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        from montar_opcao1 import montar

        montar()
