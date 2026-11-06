"""Relatório final: consolida todo o estudo de sintonia dos PIs do FOC por
banda passante — do bug de unidades original até a constante universal C
validada nas 4 frequências, para os dois motores.

Requer que todas as simulações de BW_v4 (varredura de C a 60 Hz e C=4,0 nas
4 frequências) já tenham rodado.

    python relatorio_final.py
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

import graficos as gr

PASTA = Path(__file__).resolve().parent
DADOS_V4 = PASTA / "dados"
DADOS_BASE = PASTA.parent / "VELHARAMPA" / "dados"
FIGS_TMP = PASTA / "_figuras_docx"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)

FREQS = (60.0, 55.0, 45.0, 30.0)
T_CARGA = {"P": 1.5, "G": 13.0}
TNOM = {"P": 6.246412, "G": 13190.932302}
C_FINAL = 4.0


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
    return p


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


def _topico(doc, titulo, fato, inferencia):
    p = doc.add_paragraph()
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(11)
    r.font.name = "Arial"
    r.font.color.rgb = ACCENT
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)

    p2 = doc.add_paragraph()
    r2a = p2.add_run("Fato observado: ")
    r2a.bold = True
    r2a.font.size = Pt(10)
    r2a.font.name = "Arial"
    r2b = p2.add_run(fato)
    r2b.font.size = Pt(10)
    r2b.font.name = "Arial"
    p2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    p3 = doc.add_paragraph()
    r3a = p3.add_run("Inferência: ")
    r3a.bold = True
    r3a.font.size = Pt(10)
    r3a.font.name = "Arial"
    r3a.font.color.rgb = MUTED
    r3b = p3.add_run(inferencia)
    r3b.font.size = Pt(10)
    r3b.font.name = "Arial"
    r3b.font.italic = True
    p3.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _coletar_sweep_60hz():
    Cs = (1.0, 1.1, 1.2, 1.3, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
    linhas = []
    for motor_id in ("P", "G"):
        base = np.load(DADOS_BASE / f"{motor_id}_60Hz_foc.npz")
        tnom = TNOM[motor_id]
        tb, cb = base["t"], base["conjugado"]
        mb = tb >= tb[-1] - 1.0
        rip_base = float((cb[mb].max() - cb[mb].min()) / tnom * 100)
        for C in Cs:
            if C == 1.0:
                caminho = PASTA.parent / "BW_v2" / "dados" / f"{motor_id}_60Hz_foc_v2.npz"
            else:
                caminho = DADOS_V4 / f"{motor_id}_60Hz_foc_v4_C{C:g}.npz"
            if not caminho.exists():
                continue
            d = np.load(caminho)
            t, v, c = d["t"], d["velocidade_rpm"], d["conjugado"]
            m = t >= t[-1] - 1.0
            rip = float((c[m].max() - c[m].min()) / tnom * 100)
            linhas.append(dict(motor_id=motor_id, C=C, ripple_pct=rip,
                               reducao_pct=(rip_base - rip) / rip_base * 100))
    return linhas


def _figura_sweep_completa(linhas):
    fig = go.Figure()
    for motor_id, cor, nome in (("P", "#1f77b4", "MIT_P"), ("G", "#d62728", "MIT_G")):
        sub = sorted([l for l in linhas if l["motor_id"] == motor_id], key=lambda l: l["C"])
        fig.add_trace(go.Scatter(
            x=[l["C"] for l in sub], y=[l["reducao_pct"] for l in sub], mode="lines+markers",
            name=nome, line=dict(color=cor, width=2.4), marker=dict(size=9)))
    fig.add_hline(y=0, line=dict(color="black", width=1, dash="dash"))
    fig.add_vline(x=5.0, line=dict(color="#B02A2A", width=1.5, dash="dot"))
    fig.add_annotation(x=5.0, y=30, text="colapso de MIT_G", showarrow=False, font=dict(size=10, color="#B02A2A"))
    fig.update_layout(
        title=dict(text="Varredura completa de C a 60 Hz — do ponto seguro ao colapso", font=dict(size=13)),
        xaxis_title="C (multiplicador: kp×C, ki×C²)", yaxis_title="Redução do ripple vs. FOC original (%)",
        height=550, width=950, font=dict(family="Arial"),
        legend=dict(orientation="h", y=-0.15, font=dict(size=12)), margin=dict(t=60, b=80, l=70, r=25))
    fig.update_yaxes(range=[-20, 50])
    FIGS_TMP.mkdir(exist_ok=True)
    caminho = FIGS_TMP / "sweep_completo.png"
    gr.salvar_imagem(fig, caminho)
    return caminho


def _tabela_final(doc):
    tabela = doc.add_table(rows=1, cols=5)
    tabela.style = "Light Grid Accent 1"
    for c, nome in zip(tabela.rows[0].cells, ("Motor", "Freq. (Hz)", "Ripple original (%)", f"Ripple C={C_FINAL:g} (%)", "Redução (%)")):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for motor_id in ("P", "G"):
        for freq in FREQS:
            base = np.load(DADOS_BASE / f"{motor_id}_{freq:g}Hz_foc.npz")
            tnom = TNOM[motor_id]
            tb, cb = base["t"], base["conjugado"]
            mb = tb >= tb[-1] - 1.0
            rb = float((cb[mb].max() - cb[mb].min()) / tnom * 100)
            d = np.load(DADOS_V4 / f"{motor_id}_{freq:g}Hz_foc_v4_C{C_FINAL:g}.npz")
            t, c = d["t"], d["conjugado"]
            m = t >= t[-1] - 1.0
            rip = float((c[m].max() - c[m].min()) / tnom * 100)
            red = (rb - rip) / rb * 100
            cels = tabela.add_row().cells
            vals = ("MIT_P" if motor_id == "P" else "MIT_G", f"{freq:g}", f"{rb:.2f}", f"{rip:.2f}", f"{red:+.1f}")
            for c_, v in zip(cels, vals):
                c_.text = v
            anomalia = motor_id == "G" and freq == 55.0
            cels[4].paragraphs[0].runs[0].font.color.rgb = RUIM if (red < 0 or anomalia) else BOM
            cels[4].paragraphs[0].runs[0].font.bold = True
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
    r = titulo.add_run("Sintonia dos PIs do FOC por Banda Passante — Relatório Final")
    r.font.size = Pt(19)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    sub = doc.add_paragraph()
    r = sub.add_run("MIT_P (1,5 hp) x MIT_G (M-C-5283001) — do bug de unidades à constante universal C")
    r.font.size = Pt(12)
    r.font.color.rgb = MUTED
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "Consolidar, de forma objetiva, tudo o que foi avaliado neste estudo sobre a sintonia automática dos "
        "controladores PI do inversor FOC pelo método de banda passante (bandwidth method), aplicada a dois "
        "motores de indução de porte muito diferente (MIT_P, 1,5 hp, e MIT_G, motor industrial de grande "
        "porte), nas frequências de acionamento de 30, 45, 55 e 60 Hz. Cada etapa é reportada como um fato "
        "observado (o que a simulação mostrou) seguido da inferência correspondente (o que se pode concluir "
        "a partir dele)."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Linha do tempo do estudo")
    etapas = [
        "Correção de bug de unidades no ganho do FOC (BW/Hz): a banda dos PIs era calculada a partir de "
        "frequency_s sem converter de rad/s para Hz, inflando todos os ganhos em ~2π. Corrigido na biblioteca "
        "(ross/motors/inverters.py), válido para qualquer motor/frequência daqui em diante.",
        "Correção de bug de fase na rampa do V/F (InverterVF.get_phase_voltages): a integral de fase durante "
        "a rampa de aceleração dobrava a frequência nominal na partida. Corrigido na biblioteca.",
        "Estudo de frequência (VELHARAMPA): com os bugs corrigidos, observado que o ripple de conjugado do "
        "FOC cresce quanto mais a frequência de acionamento se aproxima de 60 Hz, em ambos os motores.",
        "BW_v2 — ki_iqs: identificado que a malha de iqs (corrente de torque) não tem integrador na "
        "biblioteca original (só P + feedforward). Adicionar ki_iqs sem anti-windup piorou o ripple "
        "drasticamente (windup colidindo com saturação de corrente/tensão). Com anti-windup (travando a "
        "integral durante saturação de tensão, mesmo mecanismo já usado na malha de velocidade), o resultado "
        "passou a ser positivo em 7 das 8 combinações motor/frequência testadas.",
        "BW_v3 — ki_iqs dependente da frequência: tentativa de escalar ki_iqs com a razão "
        "frequency_ref/frequency_nom. Melhorou MIT_P, mas desestabilizou MIT_G a 60 Hz — o afundamento de "
        "velocidade pós-carga, que antes se recuperava sozinho, deixou de recuperar. Causa: aumentar ki sem "
        "aumentar kp na mesma proporção reduz o fator de amortecimento (ζ) da malha.",
        "BW_v4 — análise de parâmetros e constante universal C: auditoria dos parâmetros internos dos dois "
        "motores (Rs, Rr, Lls, Llr, Lm, Lsline) e de como entram nas equações de kp/ki. Proposta de uma "
        "constante C, aplicada como kp×C e ki×C² nas três malhas (iqs, ids, w), que preserva ζ por construção "
        "— diferente do erro do v3. Varredura de C de 1,0 a 5,0 a 60 Hz revelou um platô de melhora seguro "
        "até C=4,5 e um colapso abrupto em C=5,0 para MIT_G. C=4,0 foi adotado (boa margem de segurança) e "
        "validado nas 4 frequências para os dois motores.",
    ]
    for i, e in enumerate(etapas, start=1):
        p = doc.add_paragraph(style="List Number")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(e)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    doc.add_page_break()
    _titulo_secao(doc, "Fatos observados e inferências")

    _topico(doc, "1. Ripple de conjugado cresce com a proximidade a 60 Hz",
        "Nos ensaios de 30 a 60 Hz, com os bugs de unidade já corrigidos, o ripple de conjugado do FOC em "
        "regime aumenta conforme a frequência de acionamento se aproxima da nominal, em MIT_P e em MIT_G.",
        "A malha de iqs (corrente de torque) depende de um termo de desacoplamento feedforward "
        "(Lss·w_sync·ids) que escala linearmente com a velocidade síncrona — a 60 Hz esse termo é o dobro do "
        "que é a 30 Hz, então qualquer resíduo de cancelamento imperfeito entra proporcionalmente ampliado.")

    _topico(doc, "2. A malha de iqs não tem integrador na biblioteca original",
        "kp_iqs existe; ki_iqs não existe no InverterFOC original — a malha é só proporcional + feedforward.",
        "Sem integrador, a malha não tem como corrigir o resíduo que o feedforward deixa passar — "
        "consistente com o ripple crescente do fato 1.")

    _topico(doc, "3. ki_iqs sem anti-windup piora o ripple, não melhora",
        "Adicionar ki_iqs (mesmo padrão de banda de ids) sem proteção de anti-windup piorou o ripple em 6 "
        "das 8 combinações motor/frequência testadas, em um caso (MIT_G a 45 Hz) 57× pior.",
        "O integrador novo soma-se a uma malha que já satura com frequência (limite de corrente e de tensão) "
        "durante rampa e degrau de carga; sem trava de anti-windup, ele acumula erro sem parar nesses "
        "trechos e produz um ciclo-limite de oscilação maior que o ripple original.")

    _topico(doc, "4. Anti-windup corrige o problema do fato 3",
        "Com state[\"int_err_iqs\"] travado durante saturação de tensão (mesmo mecanismo já usado na malha "
        "de velocidade), o resultado melhora em 7 das 8 combinações motor/frequência; a melhora é maior em "
        "MIT_P a 60 Hz (+33,8%) e modesta em MIT_G (entre -2,5% e +5,6%).",
        "O mecanismo de anti-windup já validado para a malha de velocidade generaliza para a malha de iqs — "
        "era a peça que faltava para o ki_iqs do fato 2 funcionar como esperado.")

    _topico(doc, "5. Escalar ki_iqs só pela frequência desestabiliza o motor grande",
        "Dobrar ki_iqs ao chegar em 60 Hz (mantendo kp_iqs fixo) melhorou MIT_P, mas em MIT_G o afundamento "
        "de velocidade pós-carga — que no original e no v2 se recupera em ~1,5 s — deixou de se recuperar; "
        "o ripple de conjugado no último segundo foi de 26,2% (v2) para 577,1% (v3).",
        "Aumentar ki sem aumentar kp na mesma proporção reduz o fator de amortecimento (ζ) da malha. Esse "
        "efeito, pequeno em MIT_P, foi suficiente para desestabilizar MIT_G por causa da constante de tempo "
        "rotórica (τ_r) muito mais lenta desse motor (ver fato 7) interagindo com a malha mais rápida.")

    _topico(doc, "6. MIT_G a 55 Hz tem uma instabilidade severa e pré-existente",
        "Tanto o FOC original quanto todas as variantes testadas (v2, v3, v4) mostram, em MIT_G a 55 Hz, a "
        "velocidade do rotor invertendo de sinal (perda de sincronismo) por volta de t≈18 s. Reproduzido de "
        "forma determinística (valores idênticos bit-a-bit) rodando isolado, fora do contexto de execução em "
        "paralelo com outras simulações.",
        "Essa instabilidade não é causada por nenhuma das modificações deste estudo — já existe na "
        "biblioteca original nessa combinação específica de motor e frequência. Deve ser tratada como um "
        "problema separado, não como critério de avaliação das propostas de sintonia.")

    _topico(doc, "7. Os parâmetros internos relevantes não escalam com o porte do motor",
        "τ_elec (Lsline/Rs, Lss/Rs) é 40-45× mais lento em MIT_G; τ_r (Lrr/Rr) é 28× mais lento; Is_nom "
        "(limiar de saturação) é ~100× maior — apesar de MIT_G ser uma máquina de porte muito maior (potência, "
        "tensão, corrente), não menor.",
        "O método de banda passante deriva todos os ganhos só da frequência de chaveamento (fixa, igual nos "
        "dois motores) — não considera essas diferenças de dinâmica interna. A mesma banda fechada representa "
        "uma agressividade relativa muito maior em MIT_G, o que explica por que MIT_G é consistentemente mais "
        "sensível a aumentos de ganho do que MIT_P ao longo de todo o estudo.")

    _topico(doc, "8. Uma constante C que preserva ζ evita o erro do v3",
        "Desacoplando kp e ki via (ζ, ωn) e escalando kp×C, ki×C² nas três malhas (iqs, ids, w), ζ permanece "
        "matematicamente idêntico ao original em qualquer C (validado numericamente). Na varredura de C=1,0 a "
        "C=4,5 a 60 Hz, MIT_G nunca perdeu a capacidade de se recuperar do afundamento pós-carga.",
        "Preservar o fator de amortecimento ao aumentar o ganho é uma condição necessária (embora não "
        "suficiente, ver fato 9) para escalar a sintonia com segurança entre motores de porte diferente.")

    _topico(doc, "9. Existe um penhasco de instabilidade em C=5,0 para MIT_G",
        "MIT_G manteve-se estável e com ripple decrescente de C=1,0 até C=4,5 (melhor ponto: +28,2% de "
        "redução); em C=5,0 a velocidade inverte de sinal (-560 RPM) e o ripple dispara para 1167%. MIT_P "
        "nunca desestabilizou em toda a faixa testada (até C=5,0).",
        "Mesmo preservando ζ, existe um limite de ganho além do qual efeitos não capturados pelo modelo SISO "
        "de cada malha isolada (acoplamento com a dinâmica de escorregamento, discretização, saturação) "
        "dominam e a malha perde estabilidade — e esse limite é específico de MIT_G, não de MIT_P. C=4,0 foi "
        "adotado por dar boa margem de segurança (20% abaixo do colapso observado).")

    _topico(doc, "10. C=4,0 melhora o ripple em quase todas as condições testadas",
        "Nas 4 frequências (30, 45, 55 e 60 Hz) e nos 2 motores, C=4,0 reduziu o ripple de conjugado em 7 das "
        "8 combinações, de +11,6% a +43,8% — a única exceção é MIT_G a 55 Hz, onde a instabilidade "
        "pré-existente do fato 6 se mantém independente do ganho aplicado.",
        "A constante universal C, com ζ preservado, é uma correção de sintonia que generaliza através de "
        "porte de motor e frequência de acionamento — ao contrário do v3, que só funcionava para um dos dois "
        "motores.")

    doc.add_page_break()
    _titulo_secao(doc, "Resultado final: C = 4,0, nas 4 frequências")
    _par(doc,
        "Ripple = (máximo − mínimo) do conjugado bruto no último segundo simulado, dividido pelo conjugado "
        "nominal do motor (Tnom), em %.", tamanho=9, cor=MUTED, italico=True)
    _tabela_final(doc)

    doc.add_paragraph()
    linhas_sweep = _coletar_sweep_60hz()
    caminho_fig = _figura_sweep_completa(linhas_sweep)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(caminho_fig), width=Cm(16.0))

    doc.add_page_break()
    _titulo_secao(doc, "Limitações e próximos passos")
    proximos = [
        "MIT_G a 55 Hz permanece sem solução: é uma instabilidade da biblioteca original, não resolvida por "
        "nenhuma das variantes de sintonia testadas. Requer investigação própria (possivelmente ligada a uma "
        "ressonância entre a dinâmica elétrica de MIT_G e essa frequência específica).",
        "A posição exata do penhasco de instabilidade (entre C=4,5 e C=5,0 para MIT_G) foi localizada por "
        "busca binária grosseira; uma margem de segurança formal (ex.: critério de Nyquist ou análise de "
        "polos em malha fechada incluindo a discretização) daria mais confiança do que só testar pontos.",
        "C=4,0 foi validado nas 4 frequências de referência (30-60 Hz) nominal de carga; não foi testado sob "
        "outras condições de carga, outros motores, ou variações de parâmetros do motor (robustez "
        "paramétrica).",
        "As demais frentes levantadas na primeira avaliação (checar o mapeamento de polos em tempo discreto, "
        "considerar explicitamente a constante de tempo rotórica τ_r no projeto dos ganhos) continuam "
        "disponíveis como extensões, caso se queira ir além do ganho escalar C.",
    ]
    for p_ in proximos:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(p_)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_Final_Sintonia_FOC.docx"
    doc.save(destino)
    print(f"[OK] {destino}")


if __name__ == "__main__":
    montar()
