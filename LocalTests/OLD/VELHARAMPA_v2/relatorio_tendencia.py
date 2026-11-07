"""Relatório de tendência: evolução do sobressinal e do tempo de subida com a
frequência de referência (60/55/45/30 Hz), para um motor (P ou G). Usa os
mesmos dados brutos e a mesma análise (`comum.anotacoes.analisar`) dos
relatórios por frequência — sem tempo de acomodação (ver nota em
`graficos.py`). Também monta a apresentação (.pptx) com a síntese.

Requer que `simular.py <motor> <freq>` já tenha rodado para as 4 frequências.

    python relatorio_tendencia.py P
    python relatorio_tendencia.py G
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graficos as gr
from comum import anotacoes as an
from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS = PASTA.parent / "VELHARAMPA" / "dados"
FIGURAS = PASTA / "figuras"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
ACCENT_PPTX = PptxRGBColor(0x0E, 0x5C, 0x68)
MUTED_PPTX = PptxRGBColor(0x5B, 0x66, 0x72)
TEXT_PPTX = PptxRGBColor(0x1A, 0x20, 0x27)

FREQS = (60.0, 30.0)
CORES = {"dol": "#2ca02c", "vf": "#1f77b4", "foc": "#d62728"}
NOMES = {"dol": "Partida direta (DOL)", "vf": "Inversor V/F", "foc": "Inversor FOC"}
MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}


def _carregar(motor_id, freq_hz, cenario):
    p = DADOS / f"{motor_id}_{freq_hz:g}Hz_{cenario}.npz"
    if not p.exists():
        return None
    d = np.load(p)
    return d["t"], d["velocidade_rpm"], d["conjugado"]


def coletar(motor_id, freqs=FREQS):
    sim, construir_motor, _ = MOTORES[motor_id]
    motor = construir_motor()
    linhas = []
    for freq in freqs:
        evs = gr.eventos(motor, sim, freq)
        cenarios = ("dol", "vf", "foc") if abs(freq - 60.0) < 1e-9 else ("vf", "foc")
        for cenario in cenarios:
            dados = _carregar(motor_id, freq, cenario)
            if dados is None:
                continue
            t, vel, conj = dados
            for evento_idx, evento_nome in enumerate(("partida", "carga")):
                for grandeza, y in (("velocidade", vel), ("conjugado", conj)):
                    ev = evs[grandeza][evento_idx]
                    y_ini = 0.0 if evento_idx == 0 else an.valor_pre_evento(t, y, ev.t_ini)
                    res = an.analisar(t, y, ev, y_ini)
                    linhas.append(dict(
                        freq=freq, cenario=cenario, evento=evento_nome, grandeza=grandeza,
                        sobressinal_pct=res["sobressinal_pct"],
                        tempo_subida=res["tempo_subida"],
                    ))
    return pd.DataFrame(linhas)


EVENTOS = (("partida", "Entrada em velocidade nominal"), ("carga", "Entrada da carga"))
GRANDEZAS = (("velocidade", "Velocidade"), ("conjugado", "Conjugado"))


def _figura_tendencia(df, coluna, titulo_y):
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True,
                        subplot_titles=[f"{g} — {e}" for g, _ in GRANDEZAS for _, e in EVENTOS],
                        vertical_spacing=0.12, horizontal_spacing=0.08)
    for i, (grandeza, _) in enumerate(GRANDEZAS):
        for j, (evento, _) in enumerate(EVENTOS):
            sub = df[(df.grandeza == grandeza) & (df.evento == evento)]
            for cenario in ("dol", "vf", "foc"):
                s = sub[sub.cenario == cenario].sort_values("freq")
                if s.empty:
                    continue
                modo = "markers" if len(s) == 1 else "lines+markers"
                fig.add_trace(
                    go.Scatter(x=s["freq"], y=s[coluna], mode=modo, name=NOMES[cenario],
                              legendgroup=cenario, showlegend=(i == 0 and j == 0),
                              line=dict(color=CORES[cenario], width=2),
                              marker=dict(color=CORES[cenario], size=8)),
                    row=i + 1, col=j + 1,
                )
    fig.update_xaxes(title_text="Frequência de referência (Hz)", row=2, autorange="reversed")
    for i in range(1, 3):
        fig.update_yaxes(title_text=titulo_y, row=i, col=1)
    fig.update_layout(height=760, width=1150, font=dict(family="Arial"),
                      legend=dict(orientation="h", y=-0.1), margin=dict(t=50, b=80, l=70, r=25))
    return fig


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


def _extremos(df, cenario, grandeza, evento, coluna):
    s = df[(df.cenario == cenario) & (df.grandeza == grandeza) & (df.evento == evento)].sort_values("freq")
    if s.empty:
        return None
    return s.iloc[0], s.iloc[-1]


def montar_docx(motor_id, df):
    sim, construir_motor, rotulo_motor = MOTORES[motor_id]
    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run(f"Tendência com a frequência de referência — {rotulo_motor}")
    r.font.size = Pt(20)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run("Sobressinal e tempo de subida em 60, 55, 45 e 30 Hz")
    r.font.size = Pt(13)
    r.font.color.rgb = MUTED
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    doc.add_paragraph(
        "Este relatório reúne, nas quatro frequências de referência ensaiadas, o sobressinal e o tempo de "
        "subida (10-90%) da velocidade e do conjugado dos acionamentos V/F e FOC, na partida e na entrada da "
        "carga, para observar como cada acionamento se comporta conforme a referência de frequência diminui."
    )

    doc.add_page_break()
    _titulo_secao(doc, "Sobressinal (%)")
    fig = _figura_tendencia(df, "sobressinal_pct", "Sobressinal (%)")
    c1 = FIGURAS / f"{motor_id}_tendencia_sobressinal.png"
    fig.write_image(str(c1), scale=2)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(c1), width=Cm(17))

    doc.add_page_break()
    _titulo_secao(doc, "Tempo de subida — 10 a 90% (s)")
    fig = _figura_tendencia(df, "tempo_subida", "Tempo de subida (s)")
    c2 = FIGURAS / f"{motor_id}_tendencia_subida.png"
    fig.write_image(str(c2), scale=2)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(c2), width=Cm(17))

    doc.add_page_break()
    _titulo_secao(doc, "Tabela de dados")
    tabela = doc.add_table(rows=1, cols=6)
    tabela.style = "Light Grid Accent 1"
    cab = ("Frequência (Hz)", "Acionamento", "Evento", "Grandeza", "Sobressinal (%)", "Subida (s)")
    for c, nome in zip(tabela.rows[0].cells, cab):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for _, row in df.sort_values(["freq", "cenario", "evento", "grandeza"], ascending=[False, True, True, True]).iterrows():
        vals = (f"{row.freq:g}", NOMES[row.cenario], row.evento, row.grandeza,
                f"{row.sobressinal_pct:+.1f}", f"{row.tempo_subida:.3f}" if pd.notna(row.tempo_subida) else "—")
        cels = tabela.add_row().cells
        for c, v in zip(cels, vals):
            c.text = v
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8.5)
                    r.font.name = "Arial"

    destino = PASTA / f"Tendencia_{motor_id}.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


def montar_pptx(motor_id, df):
    _, _, rotulo_motor = MOTORES[motor_id]
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

    s1 = slide_branco()
    titulo_slide(s1, "01", f"Tendência com a Frequência — {rotulo_motor}")
    box = s1.shapes.add_textbox(PptxCm(1), PptxCm(2.3), prs.slide_width - PptxCm(2), PptxCm(2))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = ("Sobressinal e tempo de subida do V/F e do FOC em 60, 55, 45 e 30 Hz, "
             "na partida e na entrada da carga nominal.")
    r.font.size = PptxPt(15)
    r.font.color.rgb = MUTED_PPTX

    for chave, titulo_fig, arquivo in (
        ("sobressinal_pct", "Sobressinal (%) x Frequência", f"{motor_id}_tendencia_sobressinal.png"),
        ("tempo_subida", "Tempo de Subida (s) x Frequência", f"{motor_id}_tendencia_subida.png"),
    ):
        s = slide_branco()
        titulo_slide(s, "02" if chave == "sobressinal_pct" else "03", titulo_fig)
        caminho = FIGURAS / arquivo
        if caminho.exists():
            s.shapes.add_picture(str(caminho), PptxCm(2.2), PptxCm(2.1), width=PptxCm(23.6))

    s4 = slide_branco()
    titulo_slide(s4, "04", "Leitura dos Resultados")
    bullets = []
    for grandeza, _ in GRANDEZAS:
        for evento, evento_nome in EVENTOS:
            extremos_vf = _extremos(df, "vf", grandeza, evento, "sobressinal_pct")
            extremos_foc = _extremos(df, "foc", grandeza, evento, "sobressinal_pct")
            if extremos_vf and extremos_foc:
                v0, v1 = extremos_vf
                f0, f1 = extremos_foc
                bullets.append(
                    f"{grandeza.capitalize()}, {evento_nome.lower()}: sobressinal do V/F vai de "
                    f"{v0.sobressinal_pct:+.1f}% (60 Hz) a {v1.sobressinal_pct:+.1f}% (30 Hz); do FOC, de "
                    f"{f0.sobressinal_pct:+.1f}% a {f1.sobressinal_pct:+.1f}%."
                )
    box = s4.shapes.add_textbox(PptxCm(1), PptxCm(2.2), prs.slide_width - PptxCm(2), PptxCm(12))
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = f"•  {b}"
        r.font.size = PptxPt(13)
        r.font.name = "Arial"
        r.font.color.rgb = TEXT_PPTX
        p.space_after = PptxPt(8)

    destino = PASTA / f"Apresentacao_Tendencia_{motor_id}.pptx"
    prs.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    motor_id = sys.argv[1]
    df = coletar(motor_id)
    FIGURAS.mkdir(exist_ok=True)
    montar_docx(motor_id, df)
    montar_pptx(motor_id, df)
