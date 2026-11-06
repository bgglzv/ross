"""Relatório comparativo: efeito de desacoplar ki_iqs de kp_iqs e escaloná-lo
pela frequência de acionamento (InverterFOCv3), sobre o ripple de conjugado
em regime, nas 4 frequências testadas (30, 45, 55 e 60 Hz), para MIT_P e
MIT_G — contra a biblioteca original e contra o v2 (ki_iqs fixo +
anti-windup).

Requer que `simular_v3.py` já tenha rodado para os dois motores nas 4
frequências (usa também os dados do FOC original em `../VELHARAMPA/dados`
e do v2 em `../BW_v2/dados`).

    python relatorio_bw_v3.py
"""

import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graficos as gr
from comum import motores
from gerar_figuras_v3 import MOTORES, _carregar_base, _carregar_foc_v3, _ordem
from ripple import FREQS, coletar

PASTA = Path(__file__).resolve().parent
FIGS_TMP = PASTA / "_figuras_docx"

ACCENT = RGBColor(0x0E, 0x5C, 0x68)
MUTED = RGBColor(0x5B, 0x66, 0x72)
BOM = RGBColor(0x1B, 0x7A, 0x3D)
RUIM = RGBColor(0xB0, 0x2A, 0x2A)


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


def _tabela_ripple(doc, df):
    tabela = doc.add_table(rows=1, cols=7)
    tabela.style = "Light Grid Accent 1"
    cab = ("Motor", "Freq (Hz)", "Base (%)", "v2 (%)", "v3 (%)", "Red. v3 vs base (%)", "Red. v3 vs v2 (%)")
    for c, nome in zip(tabela.rows[0].cells, cab):
        c.text = nome
        c.paragraphs[0].runs[0].font.bold = True
    for _, row in df.sort_values(["motor_id", "freq_hz"], ascending=[True, False]).iterrows():
        cels = tabela.add_row().cells
        vals = (
            "MIT_P" if row.motor_id == "P" else "MIT_G",
            f"{row.freq_hz:g}",
            f"{row.ripple_base_pct:.2f}",
            f"{row.ripple_v2_pct:.2f}",
            f"{row.ripple_v3_pct:.2f}",
            f"{row.reducao_v3_pct:+.1f}",
            f"{row.reducao_v3_vs_v2_pct:+.1f}",
        )
        for c, v in zip(cels, vals):
            c.text = v
        cor = BOM if row.reducao_v3_vs_v2_pct > 0 else RUIM
        cels[6].paragraphs[0].runs[0].font.color.rgb = cor
        cels[6].paragraphs[0].runs[0].font.bold = True
    for row in tabela.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(9)
                    r.font.name = "Arial"


def _figura_grandeza(motor_id, freq_hz, grandeza):
    sim, construir_motor, rotulo_motor = MOTORES[motor_id]
    motor = construir_motor()
    ordem = _ordem(freq_hz)
    dados = {}
    for c in ordem:
        dados[c] = _carregar_foc_v3(motor_id, freq_hz) if c == "foc" else _carregar_base(motor_id, freq_hz, c)
    nome_grandeza = "Velocidade" if grandeza == "velocidade" else "Conjugado"
    titulo = f"{rotulo_motor} — {freq_hz:g} Hz — FOC com ki_iqs(freq) — {nome_grandeza}"
    # Janela completa (sem o corte automático do afundamento): neste relatório
    # o ponto é justamente mostrar quando o afundamento NÃO se recupera
    # (MIT_G a 60 Hz com v3) — cortar escondia exatamente essa instabilidade.
    fig = gr.figura_geral_unica(dados, ordem, motor, sim, freq_hz, grandeza, titulo, forcar_fim_visivel=sim.tf)
    FIGS_TMP.mkdir(exist_ok=True)
    sigla = "rpm" if grandeza == "velocidade" else "conj"
    caminho = FIGS_TMP / f"{motor_id}_{freq_hz:g}Hz_{sigla}.png"
    gr.salvar_imagem(fig, caminho)
    return caminho


def _figura_conjugado(motor_id, freq_hz):
    return _figura_grandeza(motor_id, freq_hz, "conjugado")


def montar():
    df = coletar()

    doc = Document()
    _configurar_pagina(doc)

    titulo = doc.add_paragraph()
    r = titulo.add_run("ki_iqs desacoplado e dependente da frequência — MIT_P x MIT_G")
    r.font.size = Pt(19)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    doc.add_paragraph()

    _titulo_secao(doc, "Objetivo")
    _par(doc,
        "A versão anterior (BW_v2) incluiu ki_iqs com o mesmo padrão de banda já usado em ids (BWi_iqs = "
        "BWp_iqs/8, fixo) e anti-windup. O resultado melhorou o ripple de conjugado em 7 das 8 combinações "
        "motor/frequência, mas de forma desigual: em MIT_P a melhora foi maior justamente a 60 Hz (+33,8%) e "
        "menor nas frequências mais baixas; em MIT_G o efeito ficou pequeno (entre -2,5% e +5,6%) em todas as "
        "frequências válidas. Isso é consistente com a causa identificada: o termo de desacoplamento "
        "feedforward (Lss·w_sync·ids) escala com a velocidade síncrona, então o resíduo que o integrador "
        "precisa rejeitar cresce perto de 60 Hz — mas o ki_iqs do v2 é o mesmo ganho em qualquer frequência."
    )
    _par(doc,
        "Esta versão (BW_v3) desacopla ki_iqs de kp_iqs: kp_iqs continua exatamente igual ao original (só "
        "função da frequência de chaveamento), e ki_iqs passa a crescer com a razão entre a frequência de "
        "acionamento e a nominal — BWi_iqs(frequency_ref) = (BWp_iqs/8)·(1 + frequency_ref/frequency_nom), "
        "dobrando a banda do integrador ao chegar em 60 Hz, em vez do valor fixo do v2. O anti-windup "
        "(já validado) é herdado sem alteração. ids, w e kp_iqs permanecem idênticos à biblioteca original; "
        "V/F e DOL não mudam."
    )

    doc.add_paragraph()
    _titulo_secao(doc, "Ripple de conjugado no último segundo — base x v2 x v3")
    _par(doc,
        "Ripple = (máximo − mínimo) do conjugado bruto no último segundo simulado, dividido pelo conjugado "
        "nominal do motor (Tnom), em %. MIT_G a 55 Hz segue excluído da leitura comparativa — é uma "
        "instabilidade pré-existente na biblioteca original (velocidade negativa, perda de sincronismo), já "
        "reproduzida de forma determinística, e não uma medida de ripple em regime.",
        tamanho=9, cor=MUTED, italico=True)
    _tabela_ripple(doc, df)

    doc.add_page_break()
    _titulo_secao(doc, "Evolução com a frequência — análise comparativa")
    _par(doc,
        "O resultado é desigual entre os dois motores: em MIT_P, o v3 melhora ligeiramente sobre o v2 em "
        "60 e 30 Hz e piora um pouco em 55 e 45 Hz — variações pequenas, nenhuma delas grave. Em MIT_G, o v3 "
        "é neutro a 45 e 30 Hz, mas desestabiliza a 60 Hz (ripple de 26,2% no v2 para 577,1%) e piora ainda "
        "mais a instabilidade pré-existente de 55 Hz. A mesma regra de escala que ajuda o motor pequeno "
        "prejudica o motor grande justamente na condição nominal.", negrito=True, cor=RUIM)

    sub_p = df[df.motor_id == "P"].sort_values("freq_hz", ascending=False)
    p = doc.add_paragraph()
    r = p.add_run("MIT_P")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = ACCENT
    _par(doc,
        "Base → v2 → v3, por frequência: " + "; ".join(
            f"{row.freq_hz:g} Hz ({row.ripple_base_pct:.1f}% → {row.ripple_v2_pct:.1f}% → "
            f"{row.ripple_v3_pct:.1f}%, v3 vs v2: {row.reducao_v3_vs_v2_pct:+.1f}%)"
            for _, row in sub_p.iterrows()
        ) + ". Variações de poucos pontos percentuais em qualquer direção — o ganho extra de ki_iqs em "
        "frequências mais altas não muda qualitativamente o comportamento do motor pequeno, só afina o que o "
        "v2 já tinha conseguido."
    )

    sub_g = df[(df.motor_id == "G") & (df.freq_hz < 55.0)].sort_values("freq_hz", ascending=False)
    p = doc.add_paragraph()
    r = p.add_run("MIT_G — 45 e 30 Hz (60 e 55 Hz à parte, ver abaixo)")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = ACCENT
    _par(doc,
        "Base → v2 → v3, por frequência: " + "; ".join(
            f"{row.freq_hz:g} Hz ({row.ripple_base_pct:.1f}% → {row.ripple_v2_pct:.1f}% → "
            f"{row.ripple_v3_pct:.1f}%, v3 vs v2: {row.reducao_v3_vs_v2_pct:+.1f}%)"
            for _, row in sub_g.iterrows()
        ) + ". Praticamente neutro — nessas duas frequências o v3 não piora nem melhora de forma relevante."
    )

    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("Regressão nova: MIT_G a 60 Hz")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RUIM
    _par(doc,
        "Tanto a biblioteca original quanto o v2 apresentam, em MIT_G a 60 Hz, um afundamento de velocidade "
        "conhecido por volta de t≈15,5-16 s (a referência de velocidade cai para ~1000 RPM por cerca de 1,5 s) "
        "— mas em ambos os casos o controlador se recupera e a velocidade volta a ~1791 RPM, estável, por "
        "volta de t≈17-18 s. Com o v3, o mesmo afundamento acontece, só que o controlador NÃO se recupera: a "
        "velocidade fica oscilando entre ~800 e ~1350 RPM até o fim da simulação (t=20 s), e o conjugado "
        "correspondente dispara (ripple de 577% no último segundo, contra 26,2% no v2 e 25,5% no original). O "
        "ganho de ki_iqs dobrado em 60 Hz, que ajudou o motor pequeno, piora o amortecimento da malha "
        "justamente no evento mais exigente do motor grande e impede a reconvergência."
    )
    _par(doc,
        "A figura de visão geral do conjugado a seguir mostra a janela completa (sem o corte automático que "
        "este estudo usa para não deixar o afundamento normal — autorrecuperável — comprimir o eixo Y): aqui "
        "o corte esconderia justamente a instabilidade.", tamanho=9, cor=MUTED, italico=True)

    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("Anomalia pré-existente: MIT_G a 55 Hz")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RUIM
    _par(doc,
        "Como já reportado na avaliação do v2, MIT_G a 55 Hz sofre uma instabilidade severa (velocidade "
        "negativa, perda de sincronismo) presente mesmo no FOC original — não causada pelo ki_iqs. O v3 "
        "piora ainda mais esse quadro já ruim (ripple de 7853% no v2 para 8938% no v3), mas não é um caso "
        "novo: é a mesma condição pré-existente reagindo pior a um ganho mais agressivo. Continua fora do "
        "escopo desta avaliação — ver investigação futura recomendada no relatório anterior."
    )

    for freq_hz in FREQS:
        doc.add_page_break()
        _titulo_secao(doc, f"Conjugado — {freq_hz:g} Hz")
        for motor_id in ("P", "G"):
            caminho = _figura_conjugado(motor_id, freq_hz)
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.add_run().add_picture(str(caminho), width=Cm(16.5))
            print(f"  [OK] {caminho}")
        if abs(freq_hz - 60.0) < 1e-9:
            _par(doc, "MIT_G acima: janela completa (0-20 s), sem corte — ver discussão da regressão a 60 Hz.",
                tamanho=9, cor=MUTED, italico=True)
            caminho_vel = _figura_grandeza("G", freq_hz, "velocidade")
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.add_run().add_picture(str(caminho_vel), width=Cm(16.5))
            print(f"  [OK] {caminho_vel}")

    doc.add_page_break()
    _titulo_secao(doc, "Conclusões")
    conclusoes = [
        "Desacoplar ki_iqs de kp_iqs e escaloná-lo pela razão frequency_ref/frequency_nom (dobrando a banda "
        "do integrador ao chegar em 60 Hz) refina o resultado do v2 em MIT_P, mas não generaliza para MIT_G: "
        "o mesmo ganho mais agressivo em 60 Hz, que ajuda o motor pequeno, impede a reconvergência do motor "
        "grande depois do afundamento de velocidade conhecido naquele ponto — uma regressão nova, não presente "
        "no v2.",
        "Isso indica que a escala correta de ki_iqs com a frequência não pode ser a mesma razão para motores "
        "de porte muito diferente: MIT_P e MIT_G têm inércia, constantes de tempo elétrica e margens de "
        "estabilidade distintas, e uma regra única (frequency_ref/frequency_nom, sem normalizar por nenhuma "
        "dessas grandezas do motor) sobrecarrega o motor grande antes de ganhar o mesmo benefício relativo "
        "que dá ao pequeno.",
        "MIT_G a 55 Hz permanece como uma instabilidade separada e pré-existente (não causada por nenhuma das "
        "variantes testadas), que o v3 só torna um pouco mais severa — não deve ser confundida com a "
        "regressão nova de 60 Hz, que é consequência direta desta mudança.",
        "Recomendação: não adotar o v3 como está para MIT_G. Se a escala por frequência for retomada, "
        "precisa de um critério por motor (por exemplo, normalizando o incremento de banda pela margem de "
        "fase disponível de cada máquina, não só pela razão de frequências) e, no mínimo, validação explícita "
        "do comportamento no afundamento pós-carga a 60 Hz antes de qualquer novo teste em MIT_G. Para "
        "MIT_P, o v3 é uma pequena melhora sobre o v2; para MIT_G, o v2 (ki_iqs fixo + anti-windup, sem "
        "dependência de frequência) continua sendo a versão mais segura das testadas até aqui.",
    ]
    for c in conclusoes:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(c)
        run.font.size = Pt(10)
        run.font.name = "Arial"

    destino = PASTA / "Relatorio_ki_iqs_freq_dependente.docx"
    doc.save(destino)
    print(f"[OK] {destino}")
    return df


if __name__ == "__main__":
    montar()
