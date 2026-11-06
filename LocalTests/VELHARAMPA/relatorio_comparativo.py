"""Relatório final: MIT_P e MIT_G lado a lado, evidenciando o efeito de usar o
mesmo esquema de sintonização automática (método de banda passante) em
motores de porte muito diferente, com um quadro comparativo dos índices e as
conclusões do estudo. Um relatório por frequência (60 e 30 Hz), mais uma
apresentação consolidando os dois.

Requer que `simular.py` e `relatorio_frequencia.py` já tenham rodado para os
dois motores, em 60 e 30 Hz.

    python relatorio_comparativo.py
"""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from pptx import Presentation
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Cm as PptxCm, Pt as PptxPt

import graficos as gr
import relatorio_tendencia as rt

PASTA = Path(__file__).resolve().parent
FIGURAS = PASTA / "figuras"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
ACCENT_PPTX = PptxRGBColor(0x0E, 0x5C, 0x68)
MUTED_PPTX = PptxRGBColor(0x5B, 0x66, 0x72)
TEXT_PPTX = PptxRGBColor(0x1A, 0x20, 0x27)

FREQS = (60.0, 30.0)
ESTILO_MOTOR = {"P": dict(dash="solid"), "G": dict(dash="dot")}
ROTULO_MOTOR = {"P": "MIT_P (pequeno)", "G": "MIT_G (grande)"}
EVENTO_NOME = {"partida": "Chegada na referência", "carga": "Entrada da carga"}


def _configurar_pagina(doc):
    """Comparativo em paisagem (item 4): a folha mais larga é o que permite
    colocar MIT_P e MIT_G lado a lado em dimensões maiores do que caberia em
    retrato — diferente de `relatorio_frequencia.py`, que fica em retrato."""
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(1.5)
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


def _lado_a_lado(doc, caminho_p, caminho_g, largura=13.0):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caminho_p.exists():
        par.add_run().add_picture(str(caminho_p), width=Cm(largura))
    par.add_run("  ")
    if caminho_g.exists():
        par.add_run().add_picture(str(caminho_g), width=Cm(largura))


def _tabela_indices(doc, df_p, df_g):
    """Quadro comparativo dos índices (item 10): uma tabela pequena por
    combinação de acionamento x evento x grandeza (item 5), sempre com MIT_P
    na primeira linha e MIT_G na segunda — mais fácil de comparar par a par
    do que uma única tabela grande misturando tudo."""
    combinacoes = [
        (cenario, evento, grandeza)
        for cenario in ("vf", "foc")
        for evento in ("partida", "carga")
        for grandeza in ("velocidade", "conjugado")
    ]
    for cenario, evento, grandeza in combinacoes:
        sub_p = df_p[(df_p.cenario == cenario) & (df_p.evento == evento) & (df_p.grandeza == grandeza)]
        sub_g = df_g[(df_g.cenario == cenario) & (df_g.evento == evento) & (df_g.grandeza == grandeza)]
        if sub_p.empty and sub_g.empty:
            continue

        legenda = doc.add_paragraph()
        r = legenda.add_run(f"{rt.NOMES[cenario]} — {EVENTO_NOME[evento]} — {grandeza.capitalize()}")
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.name = "Arial"
        r.font.color.rgb = ACCENT
        legenda.paragraph_format.space_before = Pt(8)
        legenda.paragraph_format.space_after = Pt(2)

        tabela = doc.add_table(rows=1, cols=3)
        tabela.style = "Light Grid Accent 1"
        for c, nome in zip(tabela.rows[0].cells, ("Motor", "Sobressinal (%)", "Subida (s)")):
            c.text = nome
            c.paragraphs[0].runs[0].font.bold = True
        for motor_id, sub in (("MIT_P", sub_p), ("MIT_G", sub_g)):
            cels = tabela.add_row().cells
            cels[0].text = motor_id
            if sub.empty:
                cels[1].text = cels[2].text = "—"
            else:
                row = sub.iloc[0]
                cels[1].text = f"{row.sobressinal_pct:+.1f}"
                cels[2].text = f"{row.tempo_subida:.3f}" if row.tempo_subida == row.tempo_subida else "—"
        for row in tabela.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)
                        r.font.name = "Arial"


def montar(freq_hz):
    prefixo_freq = f"{freq_hz:g}Hz"
    df_p = rt.coletar("P", freqs=(freq_hz,))
    df_g = rt.coletar("G", freqs=(freq_hz,))
    FIGURAS.mkdir(exist_ok=True)

    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run(f"MIT_P x MIT_G a {freq_hz:g} Hz — Efeito da Sintonização Automática")
    r.font.size = Pt(19)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        f"Os dois motores testados neste estudo — MIT_P, de pequeno porte (1,5 hp), e MIT_G, um motor "
        f"industrial de grande porte — foram levados à referência de {freq_hz:g} Hz e acionados com V/F e FOC "
        f"usando exatamente o mesmo método de cálculo de ganhos: a sintonia automática por banda passante, sem "
        f"qualquer ajuste manual específico para cada máquina. Este relatório reúne os dois lado a lado para "
        f"mostrar até que ponto essa mesma regra de sintonia se comporta de forma equivalente em motores de "
        f"porte, inércia e constante de tempo elétrica muito diferentes."
    )

    doc.add_page_break()
    _titulo_secao(doc, f"Visão geral a {freq_hz:g} Hz")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / f"P_{prefixo_freq}_geral.png", FIGURAS / f"G_{prefixo_freq}_geral.png")

    doc.add_page_break()
    _titulo_secao(doc, f"Entrada da carga — V/F x FOC anotado ({freq_hz:g} Hz)")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / f"P_{prefixo_freq}_carga.png", FIGURAS / f"G_{prefixo_freq}_carga.png")

    doc.add_page_break()
    _titulo_secao(doc, f"Entrada da carga: detalhe ({freq_hz:g} Hz)")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / f"P_{prefixo_freq}_carga_detalhe.png", FIGURAS / f"G_{prefixo_freq}_carga_detalhe.png")

    doc.add_page_break()
    _titulo_secao(doc, f"Chegada na referência de velocidade ({freq_hz:g} Hz)")
    _par(doc, "MIT_P à esquerda, MIT_G à direita:", tamanho=9, cor=MUTED, italico=True)
    _lado_a_lado(doc, FIGURAS / f"P_{prefixo_freq}_chegada.png", FIGURAS / f"G_{prefixo_freq}_chegada.png")

    doc.add_page_break()
    _titulo_secao(doc, "Quadro comparativo dos índices")
    _tabela_indices(doc, df_p, df_g)

    doc.add_page_break()
    _titulo_secao(doc, "Conclusões")
    conclusoes = [
        "A causa raiz identificada — a banda dos PIs do FOC calculada a partir de frequency_s sem converter "
        "de rad/s para Hz antes de dividir por 8 — inflava todos os ganhos em cerca de 2π (~6,28×). A correção "
        "foi aplicada uma única vez, na biblioteca (InverterFOC.__init__), e vale para os dois motores em "
        "qualquer frequência de referência.",
        f"Com os ganhos corrigidos, o barramento ajustado para 1,414 × V_linha e o passo interno de simulação "
        f"em 1 × 10⁻⁶ s (200 amostras por período de chaveamento), os ensaios a {freq_hz:g} Hz foram "
        f"reproduzidos de forma consistente para os dois motores, sempre sobre o sinal bruto medido.",
        "V/F e FOC usam a mesma rampa de referência em cada motor (o experimento de encurtar a rampa do FOC "
        "para acelerar no limite de corrente, como a partida direta, foi desfeito nesta rodada).",
    ]
    for c in conclusoes:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(c)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / f"Comparativo_MIT_P_x_MIT_G_{prefixo_freq}.docx"
    doc.save(destino)
    print(f"[OK] {destino}")
    return df_p, df_g


# =============================================================================
# Apresentação consolidada (item 11)
# =============================================================================


def _figura_comparativa_freq(dados_por_freq, coluna, titulo_y):
    """Sobrepõe MIT_P (linha cheia) e MIT_G (linha pontilhada) por cenário,
    através das frequências testadas — velocidade e conjugado lado a lado,
    evento de entrada da carga."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Velocidade — entrada da carga",
                                                         "Conjugado — entrada da carga"))
    for col, grandeza in enumerate(("velocidade", "conjugado"), start=1):
        for motor_id in ("P", "G"):
            linhas = []
            for freq in FREQS:
                df_p, df_g = dados_por_freq[freq]
                df = df_p if motor_id == "P" else df_g
                linhas.append(df[(df.grandeza == grandeza) & (df.evento == "carga")].assign(freq=freq))
            import pandas as pd
            sub = pd.concat(linhas)
            for cenario in ("vf", "foc"):
                s = sub[sub.cenario == cenario].sort_values("freq")
                if s.empty:
                    continue
                fig.add_trace(
                    go.Scatter(
                        x=s["freq"], y=s[coluna], mode="lines+markers",
                        name=f"{rt.NOMES[cenario]} — {ROTULO_MOTOR[motor_id]}",
                        line=dict(color=rt.CORES[cenario], width=2, dash=ESTILO_MOTOR[motor_id]["dash"]),
                        marker=dict(color=rt.CORES[cenario], size=9),
                        legendgroup=f"{cenario}_{motor_id}", showlegend=(col == 1),
                    ),
                    row=1, col=col,
                )
    fig.update_xaxes(title_text="Frequência de referência (Hz)", autorange="reversed",
                     tickvals=list(FREQS))
    fig.update_yaxes(title_text=titulo_y, row=1, col=1)
    fig.update_layout(height=520, width=1150, font=dict(family="Arial"),
                      legend=dict(orientation="h", y=-0.25, font=dict(size=11)),
                      margin=dict(t=50, b=110, l=70, r=25))
    return fig


def montar_pptx_consolidado(dados_por_freq):
    prs = Presentation()
    prs.slide_width = PptxCm(28.0)
    prs.slide_height = PptxCm(15.75)

    def slide_branco():
        s = prs.slides.add_slide(prs.slide_layouts[6])
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, PptxCm(0.35))
        bar.fill.solid()
        bar.fill.fore_color.rgb = ACCENT_PPTX
        bar.line.fill.background()
        bar.shadow.inherit = False
        return s

    def titulo_slide(s, numero, texto):
        box = s.shapes.add_textbox(PptxCm(1), PptxCm(0.7), prs.slide_width - PptxCm(2), PptxCm(1.5))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r0 = p.add_run()
        r0.text = f"{numero}  "
        r0.font.size = PptxPt(14)
        r0.font.color.rgb = PptxRGBColor(0x8A, 0x92, 0x9B)
        r0.font.name = "Consolas"
        r1 = p.add_run()
        r1.text = texto
        r1.font.size = PptxPt(24)
        r1.font.bold = True
        r1.font.color.rgb = ACCENT_PPTX
        r1.font.name = "Arial"

    def bullets_slide(s, itens, top=2.3, size=14):
        box = s.shapes.add_textbox(PptxCm(1), PptxCm(top), prs.slide_width - PptxCm(2),
                                   prs.slide_height - PptxCm(top + 0.5))
        tf = box.text_frame
        tf.word_wrap = True
        for i, texto in enumerate(itens):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r = p.add_run()
            r.text = f"•  {texto}"
            r.font.size = PptxPt(size)
            r.font.name = "Arial"
            r.font.color.rgb = TEXT_PPTX
            p.space_after = PptxPt(8)

    # --- Slide 1: objetivo ---
    s1 = slide_branco()
    titulo_slide(s1, "01", "MIT_P x MIT_G — Sintonia Automática em Duas Frequências")
    bullets_slide(s1, [
        "Mesmo motor, mesma correção de ganhos do FOC, mesma sintonia automática por banda passante — "
        "testados em 60 Hz (velocidade nominal) e 30 Hz (metade da nominal), nos dois motores.",
        "Objetivo: mostrar se a sintonia automática entrega desempenho equivalente quando o porte do motor "
        "e a frequência de referência mudam ao mesmo tempo.",
    ], top=3.0, size=16)

    n = 1

    def prox():
        nonlocal n
        n += 1
        return f"{n:02d}"

    # --- Slides: os três zooms, para cada frequência ---
    ZOOMS = (
        ("carga", "Entrada da Carga"),
        ("carga_detalhe", "Entrada da Carga: Detalhe"),
        ("chegada", "Chegada na Referência de Velocidade"),
    )
    for freq in FREQS:
        for chave, rotulo in ZOOMS:
            s = slide_branco()
            titulo_slide(s, prox(), f"{rotulo} a {freq:g} Hz — MIT_P (esq.) x MIT_G (dir.)")
            img_p = FIGURAS / f"P_{freq:g}Hz_{chave}.png"
            img_g = FIGURAS / f"G_{freq:g}Hz_{chave}.png"
            if img_p.exists():
                s.shapes.add_picture(str(img_p), PptxCm(0.4), PptxCm(2.1), width=PptxCm(13.6))
            if img_g.exists():
                s.shapes.add_picture(str(img_g), PptxCm(14.1), PptxCm(2.1), width=PptxCm(13.6))

    # --- Slides: índices comparados através das frequências ---
    for coluna, titulo_fig, titulo_y in (
        ("sobressinal_pct", "Sobressinal x Frequência (60 e 30 Hz)", "Sobressinal (%)"),
        ("tempo_subida", "Tempo de Subida x Frequência (60 e 30 Hz)", "Tempo de subida (s)"),
    ):
        fig = _figura_comparativa_freq(dados_por_freq, coluna, titulo_y)
        caminho = FIGURAS / f"consolidado_{coluna}.png"
        gr.salvar_imagem(fig, caminho)
        fig.write_html(str(caminho.with_suffix(".html")))
        s = slide_branco()
        titulo_slide(s, prox(), titulo_fig)
        s.shapes.add_picture(str(caminho), PptxCm(1.4), PptxCm(2.3), width=PptxCm(25.2))

    # --- Slide final: tópicos ---
    s6 = slide_branco()
    titulo_slide(s6, prox(), "Desempenho a 60 Hz x 30 Hz — Mesma Sintonia, Motores Diferentes")
    bullets_slide(s6, [
        "A 60 Hz (velocidade e carga nominais), a mesma sintonia automática do FOC se comporta de forma bem "
        "mais heterogênea entre os dois motores do que a 30 Hz — o motor grande mostra sobressinal e "
        "oscilação pós-carga bem mais acentuados do que o pequeno nessa condição.",
        "A 30 Hz, com metade da referência de velocidade e do escorregamento nominal envolvidos, o "
        "comportamento do FOC nos dois motores se aproxima mais um do outro — a diferença de porte pesa "
        "menos quando a máquina opera longe da condição nominal plena.",
        "Em ambas as frequências, o V/F em malha aberta não corrige o mesmo tipo de desvio de velocidade "
        "sob carga que o FOC corrige — essa vantagem estrutural do FOC se mantém independente do porte do "
        "motor e da frequência de referência.",
        "Conclusão: a sintonia automática por banda passante, calculada só a partir da frequência de "
        "chaveamento e dos parâmetros do motor, não garante o mesmo grau de robustez em toda combinação de "
        "porte de máquina e ponto de operação — o caso mais exigente observado aqui foi o motor grande "
        "operando na condição nominal (60 Hz, carga plena), não o motor pequeno nem a operação em frequência "
        "reduzida.",
    ], top=2.2, size=13.5)

    destino = PASTA / "Apresentacao_Comparativo_Consolidado.pptx"
    prs.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    dados_por_freq = {freq: montar(freq) for freq in FREQS}
    montar_pptx_consolidado(dados_por_freq)
