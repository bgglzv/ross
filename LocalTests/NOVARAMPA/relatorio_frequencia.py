"""Monta o relatório de um motor (P ou G) numa frequência de referência.

Requer que `simular.py <motor> <freq_hz>` já tenha rodado.

    python relatorio_frequencia.py P 60
    python relatorio_frequencia.py G 30
"""

import sys
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graficos as gr
from comum import motores

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
FIGURAS = PASTA / "figuras"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)

MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}

LARGURA_GERAL_CM = 17.0
LARGURA_ZOOM_CM = 8.4


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


def _carregar(motor_id, freq_hz, cenario):
    d = np.load(DADOS / f"{motor_id}_{freq_hz:g}Hz_{cenario}.npz")
    return d["t"], d["velocidade_rpm"], d["conjugado"]


def _ordem(freq_hz):
    return ["dol", "vf", "foc"] if abs(freq_hz - 60.0) < 1e-9 else ["vf", "foc"]


def _titulo_secao(doc, texto):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = ACCENT
    p.paragraph_format.space_after = Pt(8)
    return p


def _tabela(doc, linhas):
    tabela = doc.add_table(rows=0, cols=2)
    tabela.style = "Light Grid Accent 1"
    for chave, valor in linhas:
        cels = tabela.add_row().cells
        cels[0].text, cels[1].text = chave, valor
        cels[0].paragraphs[0].runs[0].font.bold = True
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)
                    r.font.name = "Arial"
    return tabela


def _pagina_1(doc, motor_id, freq_hz, motor, sim, ordem):
    nominal = abs(freq_hz - 60.0) < 1e-9
    rotulo_motor = MOTORES[motor_id][2]

    titulo = doc.add_paragraph()
    r = titulo.add_run(f"Resposta dinâmica sob degrau de carga — {rotulo_motor}")
    r.font.size = Pt(20)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run(f"Referência de frequência: {freq_hz:g} Hz")
    r.font.size = Pt(13)
    r.font.color.rgb = MUTED
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo do ensaio")
    if nominal:
        acionamentos = "partida direta (ligação à rede), acionamento escalar V/F em malha aberta e acionamento vetorial FOC em malha fechada"
    else:
        acionamentos = "acionamento escalar V/F em malha aberta e acionamento vetorial FOC em malha fechada (a partida direta não admite referência de frequência reduzida, por ligar o motor direto à rede)"
    doc.add_paragraph(
        f"Este relatório avalia o comportamento dinâmico do {rotulo_motor.split(' — ')[1]} quando levado à "
        f"referência de {freq_hz:g} Hz e, em seguida, submetido a um degrau de carga nominal já em regime "
        f"permanente. São comparados: {acionamentos}."
    )
    doc.add_paragraph(
        "As grandezas acompanhadas são a velocidade do rotor e o conjugado eletromagnético, no domínio do "
        "tempo, sobre o sinal bruto medido (sem filtragem). São marcados os pontos de máximo alcançados na "
        "partida e na entrada da carga e, nas figuras de detalhe, o sobressinal e o tempo de subida (10-90%) "
        "de cada acionamento."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Dados do ensaio")
    linhas = [
        ("Motor", rotulo_motor),
        ("Potência nominal", f"{motor.power_nom:.4g} W" if hasattr(motor, "power_nom") else "—"),
        ("Tensão nominal (fase)", f"{float(motor.voltage_nom):.1f} V"),
        ("Frequência nominal", "60 Hz"),
        ("Frequência de referência deste ensaio", f"{freq_hz:g} Hz"),
        ("Polos", "4"),
        ("Velocidade nominal", f"{float(motor.speed_nom) * 60 / (2 * np.pi):.0f} RPM"),
        ("Inércia do rotor", f"{float(motor.Ip_motor):.4g} kg·m²"),
        ("Frequência de chaveamento do inversor", f"{sim.frequencia_chaveamento.to('Hz').magnitude:.0f} Hz"),
        ("Rampa de aceleração", f"{sim.rampa:.4g} s"),
        ("Instante de aplicação da carga nominal", f"{sim.t_carga:g} s"),
        ("Tempo total de simulação", f"{sim.tf:g} s"),
        ("Passo interno de simulação", "1 × 10⁻⁶ s (200 amostras por período de chaveamento)"),
        ("Acionamentos comparados", ", ".join(gr.NOMES[c] for c in ordem)),
    ]
    _tabela(doc, [(k, v.replace(".", ",") if isinstance(v, str) else v) for k, v in linhas])


def montar(motor_id, freq_hz):
    sim, construir_motor, rotulo_motor = MOTORES[motor_id]
    motor = construir_motor()
    ordem = _ordem(freq_hz)
    dados = {c: _carregar(motor_id, freq_hz, c) for c in ordem}
    FIGURAS.mkdir(exist_ok=True)
    prefixo = f"{motor_id}_{freq_hz:g}Hz"

    doc = Document()
    _configurar_pagina(doc)
    _pagina_1(doc, motor_id, freq_hz, motor, sim, ordem)

    doc.add_page_break()
    _titulo_secao(doc, "Visão geral — velocidade e conjugado")
    fig = gr.figura_geral(dados, ordem, motor, sim,
                          f"{rotulo_motor} — {freq_hz:g} Hz — visão completa")
    caminho = FIGURAS / f"{prefixo}_geral.png"
    fig.write_image(str(caminho), scale=2)
    fig.write_html(str(caminho.with_suffix(".html")))
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(caminho), width=Cm(LARGURA_GERAL_CM))
    print(f"  [OK] {caminho}")

    for evento_idx, (secao, momento) in enumerate((
        ("Detalhe — entrada em velocidade nominal", "partida"),
        ("Detalhe — entrada da carga", "carga"),
    )):
        doc.add_page_break()
        _titulo_secao(doc, secao)
        janela_apertada, janela_larga = gr.janelas(dados, ordem, motor, sim, evento_idx)

        fig1 = gr.figura_zoom_pico(dados, ordem, motor, sim, evento_idx, janela_apertada,
                                   f"Sobressinal de todos os acionamentos — {momento}")
        c1 = FIGURAS / f"{prefixo}_{momento}_pico.png"
        fig1.write_image(str(c1), scale=2)
        fig1.write_html(str(c1.with_suffix(".html")))
        print(f"  [OK] {c1}")

        fig2 = gr.figura_zoom_foc(dados, motor, sim, evento_idx, janela_larga,
                                  f"V/F x FOC (anotado) — {momento}")
        c2 = FIGURAS / f"{prefixo}_{momento}_foc.png"
        fig2.write_image(str(c2), scale=2)
        fig2.write_html(str(c2.with_suffix(".html")))
        print(f"  [OK] {c2}")

        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(c1), width=Cm(LARGURA_ZOOM_CM))
        par.add_run("  ")
        par.add_run().add_picture(str(c2), width=Cm(LARGURA_ZOOM_CM))

    destino = PASTA / f"Relatorio_{prefixo}.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar(sys.argv[1], float(sys.argv[2]))
