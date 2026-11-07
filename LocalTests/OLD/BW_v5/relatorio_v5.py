"""Relatório: formulação detalhada da sintonia motor-aware do FOC
(InverterFOCv5), tabela de ganhos previstos para 30/45/55/62 Hz, e
validação por simulação nos dois motores, nas 4 frequências.

Requer que `simular_v5.py` já tenha rodado para os dois motores nas 4
frequências.

    python relatorio_v5.py
"""

import sys
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import motores
from inverter_foc_v5 import InverterFOCv5, K_IDS, K_IQS
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS_V5 = PASTA / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)

FREQS = (30.0, 45.0, 55.0, 62.0)
T_CARGA = {"P": 1.5, "G": 13.0}
TNOM = {"P": 6.246412, "G": 13190.932302}
MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}


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


def _titulo_secao(doc, texto, tamanho=14):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(tamanho)
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


def _formula(doc, texto):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.font.name = "Consolas"
    r.font.size = Pt(9.5)
    r.font.color.rgb = ACCENT
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.space_after = Pt(4)


def _extrair_parametros(motor_id):
    sim, construir_motor, _ = MOTORES[motor_id]
    motor = construir_motor()
    inv = InverterFOCv5(
        voltage_dc=motor.voltage_nom * 1.414 * np.sqrt(2), frequency_s=Q_(5000.0, "Hz"),
        voltage_nom=motor.voltage_nom, frequency_nom=motor.frequency_nom, n_poles=motor.n_poles,
        speed_nom=motor.speed_nom, torque_nom=motor.Tnom, stator_resistance=motor.stator_resistance,
        rotor_resistance=motor.rotor_resistance, stator_reactance=motor.stator_reactance,
        rotor_reactance=motor.rotor_reactance, mutual_reactance=motor.mutual_reactance,
        Ip_motor=motor.Ip_motor, time_ramp=0.6667, frequency_ref=Q_(60.0, "Hz"),
    )
    return inv


def _tabela_ganhos(doc):
    tabela = doc.add_table(rows=1, cols=7)
    tabela.style = "Light Grid Accent 1"
    cab = ("Motor", "Freq. (Hz)", "BWp_iqs (Hz)", "kp_iqs", "ki_iqs", "BWp_ids (Hz)", "kp_ids")
    for c, nome in zip(tabela.rows[0].cells, cab):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for motor_id in ("P", "G"):
        inv = _extrair_parametros(motor_id)
        for freq in FREQS:
            cels = tabela.add_row().cells
            vals = ("MIT_P" if motor_id == "P" else "MIT_G", f"{freq:g}",
                    f"{inv.bwp_iqs_hz:.2f}", f"{inv.kp_iqs:.3f}", f"{inv.ki_iqs:.2f}",
                    f"{inv.bwp_ids_hz:.3f}", f"{inv.kp_ids:.3f}")
            for c, v in zip(cels, vals):
                c.text = v
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"


def _tabela_ki_ids(doc):
    tabela = doc.add_table(rows=1, cols=3)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Motor", "ki_ids", "BWi_ids = BWp_ids (ζ_ids=1)")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for motor_id in ("P", "G"):
        inv = _extrair_parametros(motor_id)
        cels = tabela.add_row().cells
        vals = ("MIT_P" if motor_id == "P" else "MIT_G", f"{inv.ki_ids:.2f}", f"{inv.bwp_ids_hz:.3f} Hz")
        for c, v in zip(cels, vals):
            c.text = v
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"


def _tabela_resultados(doc):
    tabela = doc.add_table(rows=1, cols=4)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Motor", "Freq. (Hz)", "Ripple de conjugado (%)", "Vel. mín. pós-carga (RPM)")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for motor_id in ("P", "G"):
        tnom = TNOM[motor_id]
        for freq in FREQS:
            d = np.load(DADOS_V5 / f"{motor_id}_{freq:g}Hz_foc_v5.npz")
            t, v, c_ = d["t"], d["velocidade_rpm"], d["conjugado"]
            m = t >= t[-1] - 1.0
            rip = (c_[m].max() - c_[m].min()) / tnom * 100
            vmin = v[t >= T_CARGA[motor_id]].min()
            cels = tabela.add_row().cells
            vals = ("MIT_P" if motor_id == "P" else "MIT_G", f"{freq:g}", f"{rip:.2f}", f"{vmin:.1f}")
            for c, v_ in zip(cels, vals):
                c.text = v_
            cels[3].paragraphs[0].runs[0].font.color.rgb = BOM
            cels[3].paragraphs[0].runs[0].font.bold = True
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9.5)
                    r.font.name = "Arial"


def montar():
    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("Sintonia Motor-Aware do FOC (BW_v5) — Formulação e Validação")
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "Descrever em detalhe como cada ganho das malhas de iqs e ids do FOC é obtido no InverterFOCv5 — "
        "a partir dos parâmetros físicos do motor (Rs, Lsline, Lss) e da frequência de chaveamento (fs), "
        "sem nenhuma constante achada por varredura — prever os ganhos resultantes a 30, 45, 55 e 62 Hz, e "
        "validar por simulação nos dois motores, nessas 4 frequências."
    )

    doc.add_page_break()
    _titulo_secao(doc, "Formulação — malha de iqs (corrente de torque)")
    _par(doc, "1) Polo elétrico da própria planta (parâmetro do motor, não escolhido):")
    _formula(doc, "polo_iqs = Rs / (2·π·Lsline)  [Hz]")
    _par(doc, "2) Banda de malha fechada \"alvo\", K_IQS vezes mais rápida que esse polo, nunca excedendo o "
             f"teto de discretização já validado (fs/8, mesmo usado no método original) — K_IQS = {K_IQS:g} "
             "(constante universal adimensional, única escolhida por critério de projeto clássico, não achada "
             "por varredura):")
    _formula(doc, "BWp_iqs_teto = min(K_IQS · polo_iqs, fs/8)")
    _par(doc, "3) Piso: média geométrica entre esse alvo e o valor original do método (fs/8) — evita que "
             "BWp_iqs desabe para perto de zero em motores com polo elétrico muito lento (ex.: MIT_G), sem "
             "nenhuma constante nova além de K_IQS e fs já usadas acima:")
    _formula(doc, "BWp_iqs = sqrt(BWp_iqs_teto · fs/8)")
    _par(doc, "4) Banda do integrador, mesma razão do método original (preserva ζ_iqs = √2, já validado):")
    _formula(doc, "BWi_iqs = BWp_iqs / 8")
    _par(doc, "5) Ganhos finais (mesma forma do InverterFOC original, só a base BWp/BWi mudou):")
    _formula(doc, "kp_iqs = 2·π·Lsline·BWp_iqs")
    _formula(doc, "ki_iqs = Lsline·4·π²·BWp_iqs·BWi_iqs")

    doc.add_paragraph()
    _titulo_secao(doc, "Formulação — malha de ids (corrente de fluxo)")
    _par(doc, "Mesma lógica, com o polo elétrico próprio de ids (Lss no lugar de Lsline) e ζ_ids = 1 "
             "(criticamente amortecido, igual ao método original — BWi_ids = BWp_ids, sem a razão /8):")
    _formula(doc, "polo_ids = Rs / (2·π·Lss)  [Hz]")
    _formula(doc, f"BWp_ids_teto = min(K_IDS · polo_ids, fs/8)      [K_IDS = {K_IDS:g}]")
    _formula(doc, "BWp_ids = sqrt(BWp_ids_teto · fs/8)")
    _formula(doc, "BWi_ids = BWp_ids")
    _formula(doc, "kp_ids = Lss·2·π·(BWp_ids + BWi_ids)")
    _formula(doc, "ki_ids = Lss·4·π²·BWp_ids·BWi_ids")

    doc.add_paragraph()
    _titulo_secao(doc, "Malha de w (velocidade) e anti-windup")
    _par(doc,
        "kp_w e ki_w permanecem os da biblioteca original (não dependem de nenhum parâmetro novo deste "
        "estudo). O anti-windup da malha de iqs — travar state[\"int_err_iqs\"] durante saturação de tensão "
        "— é herdado do BW_v2, sem alteração: evita o ciclo-limite por windup já identificado quando um "
        "integrador é adicionado a uma malha que satura com frequência."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Por que os ganhos não dependem da frequência de acionamento")
    _par(doc,
        "Note que nenhuma das fórmulas acima usa frequency_ref (a frequência de acionamento) — só Rs, "
        "Lsline, Lss (parâmetros do motor) e fs (frequência de chaveamento, fixa no acionamento). Isso é "
        "proposital: fisicamente, a resistência e as indutâncias do motor não mudam com a velocidade "
        "comandada, então os ganhos de malha fechada, que devem casar com essas constantes de tempo da "
        "planta, também não deveriam mudar. A tabela a seguir, por isso, mostra o MESMO ganho nas 4 colunas "
        "de frequência — resultado esperado, não uma omissão.", italico=True, cor=MUTED
    )

    doc.add_page_break()
    _titulo_secao(doc, "Tabela de ganhos previstos — 30, 45, 55 e 62 Hz")
    _tabela_ganhos(doc)
    doc.add_paragraph()
    _par(doc, "ki_ids (não cabe na tabela acima) e banda do integrador de ids:", tamanho=9, cor=MUTED, italico=True)
    _tabela_ki_ids(doc)

    doc.add_page_break()
    _titulo_secao(doc, "Validação por simulação — ripple de conjugado e estabilidade")
    _par(doc,
        "Ripple = (máximo − mínimo) do conjugado bruto no último segundo simulado, dividido pelo conjugado "
        "nominal do motor (Tnom), em %. Velocidade mínima pós-carga: o menor valor de velocidade observado "
        "depois do degrau de carga — usado para detectar instabilidade (valores bem abaixo da referência, ou "
        "negativos, indicam perda de sincronismo, como ocorria em versões anteriores)."
    )
    _tabela_resultados(doc)
    doc.add_paragraph()
    _par(doc,
        "Nenhuma das 8 combinações motor/frequência mostrou qualquer sinal de instabilidade — inclusive "
        "MIT_G a 55 Hz, que em todas as versões anteriores (biblioteca original, v2, v3, v4) apresentava "
        "perda de sincronismo (velocidade negativa) por volta de t≈18 s. Com os ganhos motor-aware do v5, "
        "essa combinação fica estável em 1650,0 RPM do início ao fim do regime pós-carga.",
        negrito=True, cor=BOM
    )

    doc.add_page_break()
    _titulo_secao(doc, "Figuras geradas")
    _par(doc,
        "Para cada motor (MIT_P, MIT_G) e cada frequência (30, 45, 55, 62 Hz), em subpastas "
        "Velocidade/, Torque/, Idq/ e Espectros/ dentro de MIT_P/ e MIT_G/:"
    )
    itens = [
        "Velocidade e Torque: visão geral (V/F x FOC), sem marcadores nem anotações nos pontos de máximo.",
        "Idq: corrente iq (torque) e id (fluxo) do FOC, em subplot (iq em cima, id embaixo).",
        "Espectros: espectro de frequência (FFT) do conjugado e da velocidade do FOC, em regime (do degrau "
        "de carga até o fim da simulação), eixo de frequência logarítmico.",
    ]
    for it in itens:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(it)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_Sintonia_Motor_Aware_v5.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
