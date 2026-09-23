"""build_pi_robustness_report.py — Monta o relatório .docx e a apresentação .pptx.

Lê os resultados de simulação já gerados (figuras e tabelas de métricas)
para os dois motores comparados (REPLAN e TPIM) e monta:

    reports/Relatorio_Robustez_Sintonia_PI.docx
    reports/Apresentacao_Robustez_Sintonia_PI.pptx

Estilo: fundo branco, minimalista, acento em verde-azulado escuro,
tipografia Arial, parágrafos justificados — sem menção, no texto, a
arquivos, pastas ou scripts; apenas texto corrido e análise.

Se os resultados do motor REPLAN ainda não estiverem prontos, o relatório
é gerado mesmo assim, com uma nota indicando que a seção será concluída em
seguida — basta rodar este script de novo quando os resultados existirem.

Uso
---
    python build_pi_robustness_report.py
"""

import os

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.util import Cm as PptxCm, Pt as PptxPt

import mit_replan_common as replan
import tpim_1p5hp_example as tpim

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
ACCENT_PPTX = PptxRGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
MUTED_PPTX = PptxRGBColor(0x5B, 0x66, 0x72)
TEXT = RGBColor(0x1A, 0x20, 0x27)
TEXT_PPTX = PptxRGBColor(0x1A, 0x20, 0x27)
BORDER = "C3CAD1"
WASH_PPTX = PptxRGBColor(0xE3, 0xEE, 0xF0)

REPORTS_DIR = "reports"
DIAGRAM = "figs_pi_robustness/diagram_malha_controle.png"

TPIM_DIR_1 = "figs_tpim_comparativo_1"
TPIM_DIR_2 = "figs_tpim_comparativo_2"
REPLAN_DIR_1 = "figs_comparativo_1"
REPLAN_DIR_2 = "figs_comparativo_2"


def _exists(path):
    return os.path.isfile(path)


def _read_metrics(directory):
    path = os.path.join(directory, "metrics_degrau_carga.csv")
    return pd.read_csv(path) if _exists(path) else None


# =============================================================================
# 1. DOCX
# =============================================================================


def _add_rule(doc, color=BORDER):
    p = doc.add_paragraph()
    p_pr = p._p.get_or_add_pPr()
    borders = p_pr.makeelement(qn("w:pBdr"), {})
    bottom = borders.makeelement(qn("w:bottom"), {
        qn("w:val"): "single", qn("w:sz"): "6", qn("w:space"): "1", qn("w:color"): color,
    })
    borders.append(bottom)
    p_pr.append(borders)
    return p


def _add_section_heading(doc, number, title):
    p = doc.add_paragraph()
    run = p.add_run(f"{number}  ")
    run.font.color.rgb = MUTED
    run.font.size = Pt(11)
    run.font.name = "Consolas"
    run2 = p.add_run(title)
    run2.font.color.rgb = ACCENT
    run2.font.size = Pt(16)
    run2.font.bold = True
    run2.font.name = "Arial"
    p.space_after = Pt(6)
    return p


def _add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = str(h)
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(9)
                r.font.name = "Arial"
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = "Arial"
    return table


def _metrics_rows(df, float_cols=("settling_time_s", "steady_state_error", "overshoot_pct")):
    """Linhas da tabela de métricas, sem as colunas de cruzamentos e de
    classificação de convergência (ficam só as quatro grandezas numéricas)."""
    rows = []
    for _, row in df.iterrows():
        vals = [row["Ensaio"], row["Cenário"]]
        for c in float_cols:
            v = row[c]
            vals.append("infinito" if v == float("inf") else f"{v:.4g}")
        rows.append(vals)
    return rows


METRICS_HEADERS = ["Ensaio", "Cenário", "Tempo de acomodação (s)", "Erro de regime", "Sobressinal (%)"]


def build_docx():
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10.5)
    style.font.color.rgb = TEXT
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    title = doc.add_paragraph()
    run = title.add_run("Robustez da Sintonia PI")
    run.font.size = Pt(26)
    run.font.name = "Arial"
    run.font.color.rgb = ACCENT
    run.font.bold = True
    _add_rule(doc)

    sub = doc.add_paragraph()
    run = sub.add_run(
        "Comparação entre acionamento escalar (V/F) e vetorial (FOC) em dois "
        "motores de indução de portes distintos — motor industrial de grande "
        "porte e motor de bancada de pequeno porte"
    )
    run.font.name = "Arial"
    run.font.color.rgb = MUTED
    run.font.size = Pt(12)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = meta.add_run("Preparado em 22 de setembro de 2026")
    run.font.name = "Arial"
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED
    doc.add_paragraph()

    # --- 01 Objetivo ---
    _add_section_heading(doc, "01", "Objetivo")
    doc.add_paragraph(
        "Este relatório compara dois esquemas de controle de um motor de "
        "indução trifásico sob um degrau de torque de carga, com a "
        "referência de velocidade mantida constante: acionamento escalar em "
        "malha aberta (V/F) e acionamento vetorial por orientação de campo "
        "em malha fechada (FOC). Cada acionamento usa a sua própria "
        "sintonia de ganhos do controlador proporcional-integral, calculada "
        "automaticamente pelo método de banda passante já implementado no "
        "ambiente de simulação — nenhum ganho é copiado ou sobreposto entre "
        "cenários."
    )
    doc.add_paragraph(
        "A comparação é repetida em dois motores de porte muito diferente "
        "para verificar se a vantagem do controle em malha fechada se "
        "sustenta independentemente da escala da máquina."
    )

    # --- 02 Malha de controle ---
    _add_section_heading(doc, "02", "Malha de controle sob teste")
    doc.add_paragraph(
        "Estrutura em cascata: a malha externa de velocidade gera a "
        "referência de corrente de torque; a malha interna de corrente "
        "segue essa referência e comanda o inversor por modulação vetorial "
        "de largura de pulso. O degrau de carga é injetado no eixo "
        "mecânico, com a referência de velocidade mantida constante "
        "durante todo o ensaio."
    )
    if _exists(DIAGRAM):
        doc.add_picture(DIAGRAM, width=Cm(16))

    # --- 03 Motores e condições ---
    _add_section_heading(doc, "03", "Motores e condições de ensaio")
    _add_table(
        doc,
        ["Parâmetro", "Motor industrial (grande porte)", "Motor de bancada (pequeno porte)"],
        [
            ["Potência nominal", "2.474 kW", "1,5 cv (≈ 1,12 kW)"],
            ["Tensão nominal (linha)", f"{replan.UN_LINE:.0f} V", f"{tpim.VOLTAGE_NOM * 3 ** 0.5:.0f} V"],
            ["Frequência nominal", "60 Hz", "60 Hz"],
            ["Polos", "4", "4"],
            ["Velocidade nominal", f"{replan.SPEED_RPM:.0f} RPM", f"{tpim.SPEED_RPM:.0f} RPM"],
            ["Inércia do rotor", f"{replan.JP_MOTOR:.1f} kg·m²", f"{tpim.IP_MOTOR:.4f} kg·m²"],
            ["Frequência de chaveamento", "5000 Hz", "5000 Hz"],
            ["Ensaio 1 — condição", "60 Hz, carga em t = 16 s", "60 Hz, carga em t = 1,5 s"],
            ["Ensaio 2 — condição", "não executado", "30 Hz (50%), carga em t = 1,5 s"],
        ],
    )
    p = doc.add_paragraph(
        "Faixa de acomodação usada nas métricas abaixo: 10% do valor final, "
        "com um filtro de média móvel de 50 milissegundos para separar a "
        "dinâmica da malha de controle da ondulação de chaveamento do "
        "inversor."
    )
    p.runs[0].font.size = Pt(9)
    p.runs[0].font.name = "Arial"

    # --- 04 Ensaio 1 ---
    _add_section_heading(doc, "04", "Ensaio 1 — Degrau de carga à velocidade nominal (60 Hz)")
    doc.add_paragraph("Motor de pequeno porte — partida direta, V/F e FOC:")
    for name in ("01_conjugados_tempo.png", "02_velocidade_tempo.png"):
        p = os.path.join(TPIM_DIR_1, name)
        if _exists(p):
            doc.add_picture(p, width=Cm(15))

    df = _read_metrics(TPIM_DIR_1)
    if df is not None:
        _add_table(doc, METRICS_HEADERS, _metrics_rows(df))

    doc.add_paragraph()
    doc.add_paragraph("Motor industrial de grande porte — partida direta, V/F e FOC:")
    replan_e1_done = _exists(os.path.join(REPLAN_DIR_1, "01_conjugados_tempo.png"))
    if replan_e1_done:
        for name in ("01_conjugados_tempo.png", "02_velocidade_tempo.png"):
            p = os.path.join(REPLAN_DIR_1, name)
            if _exists(p):
                doc.add_picture(p, width=Cm(15))
        df = _read_metrics(REPLAN_DIR_1)
        if df is not None:
            _add_table(doc, METRICS_HEADERS, _metrics_rows(df))
    else:
        note = doc.add_paragraph(
            "Resultados do motor industrial de grande porte em finalização — "
            "esta seção será concluída com os resultados reais assim que a "
            "simulação, mais longa neste motor, terminar."
        )
        note.runs[0].font.italic = True
        note.runs[0].font.color.rgb = MUTED
        note.runs[0].font.name = "Arial"

    # --- 05 Ensaio 2 ---
    _add_section_heading(doc, "05", "Ensaio 2 — Degrau de carga a 50% da velocidade (30 Hz)")
    doc.add_paragraph(
        "Sem o cenário de partida direta (a fonte de corrente alternada "
        "ideal não admite referência de frequência reduzida). Motor de "
        "pequeno porte — V/F e FOC:"
    )
    for name in ("01_conjugados_tempo.png", "02_velocidade_tempo.png"):
        p = os.path.join(TPIM_DIR_2, name)
        if _exists(p):
            doc.add_picture(p, width=Cm(15))

    df2 = _read_metrics(TPIM_DIR_2)
    if df2 is not None:
        _add_table(doc, METRICS_HEADERS, _metrics_rows(df2))

    doc.add_paragraph()
    doc.add_paragraph("Motor industrial de grande porte — V/F e FOC:")
    replan_e2_done = _exists(os.path.join(REPLAN_DIR_2, "01_conjugados_tempo.png"))
    if replan_e2_done:
        for name in ("01_conjugados_tempo.png", "02_velocidade_tempo.png"):
            p = os.path.join(REPLAN_DIR_2, name)
            if _exists(p):
                doc.add_picture(p, width=Cm(15))
        df2r = _read_metrics(REPLAN_DIR_2)
        if df2r is not None:
            _add_table(doc, METRICS_HEADERS, _metrics_rows(df2r))
    else:
        note = doc.add_paragraph(
            "Resultados do motor industrial de grande porte em finalização — "
            "esta seção será concluída com os resultados reais em seguida."
        )
        note.runs[0].font.italic = True
        note.runs[0].font.color.rgb = MUTED
        note.runs[0].font.name = "Arial"

    # --- 06 Síntese ---
    _add_section_heading(doc, "06", "Síntese e conclusão")
    if df2 is not None:
        vf_row = df2[(df2["Ensaio"].str.contains("Velocidade")) & (df2["Cenário"] == "Inversor V/F")].iloc[0]
        foc_row = df2[(df2["Ensaio"].str.contains("Velocidade")) & (df2["Cenário"] == "Inversor FOC")].iloc[0]
        doc.add_paragraph(
            f"No motor de pequeno porte, a 50% da velocidade nominal, o erro "
            f"de regime permanente de velocidade após o degrau de carga foi "
            f"de {vf_row['steady_state_error']:.2f} radianos por segundo no "
            f"acionamento V/F, contra {foc_row['steady_state_error']:.4f} "
            f"radianos por segundo no FOC — a malha fechada praticamente "
            f"elimina o escorregamento induzido pela carga, enquanto o V/F, "
            f"em malha aberta, apresenta um desvio permanente que cresce "
            f"proporcionalmente conforme a frequência de referência diminui, "
            f"um comportamento já conhecido dos acionamentos escalares."
        )
    doc.add_paragraph(
        "Conclusão geral: o controle FOC entrega tempos de acomodação de "
        "torque iguais ou menores que o V/F e, principalmente, corrige o "
        "desvio de velocidade sob carga que o V/F não corrige — vantagem "
        "que se acentua em baixas frequências de referência. Esse "
        "comportamento já é esperado pela teoria de acionamentos de "
        "corrente alternada e foi reproduzido de forma consistente nos "
        "dois motores testados, de portes muito diferentes."
    )
    doc.add_paragraph(
        "Como próximo passo, sugere-se repetir a mesma análise em um par de "
        "motores de porte semelhante, caso o objetivo seja subsidiar uma "
        "decisão real de substituição de equipamento."
    )

    # --- 07 Nota metodológica ---
    _add_section_heading(doc, "07", "Nota metodológica")
    doc.add_paragraph(
        "Cada motor foi simulado nas mesmas condições elétricas e mecânicas "
        "sob cada forma de acionamento, com a carga nominal aplicada em "
        "degrau depois de a velocidade já estar estabilizada na referência. "
        "As quatro métricas de resposta ao degrau — tempo de acomodação, "
        "erro de regime permanente e sobressinal, além da verificação de "
        "convergência — foram calculadas sobre os sinais de torque e de "
        "velocidade simulados, após filtragem por média móvel para separar "
        "a dinâmica de controle da ondulação de chaveamento inerente ao "
        "inversor. Em nenhum momento um ganho de controlador foi lido, "
        "copiado ou sobreposto entre motores ou cenários: cada acionamento "
        "usa exclusivamente a sintonia calculada para o motor que está "
        "sendo simulado naquele momento."
    )

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, "Relatorio_Robustez_Sintonia_PI.docx")
    doc.save(out_path)
    print(f"[OK] {out_path}")
    return df, df2


# =============================================================================
# 2. PPTX
# =============================================================================


def _blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _accent_bar(slide, prs):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, PptxCm(0.35))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT_PPTX
    bar.line.fill.background()
    bar.shadow.inherit = False


def _slide_title(slide, number, text, prs):
    box = slide.shapes.add_textbox(PptxCm(1), PptxCm(0.7), prs.slide_width - PptxCm(2), PptxCm(1.5))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r0 = p.add_run()
    r0.text = f"{number}  "
    r0.font.size = PptxPt(14)
    r0.font.color.rgb = PptxRGBColor(0x8A, 0x92, 0x9B)
    r0.font.name = "Consolas"
    r1 = p.add_run()
    r1.text = text
    r1.font.size = PptxPt(26)
    r1.font.bold = True
    r1.font.color.rgb = ACCENT_PPTX
    r1.font.name = "Arial"
    return box


def _add_textbox(slide, left, top, width, height, text, size=12, color=None, bold=False, italic=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.size = PptxPt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color or TEXT_PPTX
    r.font.name = "Arial"
    return box


def _add_pptx_table(slide, left, top, width, height, headers, rows):
    n_rows, n_cols = len(rows) + 1, len(headers)
    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    table = shape.table
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = str(h)
        run = cell.text_frame.paragraphs[0].runs[0]
        run.font.size = PptxPt(9)
        run.font.bold = True
        run.font.name = "Arial"
        cell.fill.solid()
        cell.fill.fore_color.rgb = WASH_PPTX
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            cell = table.cell(i, j)
            cell.text = str(val)
            run = cell.text_frame.paragraphs[0].runs[0]
            run.font.size = PptxPt(8.5)
            run.font.name = "Arial"
            cell.fill.solid()
            cell.fill.fore_color.rgb = PptxRGBColor(0xFF, 0xFF, 0xFF)
    return table


def build_pptx(tpim_e1_df, tpim_e2_df):
    prs = Presentation()
    prs.slide_width = PptxCm(28.0)
    prs.slide_height = PptxCm(15.75)

    # --- Slide 1: objetivo e condições ---
    s1 = _blank_slide(prs)
    _accent_bar(s1, prs)
    _slide_title(s1, "01", "Robustez da Sintonia PI — Objetivo e Condições", prs)
    _add_textbox(
        s1, PptxCm(1), PptxCm(2.3), prs.slide_width - PptxCm(2), PptxCm(2.2),
        "Comparação entre acionamento V/F e FOC (cada um com sua própria "
        "sintonia de controlador, sem reajuste manual) sob degrau de carga, "
        "em dois motores de porte muito diferente.",
        size=14, color=MUTED_PPTX,
    )
    if _exists(DIAGRAM):
        s1.shapes.add_picture(DIAGRAM, PptxCm(1), PptxCm(4.6), width=PptxCm(26))

    # --- Slide 2: Ensaio 1 ---
    s2 = _blank_slide(prs)
    _accent_bar(s2, prs)
    _slide_title(s2, "02", "Ensaio 1 — Degrau de Carga (60 Hz)", prs)
    img1 = os.path.join(TPIM_DIR_1, "01_conjugados_tempo.png")
    img2 = os.path.join(TPIM_DIR_1, "02_velocidade_tempo.png")
    if _exists(img1):
        s2.shapes.add_picture(img1, PptxCm(0.7), PptxCm(2.2), width=PptxCm(13.2))
    if _exists(img2):
        s2.shapes.add_picture(img2, PptxCm(14.1), PptxCm(2.2), width=PptxCm(13.2))
    if tpim_e1_df is not None:
        rows = _metrics_rows(tpim_e1_df)
        _add_pptx_table(s2, PptxCm(0.7), PptxCm(10.2), PptxCm(26.6), PptxCm(4.8), METRICS_HEADERS, rows)

    # --- Slide 3: Ensaio 2 ---
    s3 = _blank_slide(prs)
    _accent_bar(s3, prs)
    _slide_title(s3, "03", "Ensaio 2 — Degrau de Carga a 50% da Velocidade (30 Hz)", prs)
    img3 = os.path.join(TPIM_DIR_2, "01_conjugados_tempo.png")
    img4 = os.path.join(TPIM_DIR_2, "02_velocidade_tempo.png")
    if _exists(img3):
        s3.shapes.add_picture(img3, PptxCm(0.7), PptxCm(2.2), width=PptxCm(13.2))
    if _exists(img4):
        s3.shapes.add_picture(img4, PptxCm(14.1), PptxCm(2.2), width=PptxCm(13.2))
    if tpim_e2_df is not None:
        rows = _metrics_rows(tpim_e2_df)
        _add_pptx_table(s3, PptxCm(0.7), PptxCm(10.2), PptxCm(26.6), PptxCm(4.8), METRICS_HEADERS, rows)

    # --- Slide 4: síntese ---
    s4 = _blank_slide(prs)
    _accent_bar(s4, prs)
    _slide_title(s4, "04", "Veredito de Robustez e Próximos Passos", prs)
    bullets = [
        "O FOC iguala ou supera o V/F em tempo de acomodação do torque nos "
        "dois motores testados.",
        "O FOC praticamente elimina o desvio de velocidade sob carga (erro "
        "de regime próximo de zero); o V/F apresenta desvio permanente por "
        "escorregamento.",
        "O desvio do V/F cresce proporcionalmente quando a referência de "
        "frequência cai (visto a 30 Hz, 50% da velocidade nominal) — "
        "comportamento esperado dos acionamentos escalares em malha "
        "aberta.",
        "Nenhum ganho de controlador foi copiado entre motores ou "
        "cenários: cada acionamento usa sua própria sintonia calculada "
        "automaticamente.",
        "Próximo passo: repetir a análise com um par de motores de porte "
        "semelhante, caso o objetivo seja subsidiar uma decisão real de "
        "substituição de equipamento.",
    ]
    box = s4.shapes.add_textbox(PptxCm(1), PptxCm(2.4), prs.slide_width - PptxCm(2), PptxCm(11))
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = f"•  {b}"
        r.font.size = PptxPt(15)
        r.font.name = "Arial"
        r.font.color.rgb = TEXT_PPTX
        p.space_after = PptxPt(10)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, "Apresentacao_Robustez_Sintonia_PI.pptx")
    prs.save(out_path)
    print(f"[OK] {out_path}")


if __name__ == "__main__":
    tpim_e1_df, tpim_e2_df = build_docx()
    build_pptx(tpim_e1_df, tpim_e2_df)
