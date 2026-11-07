"""Ripple % do conjugado no último segundo de simulação: (max-min)/Tnom*100,
sobre o sinal bruto, comparando três versões do FOC:

    base — biblioteca original (sem ki_iqs)
    v2   — ki_iqs fixo (BWi_iqs = BWp_iqs/8) + anti-windup (../BW_v2)
    v3   — ki_iqs desacoplado de kp_iqs e escalado pela frequência de
           acionamento (BWi_iqs cresce de 1,5x a 2,0x o valor do v2,
           conforme a razão frequency_ref/frequency_nom) + anti-windup
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS_V3 = PASTA / "dados"
DADOS_V2 = PASTA.parent / "BW_v2" / "dados"
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
            d_v3 = np.load(DADOS_V3 / f"{motor_id}_{freq_hz:g}Hz_foc_v3.npz")
            rip_base = _ripple_pct(d_base["t"], d_base["conjugado"], tnom)
            rip_v2 = _ripple_pct(d_v2["t"], d_v2["conjugado"], tnom)
            rip_v3 = _ripple_pct(d_v3["t"], d_v3["conjugado"], tnom)
            linhas.append(dict(
                motor_id=motor_id, freq_hz=freq_hz, tnom=tnom,
                ripple_base_pct=rip_base, ripple_v2_pct=rip_v2, ripple_v3_pct=rip_v3,
                reducao_v2_pct=(rip_base - rip_v2) / rip_base * 100.0 if rip_base else float("nan"),
                reducao_v3_pct=(rip_base - rip_v3) / rip_base * 100.0 if rip_base else float("nan"),
                reducao_v3_vs_v2_pct=(rip_v2 - rip_v3) / rip_v2 * 100.0 if rip_v2 else float("nan"),
            ))
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    df = coletar()
    with pd.option_context("display.width", 160):
        print(df.to_string(index=False))
