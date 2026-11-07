"""Gráficos anotados do estudo de frequência — sempre sobre o sinal bruto.

`comum.anotacoes.analisar` calcula sobressinal, tempo de subida e acomodação
a partir de qualquer sinal que receba; aqui ele recebe sempre o sinal bruto
(sem média móvel), para que as marcações reflitam o dado físico medido, sem
questionamento sobre um pré-processamento que poderia mascarar o resultado.

Tempo de acomodação fica de fora deste estudo por ora: com dado bruto, o
torque do FOC oscila sem amortecer até o fim da janela em vários cenários, e
o critério de "última amostra dentro da faixa" de `comum.anotacoes.analisar`
não é robusto a isso.
"""

import sys
import time
from pathlib import Path

import numpy as np
from plotly import graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import anotacoes as an

CORES = {"dol": "#2ca02c", "vf": "#1f77b4", "foc": "#d62728"}
NOMES = {"dol": "Partida direta (DOL)", "vf": "Inversor V/F", "foc": "Inversor FOC"}
LINHAS = (("velocidade", (3, 1)), ("conjugado", (3, 2)))


def salvar_imagem(fig, caminho, scale=2, tentativas=6, espera=1.5):
    """`fig.write_image` com retentativa: o Kaleido, nesta máquina, falha às
    vezes com OSError [Errno 22] de forma transiente (arquivo diferente a
    cada rodada) quando várias imagens são exportadas em sequência rápida —
    não é um erro de dado, refazer a mesma chamada depois de uma pequena
    espera resolve."""
    ultimo = None
    for _ in range(tentativas):
        try:
            fig.write_image(str(caminho), scale=scale)
            return
        except OSError as e:
            ultimo = e
            time.sleep(espera)
    raise ultimo


def _dec(x, y, n=20000):
    if len(x) <= n:
        return x, y
    passo = int(np.ceil(len(x) / n))
    return x[::passo], y[::passo]


def eventos(motor, sim, freq_hz):
    """Eventos E1 (chegada na referência) e E2 (entrada da carga).

    A referência de velocidade de E1 é escalada pela frequência de ensaio
    (`freq_hz`), não a nominal de 60 Hz — senão o sobressinal/tubo de um
    ensaio a 30 Hz seria calculado contra a velocidade nominal de 60 Hz."""
    speed_nom_rpm = float(motor.speed_nom) * 60.0 / (2 * np.pi)
    ref_velocidade = speed_nom_rpm * freq_hz / 60.0
    return an.eventos_do_teste(sim.t_carga, sim.tf, float(motor.Tnom), ref_velocidade, float(motor.Tnom))


def _serie(dados, chave, grandeza):
    t, vel, conj, _ = dados[chave]
    return (t, vel) if grandeza == "velocidade" else (t, conj)


def _serie_carga_ref(dados, chave):
    t, _, _, conj_ref = dados[chave]
    return t, conj_ref


def _analise(dados, chave, grandeza, ev, evento_idx):
    t, y = _serie(dados, chave, grandeza)
    y_ini = 0.0 if evento_idx == 0 else an.valor_pre_evento(t, y, ev.t_ini)
    return t, y, an.analisar(t, y, ev, y_ini)


def _analise_na_janela(dados, chave, grandeza, ev, evento_idx, janela):
    """Mesma análise de `_analise` (sinal bruto), mas com o pico procurado só
    dentro de `janela` (o trecho realmente plotado) — não no evento inteiro.
    Sem isso, o "sobressinal" marcado podia ser um pico maior fora da área
    visível (ex.: um ciclo de oscilação tardio), e a marcação ficava invisível
    ou fora de contexto na figura."""
    t, y = _serie(dados, chave, grandeza)
    y_ini = 0.0 if evento_idx == 0 else an.valor_pre_evento(t, y, ev.t_ini)
    x0, x1 = janela
    ev_janela = an.Evento(ev.nome, max(ev.t_ini, x0), min(ev.t_fim, x1), ev.ref, ev.escala)
    return t, y, an.analisar(t, y, ev_janela, y_ini)


def _ax(tp, x0, x1, ax=30):
    """Espelha o deslocamento horizontal do texto quando o ponto já está na
    metade direita da janela, para a caixa não sair da figura."""
    return -ax - 40 if x1 > x0 and (tp - x0) / (x1 - x0) > 0.55 else ax


def _layout(fig, titulo, altura=1000, largura=900):
    fig.update_xaxes(title_text="Tempo (s)", row=2, col=1)
    fig.update_yaxes(title_text="Velocidade (RPM)", row=1, col=1)
    fig.update_yaxes(title_text="Conjugado (N·m)", row=2, col=1)
    fig.update_layout(title=dict(text=titulo, font=dict(size=13)), height=altura, width=largura,
                      legend=dict(orientation="h", yanchor="top", y=-0.09, x=0, font=dict(size=12)),
                      margin=dict(t=70, b=100, l=65, r=20), font=dict(family="Arial"))


def _fim_afundamento(dados, ordem, t_carga, tf):
    """Se alguma curva mostrar um afundamento de velocidade bem abaixo do
    regime pós-carga (ex.: reconvergência do FOC no motor grande em certas
    frequências), devolve o instante 0,5 s antes do início desse afundamento
    — para a figura geral não esticar o eixo Y até esse vale e comprimir o
    resto da curva. Sem afundamento (caso comum), devolve `tf` (sem corte).
    Detecção sempre por dado, nunca por tempo fixo: roda igual em qualquer
    motor/frequência, e só corta quando o afundamento realmente aparece."""
    inicio_min = None
    for chave in ordem:
        t, vel, _, _ = dados[chave]
        m_regime = (t >= t_carga + 0.3) & (t <= t_carga + 1.0)
        if not m_regime.any():
            continue
        base = float(np.median(vel[m_regime]))
        if base <= 0:
            continue
        limiar = 0.75 * base
        m_pos = t > t_carga + 1.0
        abaixo = m_pos & (vel < limiar)
        if not abaixo.any():
            continue
        inicio = float(t[abaixo][0])
        inicio_min = inicio if inicio_min is None else min(inicio_min, inicio)
    if inicio_min is None:
        return tf
    return max(t_carga, inicio_min - 0.5)


def figura_geral(dados, ordem, motor, sim, freq_hz, titulo):
    """Visão completa: velocidade em cima, conjugado embaixo, sinal bruto de
    cada cenário em `ordem`, com o ponto de máximo (tempo x valor) marcado na
    partida e na entrada da carga, para todas as curvas, e a referência de
    torque de carga tracejada. O eixo do tempo é cortado 0,5 s antes de um
    eventual afundamento de velocidade (ver `_fim_afundamento`), e o eixo Y
    é ajustado só com o dado dentro dessa janela visível."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    fim_visivel = _fim_afundamento(dados, ordem, sim.t_carga, sim.tf)
    janelas_evento = ((0.0, sim.t_carga), (sim.t_carga, fim_visivel))
    extremos = {1: [], 2: []}

    t_ref, y_ref = _serie_carga_ref(dados, ordem[0])
    m_ref = t_ref <= fim_visivel
    xr, yr = _dec(t_ref[m_ref], y_ref[m_ref])
    fig.add_trace(go.Scatter(x=xr, y=yr, name="Torque de carga (referência)",
                             line=dict(color="black", width=1.3, dash="dash")), row=2, col=1)
    if len(yr):
        extremos[2].extend([float(np.min(yr)), float(np.max(yr))])

    for chave in ordem:
        cor, nome = CORES[chave], NOMES[chave]
        for row, (grandeza, casas) in enumerate(LINHAS, start=1):
            t, y = _serie(dados, chave, grandeza)
            m_vis = t <= fim_visivel
            xr, yr = _dec(t[m_vis], y[m_vis])
            if len(yr):
                extremos[row].extend([float(np.min(yr)), float(np.max(yr))])
            fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=1.2),
                                     legendgroup=chave, showlegend=row == 1), row=row, col=1)
            for x0, x1 in janelas_evento:
                m = (t >= x0) & (t <= x1)
                if not m.any():
                    continue
                idx = int(np.argmax(y[m]))
                tp, yp = float(t[m][idx]), float(y[m][idx])
                fig.add_trace(go.Scatter(x=[tp], y=[yp], mode="markers", showlegend=False,
                                         marker=dict(color=cor, size=12, symbol="circle",
                                                     line=dict(color="white", width=1))), row=row, col=1)
                fig.add_annotation(x=tp, y=yp, text=an._rotulo(grandeza, casas, tp, yp), showarrow=True,
                                   arrowhead=2, ax=_ax(tp, x0, x1, 25), ay=-28,
                                   font=dict(size=8, color=cor),
                                   bgcolor="rgba(255,255,255,0.85)", bordercolor=cor, row=row, col=1)

    for row in (1, 2):
        if extremos[row]:
            ymin, ymax = min(extremos[row]), max(extremos[row])
            pad = 0.12 * (ymax - ymin) if ymax > ymin else 1.0
            fig.update_yaxes(range=[ymin - pad, ymax + pad], row=row, col=1)
    fig.update_xaxes(range=[0, fim_visivel])
    _layout(fig, titulo)
    return fig


def _layout_unica(fig, titulo, eixo_y, altura=750, largura=900):
    fig.update_xaxes(title_text="Tempo (s)")
    fig.update_yaxes(title_text=eixo_y)
    fig.update_layout(title=dict(text=titulo, font=dict(size=13)), height=altura, width=largura,
                      legend=dict(orientation="h", yanchor="top", y=-0.13, x=0, font=dict(size=12)),
                      margin=dict(t=70, b=90, l=65, r=20), font=dict(family="Arial"))


def figura_geral_unica(dados, ordem, motor, sim, freq_hz, grandeza, titulo, forcar_fim_visivel=None):
    """Mesmo recorte, cores e marcações de `figura_geral` (corte 0,5 s antes
    de um eventual afundamento, ponto de máximo na partida e na entrada da
    carga), mas numa figura de uma grandeza só — para quando velocidade e
    conjugado precisam sair em arquivos separados.

    `forcar_fim_visivel`, se passado, substitui o corte automático (usado
    quando o próprio afundamento não se recupera e precisa aparecer por
    inteiro, em vez de ser cortado da visão geral)."""
    fig = go.Figure()
    fim_visivel = forcar_fim_visivel if forcar_fim_visivel is not None else _fim_afundamento(dados, ordem, sim.t_carga, sim.tf)
    janelas_evento = ((0.0, sim.t_carga), (sim.t_carga, fim_visivel))
    extremos = []

    if grandeza == "conjugado":
        t_ref, y_ref = _serie_carga_ref(dados, ordem[0])
        m_ref = t_ref <= fim_visivel
        xr, yr = _dec(t_ref[m_ref], y_ref[m_ref])
        fig.add_trace(go.Scatter(x=xr, y=yr, name="Torque de carga (referência)",
                                 line=dict(color="black", width=2.6, dash="dash")))
        if len(yr):
            extremos.extend([float(np.min(yr)), float(np.max(yr))])

    for chave in ordem:
        cor, nome = CORES[chave], NOMES[chave]
        t, y = _serie(dados, chave, grandeza)
        m_vis = t <= fim_visivel
        xr, yr = _dec(t[m_vis], y[m_vis])
        if len(yr):
            extremos.extend([float(np.min(yr)), float(np.max(yr))])
        fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=2.4)))
        for x0, x1 in janelas_evento:
            m = (t >= x0) & (t <= x1)
            if not m.any():
                continue
            idx = int(np.argmax(y[m]))
            tp, yp = float(t[m][idx]), float(y[m][idx])
            fig.add_trace(go.Scatter(x=[tp], y=[yp], mode="markers", showlegend=False,
                                     marker=dict(color=cor, size=12, symbol="circle",
                                                 line=dict(color="white", width=1))))

    if extremos:
        ymin, ymax = min(extremos), max(extremos)
        pad = 0.12 * (ymax - ymin) if ymax > ymin else 1.0
        fig.update_yaxes(range=[ymin - pad, ymax + pad])
    fig.update_xaxes(range=[0, fim_visivel])
    eixo_y = "Velocidade (RPM)" if grandeza == "velocidade" else "Conjugado (N·m)"
    _layout_unica(fig, titulo, eixo_y)
    return fig


def figura_zoom(dados, motor, sim, evento_idx, janela, freq_hz, motor_label, descricao):
    """Zoom com janela explícita (`janela`): V/F e FOC totalmente anotados
    (sobressinal — o maior valor visto dentro da própria janela plotada — e
    tempo de subida), eixo Y ajustado para ocupar o espaço disponível sem
    cortar dado, e a referência de torque de carga tracejada."""
    evs = eventos(motor, sim, freq_hz)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    x0, x1 = janela
    curvas = (("vf", CORES["vf"], "Inversor V/F"), ("foc", CORES["foc"], "Inversor FOC"))
    extremos = {1: [], 2: []}

    t_ref, y_ref = _serie_carga_ref(dados, "vf")
    m_ref = (t_ref >= x0) & (t_ref <= x1)
    if m_ref.any():
        xr, yr = _dec(t_ref[m_ref], y_ref[m_ref])
        fig.add_trace(go.Scatter(x=xr, y=yr, name="Torque de carga (referência)",
                                 line=dict(color="black", width=1.3, dash="dash")), row=2, col=1)
        extremos[2].extend([float(np.min(yr)), float(np.max(yr))])

    for row, (grandeza, casas) in enumerate(LINHAS, start=1):
        for i, (chave, cor, nome) in enumerate(curvas):
            ev = evs[grandeza][evento_idx]
            t, y, res = _analise_na_janela(dados, chave, grandeza, ev, evento_idx, janela)
            m = (t >= x0) & (t <= x1)
            xr, yr = _dec(t[m], y[m])
            if len(yr):
                extremos[row].extend([float(np.min(yr)), float(np.max(yr))])
            fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=1.3),
                                     legendgroup=chave, showlegend=row == 1), row=row, col=1)

            rot_pk = "Máx. sobressinal" if res["ha_sobressinal"] else "Máx. atingido"
            fig.add_trace(go.Scatter(x=[res["t_pk"]], y=[res["y_pk"]], mode="markers", showlegend=False,
                                     marker=dict(color=cor, size=16.5, symbol="circle",
                                                 line=dict(color="white", width=1.5))), row=row, col=1)
            # Caixas presas fora da faixa ocupada pelo dado (ver padding
            # abaixo: o eixo Y reserva ~17% de altura no topo e na base, sem
            # nenhuma curva desenhada ali), ancoradas por "yanchor" para
            # crescerem para fora do gráfico em vez de para dentro — assim a
            # caixa nunca cobre o ponto marcado nem a curva, não importa em
            # que instante da janela o pico ou o cruzamento caiam.
            xref_row = f"x{row if row > 1 else ''} domain"
            yref_row = f"y{row if row > 1 else ''} domain"
            x_canto = 0.01 if i == 0 else 0.99
            ancora = "left" if i == 0 else "right"
            fig.add_annotation(
                xref=xref_row, yref=yref_row, x=x_canto, y=0.995, xanchor=ancora, yanchor="top",
                showarrow=False,
                text=f"{rot_pk} ({nome}): ({res['sobressinal_pct']:+.1f}%)<br>{an._rotulo(grandeza, casas, res['t_pk'], res['y_pk'])}",
                font=dict(size=9.5, color=cor),
                bgcolor="rgba(255,255,255,0.92)", bordercolor=cor, borderwidth=2, row=row, col=1)

            if res["t_sub0"] is not None:
                for xv in (res["t_sub0"], res["t_sub1"]):
                    fig.add_vline(x=xv, line=dict(color=cor, width=1.3, dash="dash"), row=row, col=1)
                fig.add_annotation(
                    xref=xref_row, yref=yref_row, x=x_canto, y=0.005, xanchor=ancora, yanchor="bottom",
                    showarrow=False,
                    text=f"Subida 10–90% ({nome}): {res['tempo_subida']:.3f} s",
                    font=dict(size=9.5, color=cor),
                    bgcolor="rgba(255,255,255,0.92)", bordercolor=cor, borderwidth=2, row=row, col=1)

    for row in (1, 2):
        if extremos[row]:
            ymin, ymax = min(extremos[row]), max(extremos[row])
            # Padding grande o bastante para reservar uma faixa livre de
            # dado no topo e na base do eixo Y (~17% cada, com fator 0.25):
            # é nessa faixa que as caixas de sobressinal/subida ficam presas
            # (yanchor "top"/"bottom"), nunca sobre o ponto ou a curva.
            pad = 0.25 * (ymax - ymin) if ymax > ymin else 1.0
            fig.update_yaxes(range=[ymin - pad, ymax + pad], row=row, col=1)

    pad_x = 0.02 * (x1 - x0)
    fig.update_xaxes(range=[x0 - pad_x, x1 + pad_x])
    titulo = f"{motor_label} — {freq_hz:g} Hz — zoom {x0:g}s–{x1:g}s — {descricao}"
    _layout(fig, titulo)
    return fig
