"""Compara os resultados de BW_v5 e BW_v6 entre OLD (biblioteca antes da
atualizacao) e ATUAL (biblioteca com as modificacoes de jguarato).

Gera, em ATUAL/comparativo/: tabela CSV, figuras PNG e o relatorio .docx.

    python comparar_old_atual.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.shared import Cm, Pt

RAIZ = Path(__file__).resolve().parents[1]
OLD = RAIZ / "OLD"
ATUAL = RAIZ / "ATUAL"
SAIDA = ATUAL / "comparativo"

FREQS = (30, 45, 55, 60, 62)
MOTORES = ("P", "G")
VERSOES = ("v5", "v6")
SINAIS = (("id", "id", "Id"), ("iq", "iq", "Iq"), ("conjugado", "torque", "Torque"), ("velocidade_rpm", "velocidade", "Velocidade"))
NOME_MOTOR = {"P": "MIT_P", "G": "MIT_G"}
JANELA = 2.0


def caminho(raiz, versao, motor, freq):
    return raiz / f"BW_{versao}" / "dados" / f"{motor}_{freq:g}Hz_foc_{versao}.npz"


def ripple_pct(sinal, t, janela=JANELA):
    s = sinal[t >= t[-1] - janela]
    media = np.mean(s)
    if abs(media) < 1e-9:
        return float("nan")
    return float((s.max() - s.min()) / abs(media) * 100.0)


def carregar(raiz, versao, motor, freq):
    arq = caminho(raiz, versao, motor, freq)
    if not arq.exists():
        return None
    d = np.load(arq)
    return {k: d[k] for k in ("t", "velocidade_rpm", "conjugado", "iq", "id")}


def diferenca_relativa(a, b):
    if len(a) != len(b):
        return float("nan")
    escala = max(np.max(np.abs(a)), 1e-12)
    return float(np.max(np.abs(a - b)) / escala * 100.0)


def montar_tabela():
    linhas = []
    for versao in VERSOES:
        for motor in MOTORES:
            for freq in FREQS:
                old = carregar(OLD, versao, motor, freq)
                atual = carregar(ATUAL, versao, motor, freq)
                if old is None or atual is None:
                    continue
                linha = {"versao": versao, "motor": NOME_MOTOR[motor], "freq_hz": freq,
                         "n_amostras_old": len(old["t"]), "n_amostras_atual": len(atual["t"])}
                for chave, rotulo, _ in SINAIS:
                    r_old = ripple_pct(old[chave], old["t"])
                    r_atual = ripple_pct(atual[chave], atual["t"])
                    linha[f"ripple_{rotulo}_old"] = r_old
                    linha[f"ripple_{rotulo}_atual"] = r_atual
                    linha[f"ripple_{rotulo}_delta_pp"] = r_atual - r_old
                    linha[f"difmax_{rotulo}_pct"] = diferenca_relativa(old[chave], atual[chave])
                linhas.append(linha)
    return pd.DataFrame(linhas)


def figura_barras(tabela, versao):
    fig, eixos = plt.subplots(2, 4, figsize=(18, 7), sharex=True)
    for i, motor in enumerate(MOTORES):
        sub = tabela[(tabela.versao == versao) & (tabela.motor == NOME_MOTOR[motor])]
        for j, (_, rotulo, titulo) in enumerate(SINAIS):
            ax = eixos[i, j]
            x = np.arange(len(sub))
            ax.bar(x - 0.2, sub[f"ripple_{rotulo}_old"], 0.4, label="OLD")
            ax.bar(x + 0.2, sub[f"ripple_{rotulo}_atual"], 0.4, label="ATUAL")
            ax.set_xticks(x, [f"{f:g}" for f in sub.freq_hz])
            ax.set_title(f"{NOME_MOTOR[motor]} - ripple de {titulo} (%)")
            ax.set_xlabel("Frequencia (Hz)")
            ax.grid(alpha=0.3)
            if i == 0 and j == 0:
                ax.legend()
    fig.suptitle(f"BW_{versao}: ripple (ultimos 2 s) - OLD x ATUAL")
    fig.tight_layout()
    arq = SAIDA / f"barras_{versao}.png"
    fig.savefig(arq, dpi=110)
    plt.close(fig)
    return arq


def figura_sobreposicao(versao, motor, freq):
    old = carregar(OLD, versao, motor, freq)
    atual = carregar(ATUAL, versao, motor, freq)
    if old is None or atual is None:
        return None
    fig, eixos = plt.subplots(2, 2, figsize=(14, 7))
    for ax, (chave, titulo) in zip(eixos[0], (("velocidade_rpm", "Velocidade (rpm)"), ("conjugado", "Conjugado (N.m)"))):
        ax.plot(old["t"], old[chave], label="OLD", lw=1.2)
        ax.plot(atual["t"], atual[chave], "--", label="ATUAL", lw=1.0)
        ax.set_title(titulo)
        ax.set_xlabel("t (s)")
        ax.grid(alpha=0.3)
        ax.legend()
    zoom = 0.05
    for ax, (chave, titulo) in zip(eixos[1], (("iq", "iq (A) - ultimos 50 ms"), ("conjugado", "Conjugado - ultimos 50 ms"))):
        for dados, nome, estilo in ((old, "OLD", "-"), (atual, "ATUAL", "--")):
            m = dados["t"] >= dados["t"][-1] - zoom
            ax.plot(dados["t"][m], dados[chave][m], estilo, label=nome, lw=1.0)
        ax.set_title(titulo)
        ax.set_xlabel("t (s)")
        ax.grid(alpha=0.3)
        ax.legend()
    fig.suptitle(f"BW_{versao} - {NOME_MOTOR[motor]} a {freq:g} Hz")
    fig.tight_layout()
    arq = SAIDA / f"sobreposicao_{versao}_{motor}_{freq:g}Hz.png"
    fig.savefig(arq, dpi=100)
    plt.close(fig)
    return arq


def tabela_docx(doc, sub, rotulo):
    t = doc.add_table(rows=1, cols=5)
    t.style = "Light Grid Accent 1"
    for c, nome in zip(t.rows[0].cells, ("Motor", "Freq (Hz)", "OLD (%)", "ATUAL (%)", "Delta (p.p.)")):
        c.text = nome
    for _, r in sub.iterrows():
        cel = t.add_row().cells
        cel[0].text = r.motor
        cel[1].text = f"{r.freq_hz:g}"
        cel[2].text = f"{r[f'ripple_{rotulo}_old']:.2f}"
        cel[3].text = f"{r[f'ripple_{rotulo}_atual']:.2f}"
        cel[4].text = f"{r[f'ripple_{rotulo}_delta_pp']:+.2f}"
    for linha in t.rows:
        for c in linha.cells:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)


def montar_docx(tabela, figuras_barras, figuras_sobrep, texto_analise):
    doc = Document()
    doc.add_heading("BW_v5 e BW_v6: OLD x ATUAL", 0)
    doc.add_paragraph(
        "Comparacao dos mesmos casos (MIT_P e MIT_G, 30/45/55/60/62 Hz) simulados com a biblioteca "
        "antes da atualizacao (OLD) e com a feature-motor de jguarato incorporada (ATUAL). Ripple = "
        "(maximo - minimo) / media do sinal bruto nos ultimos 2 s de simulacao."
    )
    for paragrafo in texto_analise:
        doc.add_paragraph(paragrafo)
    for versao in VERSOES:
        doc.add_heading(f"BW_{versao}", 1)
        doc.add_picture(str(figuras_barras[versao]), width=Cm(17))
        for _, rotulo, titulo in SINAIS:
            doc.add_heading(f"Ripple de {titulo}", 2)
            tabela_docx(doc, tabela[tabela.versao == versao], rotulo)
        for arq in figuras_sobrep.get(versao, []):
            doc.add_picture(str(arq), width=Cm(17))
    doc.save(SAIDA / "Comparativo_OLD_x_ATUAL_BW_v5_v6.docx")


def main():
    SAIDA.mkdir(exist_ok=True)
    tabela = montar_tabela()
    tabela.to_csv(SAIDA / "tabela_comparativa.csv", index=False, float_format="%.6g")
    figuras_barras = {v: figura_barras(tabela, v) for v in VERSOES}
    figuras_sobrep = {v: [a for m in MOTORES for f in (30, 60) if (a := figura_sobreposicao(v, m, f))] for v in VERSOES}
    texto = (SAIDA / "analise.txt").read_text(encoding="utf-8").split("\n\n") if (SAIDA / "analise.txt").exists() else []
    montar_docx(tabela, figuras_barras, figuras_sobrep, texto)
    print(tabela.to_string(max_cols=40, float_format=lambda x: f"{x:.4g}"))


if __name__ == "__main__":
    main()
