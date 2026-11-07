"""Gera as figuras gerais (velocidade e conjugado, arquivos .HTML
separados) de MIT_P e MIT_G a 60, 55, 45 e 30 Hz, usando o FOC com a
constante universal C=4,0 (InverterFOCv4, ver `simular_v4.py`). DOL e V/F
não mudam com essa variante — as curvas vêm do dado já simulado em
`../VELHARAMPA/dados`.

    python gerar_figuras_v4.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graficos as gr
from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS_V4 = PASTA / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"

FREQS = (60.0, 55.0, 45.0, 30.0)
GRANDEZAS = (("velocidade", "rpm"), ("conjugado", "conj"))
C_FINAL = 4.0

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}


def _carregar_base(motor_id, freq_hz, cenario):
    d = np.load(DADOS_BASE / f"{motor_id}_{freq_hz:g}Hz_{cenario}.npz")
    return d["t"], d["velocidade_rpm"], d["conjugado"], d["conjugado_carga"]


def _carregar_foc_v4(motor_id, freq_hz):
    d = np.load(DADOS_V4 / f"{motor_id}_{freq_hz:g}Hz_foc_v4_C{C_FINAL:g}.npz")
    return d["t"], d["velocidade_rpm"], d["conjugado"], d["conjugado_carga"]


def _ordem(freq_hz):
    return ["dol", "vf", "foc"] if abs(freq_hz - 60.0) < 1e-9 else ["vf", "foc"]


def gerar():
    for motor_id in ("P", "G"):
        sim, construir_motor, rotulo_motor = MOTORES[motor_id]
        motor = construir_motor()
        subpasta = PASTA / f"MIT_{motor_id}"
        subpasta.mkdir(exist_ok=True)
        for freq_hz in FREQS:
            ordem = _ordem(freq_hz)
            dados = {}
            for c in ordem:
                dados[c] = _carregar_foc_v4(motor_id, freq_hz) if c == "foc" else _carregar_base(motor_id, freq_hz, c)
            for grandeza, sigla in GRANDEZAS:
                nome_grandeza = "Velocidade" if grandeza == "velocidade" else "Conjugado"
                titulo = f"{rotulo_motor} — {freq_hz:g} Hz — FOC com C={C_FINAL:g} — {nome_grandeza}"
                fig = gr.figura_geral_unica(dados, ordem, motor, sim, freq_hz, grandeza, titulo)
                caminho = subpasta / f"MIT_{motor_id}_{sigla}_{freq_hz:g}Hz.html"
                fig.write_html(str(caminho))
                print(f"  [OK] {caminho}")


if __name__ == "__main__":
    gerar()
