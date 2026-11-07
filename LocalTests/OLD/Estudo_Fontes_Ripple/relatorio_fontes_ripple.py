"""Estudo: origem do ripple de iq/conjugado e parâmetros (do motor ou do
chaveamento) que poderiam ser inseridos nas equações da malha de controle
para mitigá-lo — partindo de evidência espectral dos dados já simulados
(BW_v5/BW_v6), não de teoria isolada.

    python relatorio_fontes_ripple.py
"""

import sys
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from plotly import graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v2"))

import graficos as gr

PASTA = Path(__file__).resolve().parent
DADOS_V5 = PASTA.parent / "BW_v5" / "dados"
FIGS_TMP = PASTA / "_figuras_docx"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)
AMARELO = RGBColor(0xB8, 0x86, 0x0B)


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


def _topico(doc, titulo, cor_titulo=ACCENT):
    p = doc.add_paragraph()
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.name = "Arial"
    r.font.color.rgb = cor_titulo
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(3)


def _campo(doc, rotulo, texto, cor_rotulo=None):
    p = doc.add_paragraph()
    r1 = p.add_run(f"{rotulo}: ")
    r1.bold = True
    r1.font.size = Pt(10)
    r1.font.name = "Arial"
    if cor_rotulo:
        r1.font.color.rgb = cor_rotulo
    r2 = p.add_run(texto)
    r2.font.size = Pt(10)
    r2.font.name = "Arial"
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _picos_espectro(t, y, t_ini, n=6):
    m = t >= t_ini
    ts, ys = t[m], y[m]
    dt = float(np.median(np.diff(ts)))
    ys = ys - ys.mean()
    n_amostras = len(ys)
    esp = np.abs(np.fft.rfft(ys)) * 2.0 / n_amostras
    freqs = np.fft.rfftfreq(n_amostras, d=dt)
    idx = np.argsort(esp)[-n:][::-1]
    return sorted(((float(freqs[i]), float(esp[i])) for i in idx), key=lambda x: -x[1])


def _figura_espectro_anotada(t, y, t_ini, titulo, eixo_y, marcas):
    fig = go.Figure()
    m = t >= t_ini
    ts, ys = t[m], y[m]
    dt = float(np.median(np.diff(ts)))
    ys_c = ys - ys.mean()
    n = len(ys_c)
    esp = np.abs(np.fft.rfft(ys_c)) * 2.0 / n
    freqs = np.fft.rfftfreq(n, d=dt)
    fig.add_trace(go.Scatter(x=freqs, y=esp, mode="lines", line=dict(color="#d62728", width=1.3)))
    for fx, rotulo, cor in marcas:
        fig.add_vline(x=fx, line=dict(color=cor, width=1.2, dash="dot"))
        fig.add_annotation(x=fx, y=1.0, yref="paper", yanchor="top", text=rotulo,
                           showarrow=False, font=dict(size=9, color=cor), bgcolor="rgba(255,255,255,0.85)")
    fig.update_xaxes(title_text="Frequência (Hz)", type="log", range=[0, np.log10(max(freqs[-1], 10))])
    fig.update_yaxes(title_text=eixo_y)
    fig.update_layout(title=dict(text=titulo, font=dict(size=12)), height=480, width=950,
                      font=dict(family="Arial"), margin=dict(t=60, b=55, l=70, r=20))
    return fig


def montar():
    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("Origem do Ripple de iq/Conjugado e Parâmetros para Mitigá-lo")
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run("Estudo exploratório — motor ou chaveamento, inseridos nas equações da malha de controle")
    r.font.size = Pt(12)
    r.font.color.rgb = MUTED
    doc.add_paragraph()

    _titulo_secao(doc, "Por que este estudo")
    _par(doc,
        "No estudo anterior (BW_v6), tornar K_IQS dependente de frequency_ref — fazendo a banda da malha de "
        "iqs crescer ou cair com a frequência de acionamento — teve efeito quase nulo sobre o ripple de iq "
        "(variações de ±0,2 a ±1,9%, nível de ruído) em toda a faixa de banda testada (63 Hz a 615 Hz). Isso "
        "é evidência de que o ripple de iq não é, neste regime, um problema de banda/ganho de malha — exige "
        "investigar a origem física do ripple antes de propor mais ajustes de PI."
    )

    doc.add_page_break()
    _titulo_secao(doc, "Evidência espectral — onde o ripple de iq realmente está")
    _par(doc,
        "FFT de iq em regime (depois do degrau de carga), dados já simulados do BW_v5 (K_IQS=10 fixo, sem "
        "nenhuma mudança deste estudo). Picos de amplitude, dois motores, duas frequências de acionamento:"
    )

    casos = [
        ("P", 62.0, 1.5), ("P", 30.0, 1.5),
        ("G", 62.0, 13.0), ("G", 30.0, 13.0),
    ]
    tabela = doc.add_table(rows=1, cols=4)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Motor", "Freq. acion. (Hz)", "Pico (Hz)", "Amplitude (A)")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    picos_por_caso = {}
    for motor_id, freq_hz, t_ini in casos:
        d = np.load(DADOS_V5 / f"{motor_id}_{freq_hz:g}Hz_foc_v5.npz")
        picos = _picos_espectro(d["t"], d["iq"], t_ini + 0.5, n=4)
        picos_por_caso[(motor_id, freq_hz)] = (d["t"], d["iq"], t_ini)
        for fx, amp in picos:
            cels = tabela.add_row().cells
            vals = ("MIT_P" if motor_id == "P" else "MIT_G", f"{freq_hz:g}", f"{fx:.1f}", f"{amp:.3f}")
            for c, v in zip(cels, vals):
                c.text = v
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"

    doc.add_paragraph()
    _par(doc,
        "Padrão consistente nos 4 casos: os maiores picos ficam colados em fs ± 3·f1 (bandas laterais de "
        "chaveamento — fs = 5000 Hz é a frequência de chaveamento fixa do estudo, f1 é a frequência "
        "fundamental/síncrona) e em 2·fs ± 3·f1; um pico secundário, bem menor, aparece perto de 6·f1 "
        "(harmônica clássica de conjugado em máquinas trifásicas de 6 pulsos). Em nenhum caso há energia "
        "relevante na faixa de banda testada no BW_v5/v6 (63-615 Hz) — exatamente por isso mexer em K_IQS "
        "não mudou o ripple de iq: a energia dominante está 10-80× mais alto em frequência do que qualquer "
        "banda de malha segura.", negrito=True
    )

    for (motor_id, freq_hz), (t, iq, t_ini) in list(picos_por_caso.items())[:2]:
        f1_aprox = freq_hz
        marcas = [
            (5000.0, "fs", "#555"),
            (5000.0 - 3 * f1_aprox, "fs-3f1", "#d62728"),
            (5000.0 + 3 * f1_aprox, "fs+3f1", "#d62728"),
            (6 * f1_aprox, "6f1", "#1f77b4"),
        ]
        fig = _figura_espectro_anotada(t, iq, t_ini + 0.5,
                                       f"{'MIT_P' if motor_id=='P' else 'MIT_G'} — {freq_hz:g} Hz — espectro de iq (anotado)",
                                       "Amplitude de iq (A)", marcas)
        FIGS_TMP.mkdir(exist_ok=True)
        caminho = FIGS_TMP / f"espectro_{motor_id}_{freq_hz:g}Hz.png"
        gr.salvar_imagem(fig, caminho)
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(caminho), width=Cm(16.5))
        print(f"  [OK] {caminho}")

    doc.add_page_break()
    _titulo_secao(doc, "Leitura do código: o que já existe e o que falta")
    _par(doc,
        "Confirmado em ross/motors/inverters.py e motor_element.py: iqs/ids entram no cálculo do erro "
        "exatamente como medidos, sem nenhum filtro entre a transformada de Park e o regulador PI — a malha "
        "reage à corrente instantânea, inclusive ao ripple de chaveamento presente nela. Não há dead-time "
        "(tempo de interbloqueio) modelado nas chaves do SVPWM. Não há amostragem sincronizada com o centro "
        "do período de chaveamento (a corrente é lida a cada passo de simulação, não numa janela controlada "
        "do ciclo PWM)."
    )

    doc.add_page_break()
    _titulo_secao(doc, "Parâmetros candidatos — catálogo")

    _topico(doc, "A. Oriundos do chaveamento")

    _campo(doc, "A1. Frequência de chaveamento (fs)",
        "Já é parâmetro de simulação (5 kHz neste estudo), mas pode ser tratado explicitamente como variável "
        "de projeto: a teoria clássica de PWM prevê que a amplitude das bandas laterais cai com 1/fs e que "
        "elas se afastam de f1, facilitando a filtragem. Não entra diretamente numa equação de PI, mas é a "
        "alavanca mais direta — e a mais cara (mais chaveamentos = mais perdas no inversor). Efeito esperado: "
        "alto. Risco/custo: aumenta perdas de chaveamento, pode exigir revisão térmica do inversor.")

    _campo(doc, "A2. Filtro (ou amostragem sincronizada) na realimentação de iqs/ids, derivado de Ts=1/fs",
        "Inserir uma média móvel (ou um passa-baixas de 1ª ordem) com janela/constante de tempo amarrada a "
        "Ts antes de calcular err_iqs/err_ids — padrão comum em FOC digital real, onde a corrente é lida no "
        "centro do período de chaveamento (ou com média de meio período) exatamente para não realimentar o "
        "ripple de PWM no regulador. Entra diretamente na equação: err_iqs = iqs_ref - media_movel(iqs, "
        "janela=Ts). Efeito esperado: alto sobre o ripple que o CONTROLADOR reage/amplifica; não reduz o "
        "ripple físico da corrente em si (que é inerente ao chaveamento), mas evita que o PI reaja a ele e "
        "realimente mais ruído na tensão de referência. Risco: atraso de fase adicional (um filtro sempre "
        "atrasa); precisa ser compensado ou mantido pequeno frente à banda de malha.", cor_rotulo=BOM)

    _campo(doc, "A3. Instante de amostragem dentro do período de chaveamento",
        "Amostrar a corrente perto do centro do pulso PWM (onde o ripple triangular cruza perto do valor "
        "médio) em vez de em qualquer instante do período reduz o ripple capturado sem precisar de um filtro "
        "explícito. Não é bem um \"parâmetro numérico\" a inserir numa fórmula, é uma mudança na lógica de "
        "amostragem (`_get_carrier`/`get_current_state`), ligada ao mesmo Ts. Efeito esperado: médio.")

    _topico(doc, "B. Oriundos do motor")

    _campo(doc, "B1. τ_r = Lrr/Rr (constante de tempo rotórica) — precisão da estimativa de escorregamento",
        "Já usado no cálculo de wsl = iqs_ref/(ids_ref·τ_r), que define a velocidade síncrona e o ângulo de "
        "fluxo (theta) usado no desacoplamento d-q. Erro entre o τ_r assumido (valor de placa) e o real "
        "(que muda com temperatura do rotor e saturação) desalinha o referencial d-q do controlador do "
        "referencial real de fluxo do rotor — isso é uma causa clássica de acoplamento cruzado iq/id em FOC "
        "indireto, e explicaria o pico secundário perto de 6·f1 (não ligado ao chaveamento). Não é um "
        "parâmetro NOVO — já está na equação —, mas sua PRECISÃO/robustez é um candidato de melhoria "
        "(ex.: um observador de fluxo rotórico, fora do escopo de só \"inserir um parâmetro\").", cor_rotulo=AMARELO)

    _campo(doc, "B2. Saturação magnética — Lm variável com o nível de fluxo (ids)",
        "O modelo usa Lm constante; a máquina real satura (Lm cai com ids elevado). ids_ref é calculado uma "
        "vez, no ponto nominal — se o ponto de operação real diverge (campo fraco, carga parcial), o Lm "
        "assumido não bate com o real, e o desacoplamento (termos Lss·w_sync·ids, Lsline·w_sync·iqs) fica "
        "impreciso. Inserção: Lm(ids) como função (tabela ou polinômio) em vez de constante, usada nos "
        "termos de desacoplamento. Efeito esperado sobre o ripple de PWM: nenhum (mecanismo físico "
        "diferente). Efeito esperado sobre o componente de 6·f1 / torque médio: possível, não quantificado "
        "aqui.")

    _campo(doc, "B3. Resistência Rs e Rr dependentes de temperatura",
        "Rs/Rr do modelo são fixos; na máquina real crescem com a temperatura de operação (~0,4%/°C para "
        "cobre). Um Rs/Rr desatualizado desalinha os termos de desacoplamento (Rs·iqs, Rs·ids) e o próprio "
        "τ_r (item B1). Mitigação por parâmetro simples: nenhuma — precisaria de estimação online (fora do "
        "escopo de inserir uma constante).")

    doc.add_page_break()
    _titulo_secao(doc, "Recomendação de prioridade para teste")
    recomendacoes = [
        "A2 (filtro/amostragem sincronizada na realimentação, janela ligada a Ts) é o candidato mais direto, "
        "mais barato de testar (não mexe em hardware/fs) e o mais alinhado ao que a evidência espectral "
        "mostra: o problema não é banda de malha, é o controlador reagindo ao ripple que ele mesmo não "
        "consegue (nem deveria tentar) rejeitar por realimentação proporcional/integral. Primeiro candidato "
        "a implementar e testar.",
        "A1 (aumentar fs) é o mais previsível em efeito, mas é uma decisão de hardware/custo fora do escopo "
        "de \"ajustar a malha de controle\" — útil registrar como referência teórica (ripple ∝ 1/fs), não "
        "como próximo passo de implementação.",
        "B1/B2 (precisão de τ_r e Lm) explicam o componente secundário de 6·f1, não o ripple dominante de "
        "chaveamento — relevantes para uma segunda rodada, depois de tratar A2, e exigem mecanismos mais "
        "elaborados (observador) do que uma simples constante na equação.",
    ]
    for rec in recomendacoes:
        p = doc.add_paragraph(style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(rec)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_Fontes_Ripple.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
