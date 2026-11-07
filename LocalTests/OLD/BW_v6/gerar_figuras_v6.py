"""Gera as figuras do FOC com filtro síncrono de iqs/ids (InverterFOCv6,
BW_v6) a 30, 45, 55, 60 e 62 Hz, para MIT_P e MIT_G, organizadas em
subpastas por tipo (mesma estrutura do BW_v5):

    MIT_{P,G}/Velocidade/MIT_{P,G}_rpm_{freq}Hz.html
    MIT_{P,G}/Torque/MIT_{P,G}_conj_{freq}Hz.html
    MIT_{P,G}/Idq/MIT_{P,G}_idq_{freq}Hz.html
    MIT_{P,G}/Espectros/MIT_{P,G}_espectro_{rpm,conj}_{freq}Hz.html

Sem marcadores nem anotações nos pontos de máximo.

    python gerar_figuras_v6.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graficos as gr
from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS_V6 = PASTA / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"

FREQS = (60.0, 62.0, 55.0, 45.0, 30.0)

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}


def _carregar_base(motor_id, freq_hz, cenario):
    d = np.load(DADOS_BASE / f"{motor_id}_{freq_hz:g}Hz_{cenario}.npz")
    return d["t"], d["velocidade_rpm"], d["conjugado"], d["conjugado_carga"]


def _carregar_foc_v6(motor_id, freq_hz):
    d = np.load(DADOS_V6 / f"{motor_id}_{freq_hz:g}Hz_foc_v6.npz")
    return d["t"], d["velocidade_rpm"], d["conjugado"], d["conjugado_carga"]


def _carregar_foc_v6_idq(motor_id, freq_hz):
    d = np.load(DADOS_V6 / f"{motor_id}_{freq_hz:g}Hz_foc_v6.npz")
    return d["t"], d["iq"], d["id"]


def _ordem(freq_hz):
    return ["dol", "vf", "foc"] if abs(freq_hz - 60.0) < 1e-9 else ["vf", "foc"]


def gerar():
    for motor_id in ("P", "G"):
        sim, construir_motor, rotulo_motor = MOTORES[motor_id]
        motor = construir_motor()
        subpastas = {nome: (PASTA / f"MIT_{motor_id}" / nome) for nome in
                    ("Velocidade", "Torque", "Idq", "Espectros")}
        for p in subpastas.values():
            p.mkdir(parents=True, exist_ok=True)

        for freq_hz in FREQS:
            ordem = _ordem(freq_hz)
            dados = {}
            for c in ordem:
                dados[c] = _carregar_foc_v6(motor_id, freq_hz) if c == "foc" else _carregar_base(motor_id, freq_hz, c)

            fig = gr.figura_geral_unica(dados, ordem, motor, sim, freq_hz, "velocidade",
                                        f"{rotulo_motor} — {freq_hz:g} Hz — FOC filtro síncrono — Velocidade")
            caminho = subpastas["Velocidade"] / f"MIT_{motor_id}_rpm_{freq_hz:g}Hz.html"
            fig.write_html(str(caminho))
            print(f"  [OK] {caminho}")

            fig = gr.figura_geral_unica(dados, ordem, motor, sim, freq_hz, "conjugado",
                                        f"{rotulo_motor} — {freq_hz:g} Hz — FOC filtro síncrono — Conjugado")
            caminho = subpastas["Torque"] / f"MIT_{motor_id}_conj_{freq_hz:g}Hz.html"
            fig.write_html(str(caminho))
            print(f"  [OK] {caminho}")

            t, iq, id_ = _carregar_foc_v6_idq(motor_id, freq_hz)
            fig = gr.figura_idq(t, iq, id_, sim,
                                f"{rotulo_motor} — {freq_hz:g} Hz — FOC filtro síncrono — Correntes iq, id")
            caminho = subpastas["Idq"] / f"MIT_{motor_id}_idq_{freq_hz:g}Hz.html"
            fig.write_html(str(caminho))
            print(f"  [OK] {caminho}")

            t_foc, v_foc, c_foc, _ = dados["foc"]
            fig = gr.figura_espectro(t_foc, v_foc, sim,
                                     f"{rotulo_motor} — {freq_hz:g} Hz — Espectro de velocidade (regime)",
                                     "Amplitude (RPM)")
            caminho = subpastas["Espectros"] / f"MIT_{motor_id}_espectro_rpm_{freq_hz:g}Hz.html"
            fig.write_html(str(caminho))
            print(f"  [OK] {caminho}")

            fig = gr.figura_espectro(t_foc, c_foc, sim,
                                     f"{rotulo_motor} — {freq_hz:g} Hz — Espectro de conjugado (regime)",
                                     "Amplitude (N·m)")
            caminho = subpastas["Espectros"] / f"MIT_{motor_id}_espectro_conj_{freq_hz:g}Hz.html"
            fig.write_html(str(caminho))
            print(f"  [OK] {caminho}")


if __name__ == "__main__":
    gerar()
