"""Gráficos anotados do estudo de frequência — sempre sobre o sinal bruto.

`comum.anotacoes.analisar` calcula sobressinal, tempo de subida e acomodação
a partir de qualquer sinal que receba; aqui ele recebe sempre o sinal bruto
(sem média móvel), para que as marcações reflitam o dado físico medido, sem
questionamento sobre um pré-processamento que poderia mascarar o resultado.
"""

import sys
from pathlib import Path

import numpy as np
from plotly import graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import anotacoes as an

# Tempo de acomodação fica de fora deste estudo por ora (ver `figura_zoom_foc`):
# com dado bruto, o torque do FOC oscila sem amortecer até o fim da janela em
# vários cenários, e o critério de "última amostra dentro da faixa" de
# `comum.anotacoes.analisar` não é robusto a isso — pode marcar "acomodou" por
# só a amostra final ter caído dentro da faixa por acaso. Fica para retomar
# com um critério mais robusto (ex.: permanência mínima na faixa).

CORES = {"dol": "#2ca02c", "vf": "#1f77b4", "foc": "#d62728"}
NOMES = {"dol": "Partida direta (DOL)", "vf": "Inversor V/F", "foc": "Inversor FOC"}
LINHAS = (("velocidade", (3, 1)), ("conjugado", (3, 2)))


def _dec(x, y, n=20000):
    if len(x) <= n:
        return x, y
    passo = int(np.ceil(len(x) / n))
    return x[::passo], y[::passo]


def eventos(motor, sim):
    return an.eventos_do_teste(sim.t_carga, sim.tf, float(motor.Tnom),
                               float(motor.speed_nom) * 60 / (2 * np.pi), float(motor.Tnom))


def _serie(dados, chave, grandeza):
    t, vel, conj = dados[chave]
    return (t, vel) if grandeza == "velocidade" else (t, conj)


def _analise(dados, chave, grandeza, ev, evento_idx):
    t, y = _serie(dados, chave, grandeza)
    y_ini = 0.0 if evento_idx == 0 else an.valor_pre_evento(t, y, ev.t_ini)
    return t, y, an.analisar(t, y, ev, y_ini)


def _analise_suave(dados, chave, grandeza, ev, evento_idx):
    """Mesma análise, mas sobre o sinal com média móvel — usada só para
    escolher a largura das janelas de zoom (`janelas`, abaixo), não para as
    marcações mostradas nas figuras (essas usam sempre o sinal bruto, via
    `_analise`). Sinal bruto de ripple de chaveamento pode fazer o pico
    "aparente" cair numa amostra de ruído distante do transitório real,
    alargando a janela sem necessidade; a versão suavizada só orienta o
    enquadramento visual."""
    t, y = _serie(dados, chave, grandeza)
    ys = an.media_movel(t, y)
    y_ini = 0.0 if evento_idx == 0 else an.valor_pre_evento(t, ys, ev.t_ini)
    return an.analisar(t, ys, ev, y_ini)


def janelas(dados, ordem, motor, sim, evento_idx):
    """(janela_apertada, janela_larga) em torno do evento, cobrindo o pico de
    todas as curvas em `ordem` (apertada) ou a acomodação completa (larga).

    Limita a busca a `teto` (fração do evento): sinais que oscilam sem
    amortecer (ex.: torque do FOC após a carga) nunca "acomodam" segundo
    `analisar`, e sem esse limite a janela esticaria até o fim do ensaio."""
    evs = eventos(motor, sim)
    ev_ref = evs["velocidade"][evento_idx]
    t_ini, t_fim = ev_ref.t_ini, ev_ref.t_fim
    teto = t_ini + 0.4 * (t_fim - t_ini)

    picos, fins = [], []
    for chave in ordem:
        for grandeza, _ in LINHAS:
            ev = evs[grandeza][evento_idx]
            res = _analise_suave(dados, chave, grandeza, ev, evento_idx)
            picos.append(min(res["t_pk"], teto))
            candidatos = [v for v in (res["t_acom"], res["t_sub1"], res["t_pk"]) if v is not None]
            fins.append(min(max(candidatos) if candidatos else t_ini, teto))
    apertada = (max(0.0, t_ini - 0.3 * sim.zoom_antes), min(sim.tf, max(picos) + 0.5 * sim.zoom_antes))
    larga = (max(0.0, t_ini - sim.zoom_antes), min(sim.tf, max(fins) + sim.zoom_depois))
    return apertada, larga


def _ax(tp, x0, x1, ax=30):
    """Espelha o deslocamento horizontal do texto quando o ponto já está na
    metade direita da janela, para a caixa não sair da figura."""
    return -ax - 40 if x1 > x0 and (tp - x0) / (x1 - x0) > 0.55 else ax


def _layout(fig, titulo, altura=760, largura=850):
    fig.update_xaxes(title_text="Tempo (s)", row=2, col=1)
    fig.update_yaxes(title_text="Velocidade (RPM)", row=1, col=1)
    fig.update_yaxes(title_text="Conjugado (N·m)", row=2, col=1)
    fig.update_layout(title=dict(text=titulo, font=dict(size=13)), height=altura, width=largura,
                      legend=dict(orientation="h", yanchor="top", y=-0.09, x=0, font=dict(size=10)),
                      margin=dict(t=60, b=90, l=65, r=25), font=dict(family="Arial"))


def figura_geral(dados, ordem, motor, sim, titulo):
    """Visão completa: velocidade em cima, conjugado embaixo, sinal bruto de
    cada cenário em `ordem`, com o ponto de máximo (tempo x valor) marcado na
    partida e na entrada da carga, para todas as curvas."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    janelas_evento = ((0.0, sim.t_carga), (sim.t_carga, sim.tf))
    for chave in ordem:
        cor, nome = CORES[chave], NOMES[chave]
        for row, (grandeza, casas) in enumerate(LINHAS, start=1):
            t, y = _serie(dados, chave, grandeza)
            xr, yr = _dec(t, y)
            fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=1.2),
                                     legendgroup=chave, showlegend=row == 1), row=row, col=1)
            for x0, x1 in janelas_evento:
                m = (t >= x0) & (t <= x1)
                if not m.any():
                    continue
                idx = int(np.argmax(y[m]))
                tp, yp = float(t[m][idx]), float(y[m][idx])
                fig.add_trace(go.Scatter(x=[tp], y=[yp], mode="markers", showlegend=False,
                                         marker=dict(color=cor, size=8, symbol="circle",
                                                     line=dict(color="white", width=1))), row=row, col=1)
                fig.add_annotation(x=tp, y=yp, text=an._rotulo(grandeza, casas, tp, yp), showarrow=True,
                                   arrowhead=2, ax=_ax(tp, x0, x1, 25), ay=-28,
                                   font=dict(size=8, color=cor),
                                   bgcolor="rgba(255,255,255,0.85)", bordercolor=cor, row=row, col=1)
    _layout(fig, titulo, altura=780, largura=1150)
    return fig


def figura_zoom_pico(dados, ordem, motor, sim, evento_idx, janela, titulo):
    """Zoom apertado: marca o pico de sobressinal (ponto + valor) de cada
    curva em `ordem`."""
    evs = eventos(motor, sim)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    x0, x1 = janela
    pad = 0.10 * (x1 - x0)
    for i, chave in enumerate(ordem):
        cor, nome = CORES[chave], NOMES[chave]
        for row, (grandeza, casas) in enumerate(LINHAS, start=1):
            ev = evs[grandeza][evento_idx]
            t, y, res = _analise(dados, chave, grandeza, ev, evento_idx)
            m = (t >= x0) & (t <= x1)
            xr, yr = _dec(t[m], y[m])
            fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=1.3),
                                     legendgroup=chave, showlegend=row == 1), row=row, col=1)
            rot = "Máx. sobressinal" if res["ha_sobressinal"] else "Máx. atingido"
            fig.add_trace(go.Scatter(x=[res["t_pk"]], y=[res["y_pk"]], mode="markers", showlegend=False,
                                     marker=dict(color=cor, size=10, symbol="circle",
                                                 line=dict(color="white", width=1))), row=row, col=1)
            fig.add_annotation(
                x=res["t_pk"], y=res["y_pk"],
                text=f"{rot} ({res['sobressinal_pct']:+.1f}%)<br>{an._rotulo(grandeza, casas, res['t_pk'], res['y_pk'])}",
                showarrow=True, arrowhead=2, ax=_ax(res["t_pk"], x0, x1, 30), ay=-30 - 32 * i,
                font=dict(size=9, color=cor),
                bgcolor="rgba(255,255,255,0.85)", bordercolor=cor, row=row, col=1)
    fig.update_xaxes(range=[x0 - pad, x1 + pad])
    _layout(fig, titulo)
    return fig


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


def figura_zoom_foc(dados, motor, sim, evento_idx, janela, titulo):
    """Zoom largo: V/F e FOC, ambos anotados (sobressinal — o maior valor
    visto dentro da própria janela plotada — e tempo de subida). Tempo de
    acomodação fica de fora por ora — ver nota no topo do módulo."""
    evs = eventos(motor, sim)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    x0, x1 = janela
    curvas = (("vf", CORES["vf"], "Inversor V/F"), ("foc", CORES["foc"], "Inversor FOC"))

    for row, (grandeza, casas) in enumerate(LINHAS, start=1):
        for i, (chave, cor, nome) in enumerate(curvas):
            ev = evs[grandeza][evento_idx]
            t, y, res = _analise_na_janela(dados, chave, grandeza, ev, evento_idx, janela)
            m = (t >= x0) & (t <= x1)
            xr, yr = _dec(t[m], y[m])
            fig.add_trace(go.Scatter(x=xr, y=yr, name=nome, line=dict(color=cor, width=2.6),
                                     legendgroup=chave, showlegend=row == 1), row=row, col=1)

            rot_pk = "Máx. sobressinal" if res["ha_sobressinal"] else "Máx. atingido"
            fig.add_trace(go.Scatter(x=[res["t_pk"]], y=[res["y_pk"]], mode="markers", showlegend=False,
                                     marker=dict(color=cor, size=11, symbol="circle",
                                                 line=dict(color="white", width=1.5))), row=row, col=1)
            ax_base = _ax(res["t_pk"], x0, x1, 35)
            fig.add_annotation(
                x=res["t_pk"], y=res["y_pk"],
                text=f"{rot_pk} ({nome})<br>({res['sobressinal_pct']:+.1f}%)<br>{an._rotulo(grandeza, casas, res['t_pk'], res['y_pk'])}",
                showarrow=True, arrowhead=2,
                ax=ax_base + (0 if i == 0 else (55 if ax_base >= 0 else -55)),
                ay=(-65 if i == 0 else 100),
                font=dict(size=11, color=cor),
                bgcolor="rgba(255,255,255,0.92)", bordercolor=cor, borderwidth=2, row=row, col=1)

            if res["t_sub0"] is not None:
                for xv in (res["t_sub0"], res["t_sub1"]):
                    fig.add_vline(x=xv, line=dict(color=cor, width=2.6, dash="dash"), row=row, col=1)
                fig.add_annotation(
                    xref=f"x{row if row > 1 else ''} domain", yref=f"y{row if row > 1 else ''} domain",
                    x=0.99, y=0.04 + 0.12 * i, xanchor="right", showarrow=False,
                    text=f"Subida 10–90% ({nome}): {res['tempo_subida']:.3f} s",
                    font=dict(size=11, color=cor),
                    bgcolor="rgba(255,255,255,0.92)", bordercolor=cor, borderwidth=2, row=row, col=1)

    pad = 0.06 * (x1 - x0)
    fig.update_xaxes(range=[x0 - pad, x1 + pad])
    _layout(fig, titulo)
    fig.update_layout(legend=dict(font=dict(size=15)))
    return fig
