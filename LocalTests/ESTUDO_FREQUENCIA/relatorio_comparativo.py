"""Relatório final: MIT_P e MIT_G lado a lado, evidenciando o efeito de usar o
mesmo esquema de sintonização automática (método de banda passante) em
motores de porte muito diferente, com a evolução comparada dos índices e as
conclusões do estudo.

Requer que `simular.py`, `relatorio_frequencia.py` e `relatorio_tendencia.py`
já tenham rodado para os dois motores, nas 4 frequências.

    python relatorio_comparativo.py
"""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from plotly import graph_objects as go
from plotly.subplots import make_subplots

import relatorio_tendencia as rt

PASTA = Path(__file__).resolve().parent
FIGURAS = PASTA / "figuras"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)

ESTILO_MOTOR = {"P": dict(dash="solid"), "G": dict(dash="dot")}
ROTULO_MOTOR = {"P": "MIT_P (pequeno)", "G": "MIT_G (grande)"}


def _configurar_pagina(doc):
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(10.5)
    estilo.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _titulo_secao(doc, texto):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = ACCENT
    p.paragraph_format.space_after = Pt(8)


def _par(doc, texto, tamanho=10.5, cor=None, negrito=False, italico=False):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.font.size = Pt(tamanho)
    r.font.name = "Arial"
    if cor:
        r.font.color.rgb = cor
    r.font.bold = negrito
    r.font.italic = italico
    return p


def _lado_a_lado(doc, caminho_p, caminho_g, largura=8.4):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caminho_p.exists():
        par.add_run().add_picture(str(caminho_p), width=Cm(largura))
    par.add_run("  ")
    if caminho_g.exists():
        par.add_run().add_picture(str(caminho_g), width=Cm(largura))


def _figura_comparativa(df_p, df_g, coluna, titulo_y):
    """Sobrepõe MIT_P (linha cheia) e MIT_G (linha pontilhada) por cenário,
    para o evento de entrada da carga — velocidade e conjugado lado a lado."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Velocidade — entrada da carga",
                                                         "Conjugado — entrada da carga"))
    for col, grandeza in enumerate(("velocidade", "conjugado"), start=1):
        for motor_id, df in (("P", df_p), ("G", df_g)):
            sub = df[(df.grandeza == grandeza) & (df.evento == "carga")]
            for cenario in ("vf", "foc"):
                s = sub[sub.cenario == cenario].sort_values("freq")
                if s.empty:
                    continue
                fig.add_trace(
                    go.Scatter(
                        x=s["freq"], y=s[coluna], mode="lines+markers",
                        name=f"{rt.NOMES[cenario]} — {ROTULO_MOTOR[motor_id]}",
                        line=dict(color=rt.CORES[cenario], width=2, dash=ESTILO_MOTOR[motor_id]["dash"]),
                        marker=dict(color=rt.CORES[cenario], size=7),
                        legendgroup=f"{cenario}_{motor_id}", showlegend=(col == 1),
                    ),
                    row=1, col=col,
                )
    fig.update_xaxes(title_text="Frequência de referência (Hz)", autorange="reversed")
    fig.update_yaxes(title_text=titulo_y, row=1, col=1)
    fig.update_layout(height=520, width=1150, font=dict(family="Arial"),
                      legend=dict(orientation="h", y=-0.25, font=dict(size=10)),
                      margin=dict(t=50, b=110, l=70, r=25))
    return fig


def montar():
    df_p = rt.coletar("P")
    df_g = rt.coletar("G")
    FIGURAS.mkdir(exist_ok=True)

    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("MIT_P x MIT_G — Efeito da Sintonização Automática em Motores de Porte Distinto")
    r.font.size = Pt(19)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "Os dois motores testados neste estudo — MIT_P, de pequeno porte (1,5 hp), e MIT_G, um motor "
        "industrial de grande porte — foram acionados com V/F e FOC usando exatamente o mesmo método de "
        "cálculo de ganhos: a sintonia automática por banda passante, sem qualquer ajuste manual específico "
        "para cada máquina. Este relatório reúne os dois lado a lado para mostrar até que ponto essa mesma "
        "regra de sintonia se comporta de forma equivalente em motores de porte, inércia e constante de tempo "
        "elétrica muito diferentes."
    )

    doc.add_page_break()
    _titulo_secao(doc, "Visão geral à velocidade nominal (60 Hz)")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / "P_60Hz_geral.png", FIGURAS / "G_60Hz_geral.png")

    doc.add_page_break()
    _titulo_secao(doc, "Detalhe na entrada da carga — V/F x FOC anotado (60 Hz)")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / "P_60Hz_carga_foc.png", FIGURAS / "G_60Hz_carga_foc.png")
    _par(doc,
        "No motor pequeno, o FOC oscila em torno da referência sem amortecer completamente, mas dentro de uma "
        "faixa relativamente estreita. No motor grande, a mesma sintonia produz uma oscilação de amplitude "
        "muito maior nos primeiros ciclos após a carga e, mais adiante, um mergulho de velocidade que chega a "
        "perder mais de 65% da velocidade nominal antes de recuperar — um comportamento de malha "
        "subamortecida que não aparece no motor pequeno.",
        tamanho=9.5,
    )

    doc.add_page_break()
    _titulo_secao(doc, "Evolução comparada dos índices — sobressinal (entrada da carga)")
    fig = _figura_comparativa(df_p, df_g, "sobressinal_pct", "Sobressinal (%)")
    c1 = FIGURAS / "comparativo_sobressinal_carga.png"
    fig.write_image(str(c1), scale=2)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(c1), width=Cm(17))
    _par(doc, "Linha cheia: MIT_P. Linha pontilhada: MIT_G.", tamanho=9, cor=MUTED, italico=True)

    doc.add_page_break()
    _titulo_secao(doc, "Evolução comparada dos índices — tempo de subida (entrada da carga)")
    fig = _figura_comparativa(df_p, df_g, "tempo_subida", "Tempo de subida (s)")
    c2 = FIGURAS / "comparativo_subida_carga.png"
    fig.write_image(str(c2), scale=2)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(c2), width=Cm(17))
    _par(doc, "Linha cheia: MIT_P. Linha pontilhada: MIT_G.", tamanho=9, cor=MUTED, italico=True)

    doc.add_page_break()
    _titulo_secao(doc, "Conclusões")
    conclusoes = [
        "A causa raiz identificada — a banda dos PIs do FOC calculada a partir de frequency_s sem converter "
        "de rad/s para Hz antes de dividir por 8 — inflava todos os ganhos em cerca de 2π (~6,28×). A correção "
        "foi aplicada uma única vez, na biblioteca (InverterFOC.__init__), e vale para os dois motores e todas "
        "as frequências deste estudo.",
        "Com os ganhos corrigidos, o barramento ajustado para 1,414 × V_linha e o passo interno de simulação "
        "em 1 × 10⁻⁶ s (200 amostras por período de chaveamento), os oito ensaios (dois motores × quatro "
        "frequências) foram reproduzidos de forma consistente, sempre sobre o sinal bruto medido.",
        "No motor pequeno, o mesmo método de sintonia automática produz um FOC com sobressinal e tempo de "
        "subida comparáveis aos do V/F, e a diferença entre os dois acionamentos se mantém razoavelmente "
        "estável nas quatro frequências testadas.",
        "No motor grande, a mesma regra de sintonia é bem menos robusta: o sobressinal do FOC na entrada da "
        "carga é acentuadamente maior que o do motor pequeno, sobretudo na frequência nominal, e a resposta "
        "inclui um mergulho de velocidade que não tem equivalente no motor pequeno.",
        "Isso indica que a sintonia por banda passante, calculada só a partir da frequência de chaveamento e "
        "dos parâmetros elétricos e mecânicos de cada motor, não garante desempenho dinâmico equivalente "
        "entre máquinas de porte muito diferente — a inércia e a constante de tempo elétrica do motor grande "
        "parecem exigir uma revisão manual dos ganhos que o motor pequeno dispensa.",
        "Como próximo passo, sugere-se revisar manualmente a sintonia do FOC para o motor de grande porte "
        "(em particular a malha de velocidade) e, com um critério de acomodação mais robusto que a simples "
        "permanência da última amostra dentro de uma faixa, reavaliar o tempo de acomodação para os dois "
        "motores.",
    ]
    for c in conclusoes:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(c)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Comparativo_MIT_P_x_MIT_G.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
