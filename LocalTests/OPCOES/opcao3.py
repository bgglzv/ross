"""Opção 3 — Usar um limite de corrente compatível com o inversor (1,5× e 2,0× a nominal).

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s,
barramento CC padrão da biblioteca (1,35 × V_linha). Só o limite do eixo q muda:
`iqs_max = múltiplo × Is_nom` (a biblioteca usa 3,0). Sintonia, anti-windup e
SVPWM ficam idênticos; a biblioteca não é alterada.

    python opcao3.py simular <multiplo>
    python opcao3.py montar
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
from opcao2 import FOCModuloVetor
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "opcao3_dados"
FIGURAS = PASTA / "opcao3_figuras"
MULTIPLOS = (1.5, 2.0)


def foc_com_limite(multiplo):
    class FOCLimiteInversor(FOCModuloVetor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.iqs_max = float(multiplo * self.Is_nom)

    return FOCLimiteInversor


def simular(multiplo):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    classe = foc_com_limite(multiplo)
    print(f"Simulando FOC com limite de corrente de {multiplo} x Is_nom...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"),
                                     inversor_classe=classe)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"multiplo_{multiplo}.npz", t=r.t,
                        velocidade_rpm=r.speed * 60 / (2 * np.pi), conjugado=r.electric_torque,
                        corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(fator=1.35, multiplo=multiplo, iqs_max=classe.instancias[-1].iqs_max,
               conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"multiplo_{multiplo}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        from montar_opcao3 import montar

        montar()
