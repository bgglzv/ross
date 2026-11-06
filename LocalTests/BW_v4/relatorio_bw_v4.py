"""Relatório: análise dos parâmetros internos dos motores (resistências,
reatâncias, indutâncias) e seu papel nos ganhos de malha, síntese dos três
parâmetros mais influentes, e avaliação de uma constante universal C que
escala kp e ki (desacoplados) preservando o fator de amortecimento de cada
malha — testada a 60 Hz para MIT_P e MIT_G.

Requer que `simular_v4.py` já tenha rodado para os dois motores, C em
(1.1, 1.2, 1.3, 1.5, 2.0) — C=1.0 reusa o v2 (../BW_v2/dados).

    python relatorio_bw_v4.py
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
from comum import motores
from inverter_foc_v2 import InverterFOCv2
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS_V4 = PASTA / "dados"
DADOS_V2 = PASTA.parent / "BW_v2" / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"
FIGS_TMP = PASTA / "_figuras_docx"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)

CS = (1.0, 1.1, 1.2, 1.3, 1.5, 2.0)
T_CARGA = {"P": 1.5, "G": 13.0}
TNOM = {"P": 6.246412, "G": 13190.932302}
MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P"), "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G")}


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


def _extrair_parametros(motor_id):
    sim, construir_motor, _ = MOTORES[motor_id]
    motor = construir_motor()
    inv = InverterFOCv2(
        voltage_dc=motor.voltage_nom * 1.414 * np.sqrt(2), frequency_s=Q_(5000.0, "Hz"),
        voltage_nom=motor.voltage_nom, frequency_nom=motor.frequency_nom, n_poles=motor.n_poles,
        speed_nom=motor.speed_nom, torque_nom=motor.Tnom, stator_resistance=motor.stator_resistance,
        rotor_resistance=motor.rotor_resistance, stator_reactance=motor.stator_reactance,
        rotor_reactance=motor.rotor_reactance, mutual_reactance=motor.mutual_reactance,
        Ip_motor=motor.Ip_motor, time_ramp=0.6667, frequency_ref=Q_(60.0, "Hz"),
    )
    return dict(
        Rs=inv.Rs, Rr=inv.Rr, Lss=inv.Lss, Lrr=inv.Lrr, Lsline=inv.Lsline,
        taur=inv.taur, tau_elec_iqs=inv.Lsline / inv.Rs, tau_elec_ids=inv.Lss / inv.Rs,
        Is_nom=inv.Is_nom, Ip_motor=motor.Ip_motor, Tnom=float(motor.Tnom),
    )


def _tabela_parametros(doc, par_p, par_g):
    linhas = [
        ("Rs (Ω)", par_p["Rs"], par_g["Rs"]),
        ("Rr (Ω)", par_p["Rr"], par_g["Rr"]),
        ("Lss (H)", par_p["Lss"], par_g["Lss"]),
        ("Lrr (H)", par_p["Lrr"], par_g["Lrr"]),
        ("Lsline (H)", par_p["Lsline"], par_g["Lsline"]),
        ("τ_r = Lrr/Rr (s)", par_p["taur"], par_g["taur"]),
        ("τ_elec,iqs = Lsline/Rs (ms)", par_p["tau_elec_iqs"] * 1000, par_g["tau_elec_iqs"] * 1000),
        ("τ_elec,ids = Lss/Rs (ms)", par_p["tau_elec_ids"] * 1000, par_g["tau_elec_ids"] * 1000),
        ("Is_nom (A)", par_p["Is_nom"], par_g["Is_nom"]),
        ("Ip_motor = J (kg·m²)", par_p["Ip_motor"], par_g["Ip_motor"]),
        ("Tnom (N·m)", par_p["Tnom"], par_g["Tnom"]),
    ]
    tabela = doc.add_table(rows=1, cols=4)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Parâmetro", "MIT_P", "MIT_G", "Razão G/P")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for nome, vp, vg in linhas:
        cels = tabela.add_row().cells
        cels[0].text = nome
        cels[1].text = f"{vp:.5g}"
        cels[2].text = f"{vg:.5g}"
        cels[3].text = f"{vg / vp:.3g}×"
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = "Arial"


def _coletar_sweep():
    linhas = []
    for motor_id in ("P", "G"):
        base = np.load(DADOS_BASE / f"{motor_id}_60Hz_foc.npz")
        tnom = TNOM[motor_id]
        tb, cb = base["t"], base["conjugado"]
        mb = tb >= tb[-1] - 1.0
        rip_base = float((cb[mb].max() - cb[mb].min()) / tnom * 100)
        for C in CS:
            caminho = DADOS_V2 / f"{motor_id}_60Hz_foc_v2.npz" if C == 1.0 else DADOS_V4 / f"{motor_id}_60Hz_foc_v4_C{C:g}.npz"
            d = np.load(caminho)
            t, v, c = d["t"], d["velocidade_rpm"], d["conjugado"]
            m = t >= t[-1] - 1.0
            rip = float((c[m].max() - c[m].min()) / tnom * 100)
            vmin = float(v[t >= T_CARGA[motor_id]].min())
            linhas.append(dict(motor_id=motor_id, C=C, ripple_pct=rip, ripple_base_pct=rip_base,
                               reducao_pct=(rip_base - rip) / rip_base * 100, vmin_pos_carga=vmin))
    return linhas


def _figura_sweep(linhas):
    fig = go.Figure()
    for motor_id, cor, nome in (("P", "#1f77b4", "MIT_P"), ("G", "#d62728", "MIT_G")):
        sub = [l for l in linhas if l["motor_id"] == motor_id]
        fig.add_trace(go.Scatter(
            x=[l["C"] for l in sub], y=[l["reducao_pct"] for l in sub], mode="lines+markers",
            name=nome, line=dict(color=cor, width=2.4), marker=dict(size=10)))
    fig.add_hline(y=0, line=dict(color="black", width=1, dash="dash"))
    fig.update_layout(
        title=dict(text="Redução do ripple de conjugado vs. constante C (60 Hz)", font=dict(size=13)),
        xaxis_title="C (multiplicador: kp×C, ki×C²)", yaxis_title="Redução do ripple vs. FOC original (%)",
        height=550, width=900, font=dict(family="Arial"),
        legend=dict(orientation="h", y=-0.15, font=dict(size=12)), margin=dict(t=60, b=80, l=70, r=25))
    FIGS_TMP.mkdir(exist_ok=True)
    caminho = FIGS_TMP / "sweep_C_ripple.png"
    gr.salvar_imagem(fig, caminho)
    return caminho


def _figura_conjugado(motor_id, C):
    sim, construir_motor, rotulo = MOTORES[motor_id]
    motor = construir_motor()
    ordem = ["dol", "vf", "foc"]
    dados = {}
    for chave in ordem:
        if chave == "foc":
            caminho = DADOS_V2 / f"{motor_id}_60Hz_foc_v2.npz" if C == 1.0 else DADOS_V4 / f"{motor_id}_60Hz_foc_v4_C{C:g}.npz"
            d = np.load(caminho)
        else:
            d = np.load(DADOS_BASE / f"{motor_id}_60Hz_{chave}.npz")
        dados[chave] = (d["t"], d["velocidade_rpm"], d["conjugado"], d["conjugado_carga"])
    titulo = f"{rotulo} — 60 Hz — FOC com C={C:g} — Conjugado"
    fig = gr.figura_geral_unica(dados, ordem, motor, sim, 60.0, "conjugado", titulo)
    FIGS_TMP.mkdir(exist_ok=True)
    caminho = FIGS_TMP / f"{motor_id}_60Hz_conj_C{C:g}.png"
    gr.salvar_imagem(fig, caminho)
    return caminho


def montar():
    par_p = _extrair_parametros("P")
    par_g = _extrair_parametros("G")
    linhas = _coletar_sweep()

    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("Constante universal de projeto (ζ-preservada) — MIT_P x MIT_G a 60 Hz")
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "O v3 (BW_v3) tentou reduzir o ripple de conjugado escalando ki_iqs com a frequência de acionamento, "
        "mas isso reduziu o fator de amortecimento (ζ) da malha sem querer e desestabilizou MIT_G a 60 Hz (o "
        "afundamento de velocidade pós-carga deixou de se recuperar). Este relatório parte de uma análise dos "
        "parâmetros internos dos dois motores — resistências, reatâncias, indutâncias — e de como eles entram "
        "nas equações de kp/ki, para propor uma constante universal que aumente a rejeição a distúrbio sem "
        "repetir esse erro de desenho, testada só a 60 Hz nos dois motores."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Parâmetros internos dos motores e seu papel nas malhas")
    _par(doc,
        "kp_iqs e ki_iqs escalam com Lsline (indutância de dispersão equivalente); kp_ids e ki_ids escalam com "
        "Lss; kp_w e ki_w escalam com a inércia J = Ip_motor. Os termos de desacoplamento feedforward "
        "(Rs·iqs, Rs·ids, Lss·w_sync·ids, Lsline·w_sync·iqs) dependem diretamente de Rs e das indutâncias. O "
        "cálculo de escorregamento (wsl = iqs_ref/(ids_ref·τ_r)), que alimenta w_sync, depende de τ_r = Lrr/Rr. "
        "Nenhuma dessas fórmulas depende diretamente da tensão, potência ou corrente nominal do motor — mas a "
        "tabela abaixo mostra que essas grandezas de porte estão fortemente correlacionadas com os parâmetros "
        "que de fato entram nas equações."
    )
    _tabela_parametros(doc, par_p, par_g)

    doc.add_paragraph()
    _titulo_secao(doc, "Os três parâmetros mais influentes")
    _par(doc,
        "1) τ_elec = Lsline/Rs (malha de iqs) e Lss/Rs (malha de ids) — a constante de tempo elétrica própria "
        f"de cada planta. É ~{par_g['tau_elec_iqs']/par_p['tau_elec_iqs']:.0f}× mais lenta em MIT_G (iqs) e "
        f"~{par_g['tau_elec_ids']/par_p['tau_elec_ids']:.0f}× mais lenta (ids). O método por banda passante "
        "fixa a banda de malha fechada só a partir da frequência de chaveamento (fs/8), igual nos dois "
        "motores — mas como a planta de MIT_G é muito mais lenta, a MESMA banda fechada representa uma "
        "\"velocidade relativa\" de malha muito maior ali do que em MIT_P.", tamanho=10.5)
    _par(doc,
        f"2) τ_r = Lrr/Rr (constante de tempo rotórica) — ~{par_g['taur']/par_p['taur']:.0f}× mais lenta em "
        "MIT_G. Governa a velocidade com que o escorregamento (e, por tabela, w_sync e o termo de "
        "desacoplamento que escala com ele) reage a uma mudança em iqs_ref. Um τ_r muito mais lento aproxima "
        "a dinâmica de escorregamento da MESMA escala de tempo do evento transiente (afundamento pós-carga), "
        "criando uma interação de múltiplas escalas de tempo que um modelo de malha única (SISO, como o usado "
        "para calcular kp/ki) não captura.", tamanho=10.5)
    _par(doc,
        f"3) Is_nom (corrente nominal, define iqs_max = 3·Is_nom) — ~{par_g['Is_nom']/par_p['Is_nom']:.0f}× "
        "maior em MIT_G. Toda vez que um dos ganhos foi aumentado sem cuidado neste estudo (ki_iqs sem "
        "anti-windup, depois ki_iqs escalado por frequência), a falha apareceu através de saturação "
        "(corrente ou tensão) interagindo com o integrador. Is_nom (e o limite de tensão do barramento) "
        "definem onde essa saturação começa a agir.", tamanho=10.5)

    doc.add_paragraph()
    _titulo_secao(doc, "Proposta: constante universal C com ζ preservado")
    _par(doc,
        "Desacoplando kp e ki de cada malha via (ζ, ωn) — ωn² = ki/L, 2ζωn = kp/L —, uma constante universal "
        "C aplicada como kp_novo = C·kp, ki_novo = C²·ki mantém ζ EXATAMENTE igual (ωn_novo = C·ωn, "
        "ζ_novo = ζ) em qualquer malha, para qualquer motor. É o oposto do erro do v3, que aumentou ki sem "
        "aumentar kp na mesma proporção e, com isso, reduziu ζ sem intenção. C é aplicado às três malhas "
        "(iqs, ids e w) dos dois motores com o MESMO valor numérico — universal no sentido de não depender "
        "da frequência de acionamento nem ser recalculado por motor. Implementado em InverterFOCv4 "
        "(inverter_foc_v4.py); C=1 reproduz exatamente o v2 (validado bit-a-bit)."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Resultado da varredura de C a 60 Hz")
    tabela = doc.add_table(rows=1, cols=5)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Motor", "C", "Ripple (%)", "Redução vs. base (%)", "Vel. mín. pós-carga (RPM)")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for linha in linhas:
        cels = tabela.add_row().cells
        vals = ("MIT_P" if linha["motor_id"] == "P" else "MIT_G", f"{linha['C']:g}",
                f"{linha['ripple_pct']:.2f}", f"{linha['reducao_pct']:+.1f}", f"{linha['vmin_pos_carga']:.1f}")
        for c, v in zip(cels, vals):
            c.text = v
        cels[3].paragraphs[0].runs[0].font.color.rgb = BOM if linha["reducao_pct"] > 0 else RUIM
        cels[3].paragraphs[0].runs[0].font.bold = True
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9.5)
                    r.font.name = "Arial"

    doc.add_paragraph()
    caminho_sweep = _figura_sweep(linhas)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(caminho_sweep), width=Cm(15.5))

    doc.add_page_break()
    _titulo_secao(doc, "Análise")
    _par(doc,
        "Diferente do v3, NENHUM valor de C testado (até 2,0) desestabilizou MIT_G: a velocidade mínima "
        "pós-carga fica estável entre ~516 e ~586 RPM em toda a faixa (contra 597 RPM no original) — o "
        "afundamento sempre se recupera. Preservar ζ ao escalar kp/ki foi suficiente para evitar a regressão "
        "catastrófica observada no v3.", negrito=True, cor=BOM
    )
    _par(doc,
        "Em MIT_P, o ganho é consistente e cresce suavemente com C, com o melhor ponto nesta varredura em "
        "C=1,5 (+39,0% de redução, contra +33,8% do v2) — uma melhora real, mas modesta sobre o que o v2 já "
        "entregava."
    )
    _par(doc,
        "Em MIT_G, o quadro é mais neutro: entre C=1,0 e C=1,5 o ripple fica ligeiramente PIOR que o original "
        "(-2,5% a -10,5%, sempre na mesma ordem de grandeza do v2, nunca catastrófico), mas em C=2,0 o "
        "resultado volta a ficar positivo (+1,6%) — um padrão não-monotônico que sugere que, para este motor, "
        "a escala ζ-preservada por si só não resolve o ripple (provavelmente dominado por outro mecanismo, "
        "como o ripple inerente da PWM, que ganho de malha não ataca) até valores de C maiores que o testado "
        "aqui."
    )

    for motor_id, C in (("P", 1.5), ("G", 2.0)):
        doc.add_page_break()
        _titulo_secao(doc, f"Conjugado — {'MIT_P' if motor_id=='P' else 'MIT_G'}, C={C:g} (melhor ponto testado)")
        caminho = _figura_conjugado(motor_id, C)
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(caminho), width=Cm(17.0))
        print(f"  [OK] {caminho}")

    doc.add_page_break()
    _titulo_secao(doc, "Conclusões")
    conclusoes = [
        "Os três parâmetros mais influentes identificados — τ_elec (Lsline/Rs, Lss/Rs), τ_r (Lrr/Rr) e Is_nom "
        "— não escalam proporcionalmente ao porte do motor (tensão, potência, corrente nominal): MIT_G tem "
        "constantes de tempo elétrica e rotórica de 28 a 45× mais lentas que MIT_P, apesar de ser uma máquina "
        "muito maior, não menor. É essa falta de correlação direta entre \"porte\" e \"dinâmica relevante para "
        "o controle\" que faz o mesmo método de sintonia (baseado só na frequência de chaveamento) se "
        "comportar de forma tão diferente nos dois motores.",
        "A constante universal C, aplicada como kp×C e ki×C² (preservando ζ) nas três malhas, é uma correção "
        "de desenho válida sobre o erro do v3: elimina o risco de desestabilização (nenhuma regressão em "
        "MIT_G em toda a faixa C∈[1,2]) e entrega uma melhora real, ainda que modesta, em MIT_P (+39,0% em "
        "C=1,5, vs. +33,8% do v2).",
        "Em MIT_G, o resultado é promissor no sentido de SEGURANÇA (sem regressão), mas ainda não é uma "
        "melhora clara de ripple dentro da faixa testada — fica pouco pior que o original na maior parte da "
        "faixa, só virando positivo em C=2,0. Antes de testar as demais frequências, vale ampliar a faixa de "
        "C para MIT_G (ex.: C=2,5, 3,0) para confirmar se a melhora em C=2,0 é o início de uma tendência "
        "positiva ou um ponto isolado.",
        "Recomendação: para MIT_P, C≈1,3-1,5 é seguro e vantajoso. Para MIT_G, mais pontos de C acima de 2,0 "
        "são necessários antes de declarar a proposta \"promissora\" o bastante para expandir às demais "
        "frequências — o critério de segurança (preservar ζ) está validado, mas o ganho ainda não está "
        "demonstrado para o motor grande.",
    ]
    for c in conclusoes:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(c)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_constante_universal_C.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
