"""Geração das saídas de um teste de 60 Hz a partir de resultados já simulados.

Recebe {nome_do_cenário: MotorResponseResults} e produz, na pasta de saída:

    figuras/    figuras comparativas (HTML + PNG): conjugado, velocidade e corrente
                no tempo (completas e com zoom na entrada da carga) e FFT
    anotadas/   uma figura por cenário, grandeza e evento, com sobressinal,
                tubo de acomodação, acomodação, regime e tempo de subida
    metricas/   metricas_eventos.csv e resumo_sinais.csv

É usada tanto pelo teste "original" quanto pelo regenerador das figuras do
"suspeito" (mesma análise, mesmas marcações, para a comparação ser justa).
"""

import os
import re
import unicodedata

import numpy as np
import pandas as pd

from comum import anotacoes as an
from comum import graficos as gr


def slug(texto):
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()


CORES = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def _rpm(results):
    return results.speed * 60.0 / (2.0 * np.pi)


def gerar_saidas(resultados, motor, sim, pasta, rotulo, freq_ref_hz=60.0):
    fig_dir = os.path.join(pasta, "figuras")
    ano_dir = os.path.join(pasta, "anotadas")
    met_dir = os.path.join(pasta, "metricas")
    for d in (fig_dir, ano_dir, met_dir):
        gr.reset_output_dir(d)

    zoom = (sim.t_carga - sim.zoom_antes, sim.t_carga + sim.zoom_depois)

    print(f"\nFiguras comparativas em '{fig_dir}'...")
    ref = dict(reference_signal=gr.get_load_torque, reference_name="Torque de carga (referência)")
    f = gr.compare_time(resultados, gr.get_electric_torque, f"{rotulo} — Conjugados (velocidade nominal)",
                        "Torque (N·m)", **ref)
    gr.save_figure(f, fig_dir, "01_conjugados_tempo")
    f = gr.compare_time(resultados, gr.get_electric_torque,
                        f"{rotulo} — Conjugados (zoom na entrada da carga)", "Torque (N·m)", xlim=zoom, **ref)
    gr.save_figure(f, fig_dir, "01_conjugados_tempo_zoom")
    f = gr.compare_time(resultados, gr.get_speed_rpm, f"{rotulo} — Velocidade (velocidade nominal)",
                        "Velocidade (RPM)")
    gr.save_figure(f, fig_dir, "02_velocidade_tempo")
    f = gr.compare_time(resultados, gr.get_speed_rpm, f"{rotulo} — Velocidade (zoom na entrada da carga)",
                        "Velocidade (RPM)", xlim=zoom)
    gr.save_figure(f, fig_dir, "02_velocidade_tempo_zoom")
    f = gr.compare_time(resultados, gr.get_current_a, f"{rotulo} — Corrente de Fase A (velocidade nominal)",
                        "Corrente (A)")
    gr.save_figure(f, fig_dir, "03_corrente_fase_a_tempo")
    f = gr.compare_time(resultados, gr.get_current_a,
                        f"{rotulo} — Corrente de Fase A (zoom na entrada da carga)", "Corrente (A)", xlim=zoom)
    gr.save_figure(f, fig_dir, "03_corrente_fase_a_tempo_zoom")
    f = gr.compare_frequency(resultados, gr.get_electric_torque,
                             f"{rotulo} — Conjugados (FFT, velocidade nominal)", "Magnitude do torque (N·m)")
    gr.save_figure(f, fig_dir, "04_conjugados_freq")

    torque_nom = float(motor.Tnom)
    vel_nom_rpm = float(motor.speed_nom) * 60.0 / (2.0 * np.pi)
    eventos = an.eventos_do_teste(sim.t_carga, sim.tf, torque_nom, vel_nom_rpm, torque_nom)

    linhas, resumo = [], []
    print(f"\nFiguras anotadas em '{ano_dir}'...")
    for i, (cenario, r) in enumerate(resultados.items()):
        cor = CORES[i % len(CORES)]
        sinais = {"conjugado": r.electric_torque, "velocidade": _rpm(r)}
        for grandeza, bruto in sinais.items():
            ys = an.media_movel(r.t, bruto)
            for k, ev in enumerate(eventos[grandeza]):
                y_ini = 0.0 if k == 0 else an.valor_pre_evento(r.t, ys, ev.t_ini)
                res = an.analisar(r.t, ys, ev, y_ini)
                linhas.append({"cenario": cenario, "grandeza": grandeza, **res})
                tag = "partida" if k == 0 else "carga"
                titulo = f"{rotulo} — {cenario} — {grandeza.capitalize()} — {ev.nome}"
                base = f"{slug(cenario)}_{grandeza}_{tag}"
                fig = an.figura_anotada(r.t, bruto, ys, res, ev, grandeza, cenario, cor, titulo)
                gr.save_figure(fig, ano_dir, base)
                if k == 1:
                    fig = an.figura_anotada(r.t, bruto, ys, res, ev, grandeza, cenario, cor,
                                            titulo + " (zoom)", janela_plot=zoom)
                    gr.save_figure(fig, ano_dir, base + "_zoom")

        for nome_sinal, y in (("conjugado", r.electric_torque), ("velocidade_rpm", _rpm(r)),
                              ("corrente_a", r.currents["a"])):
            for jan, (a, b) in (("pre_carga", (sim.t_carga - 0.3, sim.t_carga)),
                                ("pos_carga", (sim.tf - 0.5, sim.tf))):
                m = (r.t >= a) & (r.t < b if jan == "pre_carga" else r.t <= b)
                resumo.append({"cenario": cenario, "sinal": nome_sinal, "janela": jan,
                               "media": float(np.mean(y[m])), "desvio": float(np.std(y[m])),
                               "minimo": float(np.min(y[m])), "maximo": float(np.max(y[m]))})
        m_par = r.t < sim.t_carga
        for nome_sinal, y in (("conjugado", r.electric_torque), ("velocidade_rpm", _rpm(r)),
                              ("corrente_a", r.currents["a"])):
            resumo.append({"cenario": cenario, "sinal": nome_sinal, "janela": "partida_completa",
                           "media": float(np.mean(y[m_par])), "desvio": float(np.std(y[m_par])),
                           "minimo": float(np.min(y[m_par])), "maximo": float(np.max(y[m_par]))})
        m_pos = r.t >= sim.t_carga
        resumo.append({"cenario": cenario, "sinal": "conjugado", "janela": "apos_degrau_completa",
                       "media": float(np.mean(r.electric_torque[m_pos])),
                       "desvio": float(np.std(r.electric_torque[m_pos])),
                       "minimo": float(np.min(r.electric_torque[m_pos])),
                       "maximo": float(np.max(r.electric_torque[m_pos]))})

    dados_dir = os.path.join(pasta, "dados")
    os.makedirs(dados_dir, exist_ok=True)
    for cenario, r in resultados.items():
        np.savez_compressed(os.path.join(dados_dir, slug(cenario) + ".npz"), t=r.t,
                            conjugado=r.electric_torque, velocidade_rpm=_rpm(r),
                            corrente_a=r.currents["a"], carga=r.load_torque)

    df = pd.DataFrame(linhas)
    df.to_csv(os.path.join(met_dir, "metricas_eventos.csv"), index=False)
    pd.DataFrame(resumo).to_csv(os.path.join(met_dir, "resumo_sinais.csv"), index=False)
    print(f"[OK] metricas gravadas em '{met_dir}'")
    return df, pd.DataFrame(resumo)
