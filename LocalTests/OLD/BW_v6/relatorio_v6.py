"""Relatório final do BW_v6: formulação completa dos ganhos de malha
(herdados do BW_v5) + filtro síncrono de iqs/ids, e tabela comparativa de
ripple% (base = média nos últimos 2 s) entre as versões BW_s v2, v3, v4,
v5 e v6, para Id, Iq, Torque e Velocidade, nos dois motores, nas 5
frequências (30, 45, 55, 60, 62 Hz).

Requer que todas as simulações de v2 (BW_v2), v3 (BW_v3), v4 (BW_v4,
C=4.0), v5 (BW_v5) e v6 (BW_v6) já tenham rodado nas 5 frequências, com
iq/id salvos.

    python relatorio_v6.py
"""

import sys
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from plotly import graph_objects as go

import graficos as gr_plot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v5"))

from comum import motores
from inverter_foc_v5 import InverterFOCv5
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
FIGS_TMP = PASTA / "_figuras_docx"

DADOS = {
    "v2": PASTA.parent / "BW_v2" / "dados",
    "v3": PASTA.parent / "BW_v3" / "dados",
    "v4": PASTA.parent / "BW_v4" / "dados",
    "v5": PASTA.parent / "BW_v5" / "dados",
    "v6": PASTA / "dados",
}
SUFIXO = {
    "v2": "foc_v2", "v3": "foc_v3", "v4": "foc_v4_C4", "v5": "foc_v5", "v6": "foc_v6",
}
NOME_VERSAO = {
    "v2": "v2 (ki_iqs + anti-windup)", "v3": "v3 (ki_iqs(freq), quebrado em G@60Hz)",
    "v4": "v4 (C=4,0 empírico)", "v5": "v5 (motor-aware, base do v6)",
    "v6": "v6 (motor-aware + filtro sincrono, janela motor-aware)",
}

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)

FREQS = (30.0, 45.0, 55.0, 60.0, 62.0)
MOTORES = {"P": (motores.SIM_PEQUENO, motores.motor_pequeno, "MIT_P — motor de pequeno porte (1,5 hp)"),
          "G": (motores.SIM_GRANDE, motores.motor_grande, "MIT_G — motor de grande porte (M-C-5283001)")}


def _configurar_pagina(doc):
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(1.5)
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


def _carregar(versao, motor_id, freq_hz):
    caminho = DADOS[versao] / f"{motor_id}_{freq_hz:g}Hz_{SUFIXO[versao]}.npz"
    d = np.load(caminho)
    return d


def _ripple_pct(sinal, t, janela=2.0):
    m = t >= t[-1] - janela
    s = sinal[m]
    media = np.mean(s)
    if abs(media) < 1e-9:
        return float("nan")
    return float((s.max() - s.min()) / abs(media) * 100.0)


def _coletar_ripple(versao, motor_id, freq_hz):
    d = _carregar(versao, motor_id, freq_hz)
    t = d["t"]
    out = {}
    out["velocidade"] = _ripple_pct(d["velocidade_rpm"], t)
    out["torque"] = _ripple_pct(d["conjugado"], t)
    if "iq" in d and "id" in d:
        out["iq"] = _ripple_pct(d["iq"], t)
        out["id"] = _ripple_pct(d["id"], t)
    else:
        out["iq"] = out["id"] = float("nan")
    return out


def _tabela_grandeza(doc, grandeza, titulo_grandeza):
    _titulo_secao(doc, f"Ripple de {titulo_grandeza} (%) — últimos 2 s", tamanho=12)
    tabela = doc.add_table(rows=1, cols=7)
    tabela.style = "Light Grid Accent 1"
    cab = ("Motor", "Freq (Hz)", "v2", "v3", "v4", "v5", "v6")
    for c, nome in zip(tabela.rows[0].cells, cab):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for motor_id in ("P", "G"):
        for freq in FREQS:
            valores = {}
            for versao in ("v2", "v3", "v4", "v5", "v6"):
                try:
                    r = _coletar_ripple(versao, motor_id, freq)
                    valores[versao] = r[grandeza]
                except FileNotFoundError:
                    valores[versao] = float("nan")
            cels = tabela.add_row().cells
            cels[0].text = "MIT_P" if motor_id == "P" else "MIT_G"
            cels[1].text = f"{freq:g}"
            melhor = None
            vals_validos = {k: v for k, v in valores.items() if not np.isnan(v)}
            if vals_validos:
                melhor = min(vals_validos, key=vals_validos.get)
            for i, versao in enumerate(("v2", "v3", "v4", "v5", "v6"), start=2):
                v = valores[versao]
                cels[i].text = "—" if np.isnan(v) else f"{v:.2f}"
                if versao == melhor:
                    cels[i].paragraphs[0].runs[0].font.color.rgb = BOM
                    cels[i].paragraphs[0].runs[0].font.bold = True
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"
    doc.add_paragraph()


def _extrair_v5(motor_id):
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


def _figura_espectro_comparativo(motor_id, freq_hz, titulo):
    d5 = _carregar("v5", motor_id, freq_hz)
    d6 = _carregar("v6", motor_id, freq_hz)
    t_carga = 1.5 if motor_id == "P" else 13.0
    fig = go.Figure()
    for nome, d, cor in (("v5 (sem filtro)", d5, "#1f77b4"), ("v6 (filtro síncrono)", d6, "#d62728")):
        t, iq = d["t"], d["iq"]
        m = t >= t_carga + 0.5
        ts, ys = t[m], iq[m]
        dt = float(np.median(np.diff(ts)))
        ys_c = ys - ys.mean()
        n = len(ys_c)
        esp = np.abs(np.fft.rfft(ys_c)) * 2.0 / n
        freqs = np.fft.rfftfreq(n, d=dt)
        fig.add_trace(go.Scatter(x=freqs, y=esp, mode="lines", name=nome, line=dict(color=cor, width=1.2)))
    fig.add_vline(x=2500.0, line=dict(color="#555", width=1.2, dash="dot"))
    fig.add_annotation(x=2500.0, y=1.0, yref="paper", yanchor="top", text="fs/2",
                       showarrow=False, font=dict(size=9, color="#555"))
    fig.update_xaxes(title_text="Frequência (Hz)", type="log", range=[0, 4.1])
    fig.update_yaxes(title_text="Amplitude de iq (A)")
    fig.update_layout(title=dict(text=titulo, font=dict(size=12)), height=480, width=950,
                      font=dict(family="Arial"), legend=dict(orientation="h", y=-0.18),
                      margin=dict(t=60, b=70, l=70, r=20))
    FIGS_TMP.mkdir(exist_ok=True)
    caminho = FIGS_TMP / f"espectro_comp_{motor_id}_{freq_hz:g}Hz.png"
    gr_plot.salvar_imagem(fig, caminho)
    return caminho


def montar():
    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("BW_v6 — Filtro Síncrono de iqs/ids: Formulação e Comparativo v2–v6")
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "Detalhar os cálculos de ajuste de malha usados no BW_v6 — os mesmos ganhos motor-aware do BW_v5 "
        "(herdados sem alteração) mais um filtro síncrono na realimentação de iqs/ids — e comparar o ripple "
        "percentual (em relação à média do próprio sinal nos últimos 2 s de simulação) entre as cinco "
        "variantes do estudo (v2, v3, v4, v5, v6), para corrente id, corrente iq, conjugado e velocidade, "
        "nos dois motores, em 30, 45, 55, 60 e 62 Hz."
    )

    doc.add_page_break()
    _titulo_secao(doc, "1) Ganhos de malha (herdados do BW_v5, sem alteração no BW_v6)")
    _par(doc, "Malha de iqs — banda casada com o polo elétrico da própria planta "
             "(polo_iqs = Rs/(2π·Lsline)), com piso por média geométrica em relação ao teto do método "
             "original (fs/8):")
    _formula(doc, "BWp_iqs_teto = min(K_IQS · polo_iqs, fs/8)          [K_IQS = 10]")
    _formula(doc, "BWp_iqs = sqrt(BWp_iqs_teto · fs/8)")
    _formula(doc, "BWi_iqs = BWp_iqs / 8                                [preserva ζ_iqs = √2]")
    _formula(doc, "kp_iqs = 2π·Lsline·BWp_iqs")
    _formula(doc, "ki_iqs = Lsline·4π²·BWp_iqs·BWi_iqs")
    _par(doc, "Malha de ids — mesma lógica, com o polo elétrico próprio de ids (Lss no lugar de Lsline) e "
             "ζ_ids = 1 (BWi_ids = BWp_ids, igual ao método original):")
    _formula(doc, "polo_ids = Rs / (2π·Lss)")
    _formula(doc, "BWp_ids_teto = min(K_IDS · polo_ids, fs/8)          [K_IDS = 10]")
    _formula(doc, "BWp_ids = sqrt(BWp_ids_teto · fs/8)")
    _formula(doc, "BWi_ids = BWp_ids")
    _formula(doc, "kp_ids = Lss·2π·(BWp_ids + BWi_ids)")
    _formula(doc, "ki_ids = Lss·4π²·BWp_ids·BWi_ids")
    _par(doc,
        "Malha de w (velocidade) e anti-windup de iqs: idênticos à biblioteca original / BW_v2, sem "
        "nenhuma mudança em nenhuma das versões v4-v6 (só kp_iqs/ki_iqs/kp_ids/ki_ids mudam entre elas)."
    )

    doc.add_page_break()
    _titulo_secao(doc, "2) O que o BW_v6 adiciona: filtro síncrono com janela motor-aware")
    _par(doc,
        "Motivado pela análise espectral do ripple de iq (Estudo_Fontes_Ripple/Relatorio_Fontes_Ripple.docx): "
        "o ripple de iq está concentrado em bandas laterais de chaveamento (fs±3·f1, 2·fs±3·f1) — muito acima "
        "de qualquer banda de malha seguramente ajustável. A malha original calcula o erro a partir da "
        "corrente medida INSTANTÂNEA, que já carrega esse ripple; o PI reage a ele a cada passo."
    )
    _par(doc,
        "O BW_v6 insere uma média móvel de iqs e ids antes do erro do PI e dos termos de desacoplamento "
        "feedforward (Rs·iqs, Rs·ids, Lss·w_sync·ids, Lsline·w_sync·iqs) — não só no erro, para não misturar "
        "medição filtrada e crua na mesma equação. Esse tipo de filtro (\"boxcar\", média sobre uma janela "
        "T_filt) tem nulos exatos em 1/T_filt, 2/T_filt... — quando T_filt = Ts (um período de chaveamento "
        "inteiro), os nulos caem exatamente em fs, 2fs, atacando as bandas laterais identificadas na análise "
        "espectral. kp_iqs, ki_iqs, kp_ids, ki_ids permanecem exatamente os do BW_v5 em qualquer versão do "
        "filtro abaixo."
    )

    _par(doc, "Regra geral proposta — janela do filtro ligada à banda de malha de cada motor:", negrito=True)
    _formula(doc, "T_filt = min( Ts , THETA_MAX / (pi * BWp_iqs) )")
    _par(doc,
        "Ts = 1/fs é o teto (nunca maior que um período de chaveamento). BWp_iqs é a banda de malha fechada "
        "de iqs que o BW_v5 já calcula para aquele motor (motor-aware, vem do polo elétrico da própria "
        "planta). THETA_MAX é a única constante nova — um orçamento de atraso de fase (rad) que a malha mais "
        "rápida tolera na sua própria frequência de cruzamento: o atraso de grupo de um filtro boxcar de "
        "janela T é π·f·T (rad) na frequência f; orçar THETA_MAX na frequência BWp_iqs dá a fórmula acima. A "
        "MESMA janela T_filt é usada para o buffer de iqs e para o de ids (ver por quê, abaixo)."
    )

    _titulo_secao(doc, "2.1) Como se chegou a essa regra (duas tentativas anteriores)", tamanho=11)
    _par(doc,
        "1ª tentativa — janela fixa (T_filt = Ts, igual nos dois motores): melhorou MIT_G a 55-62 Hz, mas "
        "piorou MIT_P em toda a faixa (30-62 Hz) — o espectro de iq de MIT_P passou a ter um pico dominante "
        "NOVO perto de fs/2 = 2500 Hz, uma auto-oscilação sub-harmônica ausente sem o filtro."
    )
    _par(doc,
        "2ª tentativa — janela independente por malha (T_filt_iqs de BWp_iqs, T_filt_ids de BWp_ids, cada "
        "uma com seu próprio orçamento de fase): para MIT_P isso deu n_iqs≈105 amostras e n_ids=200 (a banda "
        "de ids, mais baixa, \"tolerava\" o atraso cheio). RESULTADO: a ressonância em fs/2 persistiu quase "
        "inalterada. Um teste isolado, variando n_iqs e n_ids separadamente, mostrou a causa real: a "
        "ressonância aparece sempre que o buffer de IDS fica perto do período cheio, independente do "
        "tamanho do buffer de iqs. Faz sentido na equação de vqs_ref (saída da malha rápida de iqs): ela "
        "carrega o termo Lss·w_sync·ids — um ids atrasado entra como distúrbio atrasado DENTRO da malha "
        "rápida, mesmo que a malha de ids isolada (mais lenta) não tivesse problema com esse atraso."
    )
    _par(doc,
        "Daí a regra final: as duas janelas (iqs e ids) compartilham o MESMO valor, dimensionado pela banda "
        "da malha MAIS RÁPIDA (BWp_iqs, sempre ≥ BWp_ids nos dois motores por construção do BW_v5) — isso "
        "evita que um atraso grande em QUALQUER um dos dois buffers vaze, via o termo de acoplamento "
        "cruzado, para dentro da malha mais exigente."
    )

    _titulo_secao(doc, "2.2) Calibração de THETA_MAX e resultado da janela por motor", tamanho=11)
    tabela_theta = doc.add_table(rows=1, cols=4)
    tabela_theta.style = "Light Grid Accent 1"
    for c, nome in zip(tabela_theta.rows[0].cells, ("THETA_MAX (rad)", "n (amostras) MIT_P", "ripple iq MIT_P (%)", "observação")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    linhas_theta = [
        ("0,2 (1ª correção)", "105", "66,0", "já em degradação — perto do limiar"),
        ("0,2 (buffer único p/ ids=200)", "105 / 200", "618,6", "ressonância intacta (causa: buffer de ids)"),
        ("0,05 (regra final)", "26", "43,0", "seguro — igual ao original sem filtro"),
    ]
    for a, b, c_, d in linhas_theta:
        cels = tabela_theta.add_row().cells
        for cel, v in zip(cels, (a, b, c_, d)):
            cel.text = v
    for row in tabela_theta.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"
    doc.add_paragraph()
    _par(doc,
        "THETA_MAX = 0,05 rad (~2,9°) foi validado por varredura direta do tamanho da janela em MIT_P a "
        "60 Hz: ripple de iq fica estável (~43-46%, igual ao original) para janelas de 15 a 70 amostras, "
        "começa a degradar em 105 (66%) e sofre um salto brusco entre 150-200 amostras (570-618%) — THETA_MAX "
        "= 0,05 (que dá n≈26 para MIT_P) fica com boa margem de segurança abaixo desse limiar.",
        tamanho=9.5, cor=MUTED
    )
    _par(doc,
        "Resultado da regra final, por motor: MIT_P fica com janela de ~26 amostras (de 200) — dentro da "
        "faixa seguramente testada; MIT_G fica com janela de ~177 amostras (de 200) — ainda muito perto do "
        "período cheio, porque sua banda de malha (BWp_iqs≈90 Hz) é baixa o bastante para tolerar quase todo "
        "o atraso sem ressoar. A regra, portanto, se auto-ajusta: encolhe bastante onde precisa (MIT_P) e "
        "quase não encolhe onde não precisa (MIT_G)."
    )

    doc.add_page_break()
    _titulo_secao(doc, "3) Comparativo de ripple — v2 a v6")
    _par(doc,
        "Ripple = (máximo − mínimo) do sinal bruto nos últimos 2 s de simulação, dividido pela MÉDIA do "
        "próprio sinal nesse mesmo intervalo (não pelo valor nominal do motor), em %. Melhor valor de cada "
        "linha destacado em verde. \"—\" indica combinação não disponível (ex.: v3 não tem dado a 62 Hz).",
        tamanho=9, cor=MUTED, italico=True)

    for grandeza, titulo_grandeza in (("id", "Id"), ("iq", "Iq"), ("torque", "Torque"), ("velocidade", "Velocidade")):
        _tabela_grandeza(doc, grandeza, titulo_grandeza)

    doc.add_page_break()
    _titulo_secao(doc, "4) Análise — a janela motor-aware resolve MIT_P e preserva o ganho em MIT_G")
    _par(doc,
        "Com a janela compartilhada ligada a BWp_iqs (THETA_MAX=0,05), MIT_P deixa de apresentar a "
        "ressonância em fs/2: os números voltam a ficar próximos do v5 em todas as frequências, com pequenas "
        "diferenças para os dois lados (nunca o salto de centenas de % visto na primeira tentativa) — "
        "30-55 Hz fica 2-7 pontos percentuais pior que o v5 em id/iq (ex.: iq 30 Hz: 21,9%→29,5%), mas "
        "60-62 Hz fica até um pouco MELHOR em torque e velocidade (torque: 217,5%→211,0%; velocidade: "
        "0,37%→0,33%). No conjunto, é um resultado neutro para MIT_P — nem ganho nem perda relevante — bem "
        "diferente da piora severa e uniforme da primeira tentativa.",
        negrito=True, cor=BOM)

    _par(doc,
        "Em MIT_G, o ganho da primeira tentativa se mantém quase intacto: a 55 Hz, id cai de 8,7% (v5) para "
        "6,9% (v6) e torque de 8,5% para 6,8%; a 60-62 Hz, id cai de 16,0% para 10,2% e torque de 15,9% para "
        "10,3% — reduções de 20-35%, muito próximas das já obtidas com a janela de período cheio original "
        "(a diferença entre janela de 177 e 200 amostras, aqui, é marginal). A 30-45 Hz o resultado é neutro "
        "nos dois casos. Ou seja: a regra geral entrega o melhor dos dois mundos — resolve o problema que a "
        "primeira versão causou em MIT_P, sem abrir mão do ganho real que já existia em MIT_G."
    )

    for motor_id, freq_hz in (("P", 60.0), ("G", 60.0)):
        caminho = _figura_espectro_comparativo(
            motor_id, freq_hz,
            f"{'MIT_P' if motor_id=='P' else 'MIT_G'} — 60 Hz — espectro de iq: v5 x v6 (janela motor-aware)")
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(caminho), width=Cm(16.0))
        print(f"  [OK] {caminho}")

    doc.add_page_break()
    _titulo_secao(doc, "5) Conclusões e recomendação")
    conclusoes = [
        "A regra geral T_filt = min(Ts, THETA_MAX/(π·BWp_iqs)), com a MESMA janela usada para os buffers de "
        "iqs e de ids, resolve a auto-oscilação em fs/2 que a primeira versão (janela fixa de um período de "
        "chaveamento) causava em MIT_P, sem desfazer o ganho de ripple já obtido em MIT_G a 55-62 Hz.",
        "A causa da ressonância não estava na janela de iqs isoladamente, e sim no atraso do buffer de IDS "
        "vazando para dentro da malha mais rápida (iqs) através do termo de acoplamento cruzado "
        "Lss·w_sync·ids em vqs_ref — por isso a correção certa é uma janela COMPARTILHADA, dimensionada pela "
        "malha mais exigente (BWp_iqs), não duas janelas independentes por banda própria.",
        "A regra é genuinamente motor-aware e não precisou de nenhuma constante por motor: o mesmo "
        "THETA_MAX=0,05 (único valor novo, calibrado uma vez por varredura em MIT_P) produz janelas "
        "adequadas nos dois motores — ~26 amostras em MIT_P (banda de malha alta, precisa de janela curta) "
        "e ~177 em MIT_G (banda baixa, tolera janela quase cheia) — sem precisar reajustar nada ao trocar "
        "de máquina.",
        "Recomendado adotar o BW_v6 (regra final, THETA_MAX=0,05) para os dois motores: neutro em MIT_P, "
        "melhoria real (20-35% de redução de ripple de id/torque) em MIT_G nas frequências 55-62 Hz.",
    ]
    for c in conclusoes:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(c)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_BW6_Comparativo.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
