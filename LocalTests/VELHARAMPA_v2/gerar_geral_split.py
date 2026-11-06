"""Gera as figuras gerais (visão completa) de MIT_P e MIT_G, a 60, 55, 45 e
30 Hz, com velocidade e conjugado em arquivos .HTML separados — sem os zooms.

    python gerar_geral_split.py
"""

from pathlib import Path

import graficos as gr
from relatorio_frequencia import MOTORES, _carregar, _ordem

PASTA = Path(__file__).resolve().parent
FREQS = (60.0, 55.0, 45.0, 30.0)
GRANDEZAS = (("velocidade", "rpm"), ("conjugado", "conj"))


def gerar():
    for motor_id in ("P", "G"):
        sim, construir_motor, rotulo_motor = MOTORES[motor_id]
        motor = construir_motor()
        subpasta = PASTA / f"MIT_{motor_id}"
        subpasta.mkdir(exist_ok=True)
        for freq_hz in FREQS:
            ordem = _ordem(freq_hz)
            dados = {c: _carregar(motor_id, freq_hz, c) for c in ordem}
            for grandeza, sigla in GRANDEZAS:
                nome_grandeza = "Velocidade" if grandeza == "velocidade" else "Conjugado"
                titulo = f"{rotulo_motor} — {freq_hz:g} Hz — visão completa — {nome_grandeza}"
                fig = gr.figura_geral_unica(dados, ordem, motor, sim, freq_hz, grandeza, titulo)
                caminho = subpasta / f"MIT_{motor_id}_{sigla}_{freq_hz:g}Hz.html"
                fig.write_html(str(caminho))
                print(f"  [OK] {caminho}")


if __name__ == "__main__":
    gerar()
