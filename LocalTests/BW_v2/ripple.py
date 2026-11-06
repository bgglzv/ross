"""Ripple % do conjugado no último segundo de simulação: (max-min)/Tnom*100,
sobre o sinal bruto (sem filtragem), comparando o FOC original (biblioteca,
sem `ki_iqs`) com o FOC desta pasta (`InverterFOCv2`, com `ki_iqs`).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS_V2 = PASTA / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"

FREQS = (60.0, 55.0, 45.0, 30.0)
MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno), "G": (motores.SIM_GRANDE, motores.motor_grande)}


def _ripple_pct(t, conjugado, tnom, janela=1.0):
    tf = t[-1]
    m = t >= tf - janela
    return float((conjugado[m].max() - conjugado[m].min()) / tnom * 100.0)


def coletar():
    linhas = []
    for motor_id in ("P", "G"):
        sim, construir_motor = MOTORES[motor_id]
        motor = construir_motor()
        tnom = float(motor.Tnom)
        for freq_hz in FREQS:
            d_base = np.load(DADOS_BASE / f"{motor_id}_{freq_hz:g}Hz_foc.npz")
            d_v2 = np.load(DADOS_V2 / f"{motor_id}_{freq_hz:g}Hz_foc_v2.npz")
            rip_base = _ripple_pct(d_base["t"], d_base["conjugado"], tnom)
            rip_v2 = _ripple_pct(d_v2["t"], d_v2["conjugado"], tnom)
            linhas.append(dict(
                motor_id=motor_id, freq_hz=freq_hz, tnom=tnom,
                ripple_base_pct=rip_base, ripple_v2_pct=rip_v2,
                reducao_pct=(rip_base - rip_v2) / rip_base * 100.0 if rip_base else float("nan"),
            ))
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    df = coletar()
    with pd.option_context("display.width", 120):
        print(df.to_string(index=False))
