"""Análise de eventos e figuras anotadas (sobressinal, acomodação, regime, subida).

Dois eventos são analisados para cada cenário, para conjugado e velocidade:

    E1 "Entrada em velocidade nominal" : janela [0, t_carga] (partida + regime em vazio)
    E2 "Após a entrada da carga"       : janela [t_carga, tf] (degrau de carga nominal)

Definições (as mesmas para todos os cenários e para os dois eventos):

  Sinal analisado   média móvel de `SUAVIZACAO_S` sobre o sinal bruto (remove o
                    ripple de chaveamento; o sinal bruto é plotado ao fundo).
  Referência        velocidade: velocidade nominal do motor (RPM).
                    conjugado: 0 em E1 (vazio) e conjugado nominal em E2.
  Tubo de acomodação  referência ± 5% da escala (escala = velocidade nominal
                    ou conjugado nominal), retas pontilhadas; a referência é
                    a reta tracejada.
  Regime permanente média do sinal nos últimos 10% da janela do evento.
  Máx. sobressinal  extremo do sinal, em relação ao regime, na direção do
                    movimento (regime - valor inicial). Se a excursão do
                    evento for desprezível (< 5% da escala; ex.: conjugado
                    na partida em vazio), usa-se o maior desvio absoluto em
                    relação ao regime. Em % da excursão (ou da escala).
  Acomodação        primeiro instante a partir do qual o sinal permanece
                    dentro do tubo até o fim da janela. Se o sinal termina
                    fora do tubo, "não acomoda".
  Tempo de subida   de 10% a 90% da excursão (valor inicial -> regime). Se a
                    excursão for desprezível, usa-se a excursão até o pico.
"""

from dataclasses import dataclass

import numpy as np
from plotly import graph_objects as go

SUAVIZACAO_S = 0.02
BANDA = 0.05
CAUDA = 0.10

COR_PICO = "#c2185b"
COR_ACOMODACAO = "#000000"
COR_REGIME = "#008b8b"
COR_SUBIDA = "#9467bd"


@dataclass
class Evento:
    nome: str
    t_ini: float
    t_fim: float
    ref: float
    escala: float


def media_movel(t, y, janela_s=SUAVIZACAO_S):
    dt = float(np.median(np.diff(t)))
    n = max(1, int(round(janela_s / dt)))
    if n <= 1:
        return np.asarray(y, dtype=float)
    kernel = np.ones(n) / n
    esq = n // 2
    dir_ = n - 1 - esq
    return np.convolve(np.pad(y, (esq, dir_), mode="edge"), kernel, mode="valid")


def _primeiro_cruzamento(tt, yy, nivel, sentido):
    """Primeiro índice em que yy cruza `nivel` no sentido dado (+1 subindo, -1 descendo)."""
    dentro = (yy - nivel) * sentido >= 0
    idx = np.flatnonzero(dentro)
    return int(idx[0]) if idx.size else None


def analisar(t, ys, ev, y_ini):
    """Calcula as marcações de um evento sobre o sinal suavizado `ys`."""
    m = (t >= ev.t_ini) & (t <= ev.t_fim)
    tt, yy = t[m], ys[m]
    tol = BANDA * ev.escala

    n_cauda = max(1, int(CAUDA * len(tt)))
    y_reg = float(np.mean(yy[-n_cauda:]))
    t_reg = float(tt[-n_cauda:].mean())

    exc = y_reg - y_ini
    significativa = abs(exc) >= BANDA * ev.escala
    if significativa:
        sentido = 1.0 if exc > 0 else -1.0
        idx_pk = int(np.argmax(sentido * (yy - y_reg)))
        pct = 100.0 * sentido * (yy[idx_pk] - y_reg) / abs(exc)
    else:
        idx_pk = int(np.argmax(np.abs(yy - y_reg)))
        pct = 100.0 * (yy[idx_pk] - y_reg) / ev.escala
    t_pk, y_pk = float(tt[idx_pk]), float(yy[idx_pk])
    ha_sobressinal = pct > 0 if significativa else True

    dentro = np.abs(yy - ev.ref) <= tol
    if dentro[-1]:
        fora = np.flatnonzero(~dentro)
        i_ac = int(fora[-1] + 1) if fora.size else 0
        t_ac, y_ac = float(tt[i_ac]), float(yy[i_ac])
        tempo_ac = t_ac - ev.t_ini
    else:
        t_ac = y_ac = tempo_ac = None

    alvo = y_reg if significativa else y_pk
    delta = alvo - y_ini
    t_s0 = y_s0 = t_s1 = y_s1 = tempo_sub = None
    if abs(delta) > 1e-9:
        sent = 1 if delta > 0 else -1
        n10, n90 = y_ini + 0.1 * delta, y_ini + 0.9 * delta
        i10 = _primeiro_cruzamento(tt, yy, n10, sent)
        if i10 is not None:
            i90 = _primeiro_cruzamento(tt[i10:], yy[i10:], n90, sent)
            if i90 is not None:
                i90 += i10
                t_s0, y_s0 = float(tt[i10]), float(yy[i10])
                t_s1, y_s1 = float(tt[i90]), float(yy[i90])
                tempo_sub = t_s1 - t_s0

    return dict(
        evento=ev.nome, t_ini=ev.t_ini, t_fim=ev.t_fim, ref=ev.ref, escala=ev.escala,
        y_ini=float(y_ini), y_reg=y_reg, t_reg=t_reg,
        t_pk=t_pk, y_pk=y_pk, sobressinal_pct=float(pct), ha_sobressinal=bool(ha_sobressinal),
        excursao_significativa=bool(significativa),
        t_acom=t_ac, y_acom=y_ac, tempo_acom=tempo_ac,
        t_sub0=t_s0, y_sub0=y_s0, t_sub1=t_s1, y_sub1=y_s1, tempo_subida=tempo_sub,
        tubo_inf=ev.ref - tol, tubo_sup=ev.ref + tol,
    )


def eventos_do_teste(t_carga, tf, ref_conjugado_carga, ref_velocidade, torque_nom):
    """Devolve {'conjugado': (E1, E2), 'velocidade': (E1, E2)}."""
    e1 = "Entrada em velocidade nominal"
    e2 = "Após a entrada da carga"
    return {
        "conjugado": (
            Evento(e1, 0.0, t_carga, 0.0, torque_nom),
            Evento(e2, t_carga, tf, ref_conjugado_carga, torque_nom),
        ),
        "velocidade": (
            Evento(e1, 0.0, t_carga, ref_velocidade, ref_velocidade),
            Evento(e2, t_carga, tf, ref_velocidade, ref_velocidade),
        ),
    }


def valor_pre_evento(t, ys, t_ev, janela=0.02):
    m = (t >= t_ev - janela) & (t < t_ev)
    return float(np.mean(ys[m])) if m.any() else float(ys[np.searchsorted(t, t_ev) - 1])


def _dec(x, y, n=20000):
    if len(x) <= n:
        return x, y
    passo = int(np.ceil(len(x) / n))
    return x[::passo], y[::passo]


def _rotulo(grandeza, casas, t, y):
    if grandeza == "conjugado":
        return f"t = {t:.{casas[0]}f} s; T = {y:.{casas[1]}f} N·m"
    return f"t = {t:.{casas[0]}f} s; ω = {y:.{casas[1]}f} RPM"


def figura_anotada(t, y_raw, ys, res, ev, grandeza, nome_cenario, cor, titulo, janela_plot=None):
    """Figura Plotly com todas as marcações de um evento."""
    unidade = "N·m" if grandeza == "conjugado" else "RPM"
    casas = (3, 2) if grandeza == "conjugado" else (3, 1)
    eixo_y = "Conjugado (N·m)" if grandeza == "conjugado" else "Velocidade (RPM)"

    x0, x1 = janela_plot if janela_plot else (ev.t_ini, ev.t_fim)
    m = (t >= x0) & (t <= x1)
    fig = go.Figure()

    xr, yr = _dec(t[m], y_raw[m])
    fig.add_trace(go.Scatter(x=xr, y=yr, name=f"{nome_cenario} (bruto)",
                             line=dict(color=cor, width=1), opacity=0.35))
    xs, yv = _dec(t[m], ys[m])
    fig.add_trace(go.Scatter(x=xs, y=yv, name=f"{nome_cenario} (média móvel {SUAVIZACAO_S * 1000:.0f} ms)",
                             line=dict(color=cor, width=2.5)))

    fig.add_hline(y=res["ref"], line=dict(color="black", dash="dash", width=1.5),
                  annotation_text="Referência", annotation_position="top left")
    for nivel, rot in ((res["tubo_sup"], "+5%"), (res["tubo_inf"], "-5%")):
        fig.add_hline(y=nivel, line=dict(color="gray", dash="dot", width=1.5),
                      annotation_text=f"Tubo {rot}", annotation_position="bottom right")

    def ponto(x, y, nome, cor_p, simbolo, ax, ay, texto):
        # abre a caixa de texto para o lado com mais espaço na janela plotada
        if (x - x0) / (x1 - x0) > 0.55:
            ax = -abs(ax) - 40
        fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers", name=nome,
                                 marker=dict(color=cor_p, size=11, symbol=simbolo,
                                             line=dict(color="white", width=1))))
        fig.add_annotation(x=x, y=y, text=texto, showarrow=True, arrowhead=2,
                           ax=ax, ay=ay, font=dict(size=11, color=cor_p),
                           bgcolor="rgba(255,255,255,0.85)", bordercolor=cor_p)

    rot_pk = "Máx. sobressinal" if res["ha_sobressinal"] else "Máx. atingido (sem sobressinal)"
    ponto(res["t_pk"], res["y_pk"], rot_pk, COR_PICO, "circle", 60, -50,
          f"{rot_pk}<br>{_rotulo(grandeza, casas, res['t_pk'], res['y_pk'])}<br>({res['sobressinal_pct']:+.1f}%)")

    if res["t_acom"] is not None:
        ponto(res["t_acom"], res["y_acom"], "Acomodação (±5%)", COR_ACOMODACAO, "square", 60, 55,
              f"Acomodação em {res['tempo_acom']:.3f} s<br>{_rotulo(grandeza, casas, res['t_acom'], res['y_acom'])}")
    else:
        fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.02, showarrow=False,
                           text="Não acomoda no tubo ±5%", font=dict(color=COR_ACOMODACAO, size=12),
                           bgcolor="rgba(255,255,255,0.85)", bordercolor=COR_ACOMODACAO)

    ponto(res["t_reg"], res["y_reg"], "Regime permanente", COR_REGIME, "diamond", -70, -55,
          f"Regime permanente<br>{_rotulo(grandeza, casas, res['t_reg'], res['y_reg'])}")

    if res["t_sub0"] is not None:
        for x, rot in ((res["t_sub0"], "início da subida"), (res["t_sub1"], "fim da subida")):
            fig.add_vline(x=x, line=dict(color=COR_SUBIDA, width=1.5),
                          annotation_text=f"{rot}<br>{x:.3f} s", annotation_position="top",
                          annotation_font=dict(color=COR_SUBIDA, size=10))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=f"Subida 10–90% ({res['tempo_subida']:.3f} s)",
                                 line=dict(color=COR_SUBIDA, width=1.5)))

    fig.update_layout(title=titulo, xaxis_title="Tempo (s)", yaxis_title=eixo_y,
                      legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
                      margin=dict(t=70, b=110, r=40), width=1000, height=620)
    fig.update_xaxes(range=[x0, x1])
    ymin = float(min(np.min(yv), res["tubo_inf"]))
    ymax = float(max(np.max(yv), res["tubo_sup"]))
    pad = 0.12 * (ymax - ymin if ymax > ymin else 1.0)
    fig.update_yaxes(range=[ymin - pad, ymax + pad])
    return fig
