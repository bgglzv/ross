"""Ferramentas comuns às opções de mitigação da saturação de corrente do FOC.

Cada opção simula o FOC (motor pequeno, 60 Hz) com a biblioteca original,
mede quanto tempo a referência de corrente q fica saturada e produz figuras com
velocidade (em cima) e conjugado (embaixo) com as mesmas marcações do dossiê.
"""

import sys
from pathlib import Path

import numpy as np
from plotly import graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comum import anotacoes as an

LARGURA_PX = 1700
ALTURA_PX = 1180

COR_VELOCIDADE = "#1f77b4"
COR_CONJUGADO = "#d62728"


def contador_de_saturacao(inversor_base):
    """Subclasse do FOC que registra a razão |iq_ref sem limite| / iqs_max a cada passo."""

    class FOCContador(inversor_base):
        instancias = []

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.registro_t = []
            self.registro_razao = []
            FOCContador.instancias.append(self)

        def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
            err_w = self.speed_control(t, frequency_ref) - rotor_speed
            iqs_ref_unsat = self.kp_w * err_w + self.ki_w * self.control_state["int_err_w"]
            self.registro_t.append(t)
            self.registro_razao.append(abs(iqs_ref_unsat) / (3.0 * self.Is_nom))
            return super().get_current_state(t, dt, rotor_speed, ia, ib, ic, frequency_ref)

    return FOCContador


def simular_foc(motor, t, rampa, t_carga, frequencia_chaveamento, time_step, freq_ref,
                fator_barramento=None, inversor_classe=None):
    """Roda o FOC da biblioteca original e devolve (resultados, registro_t, registro_razao).

    `fator_barramento` substitui, só durante a simulação, o fator 1,35 que converte
    tensão de linha em tensão do barramento CC. `inversor_classe` substitui o FOC da biblioteca por uma
    subclasse que já registre `registro_t`/`registro_razao` (ver `contador_de_saturacao`).
    """
    from ross.motors import inverters, motor_element

    contador = inversor_classe or contador_de_saturacao(inverters.InverterFOC)
    original = motor_element.InverterFOC
    original_barramento = motor_element.line_to_dc_bus
    motor_element.InverterFOC = contador
    if fator_barramento is not None:
        motor_element.line_to_dc_bus = lambda v_line: v_line * fator_barramento
    try:
        resultados = motor.run_with_inverter_foc(
            t, time_step=time_step, load_torque_entrance_time=t_carga,
            load_torque_ratio=1.0, time_ramp=rampa,
            frequency_s=frequencia_chaveamento, frequency_ref=freq_ref)
    finally:
        motor_element.InverterFOC = original
        motor_element.line_to_dc_bus = original_barramento
    inv = contador.instancias[-1]
    return resultados, np.array(inv.registro_t), np.array(inv.registro_razao)


def estatisticas_saturacao(t_reg, razao, rampa, t_carga):
    sat = razao > 1.0

    def pct(m):
        return float(100.0 * np.mean(sat[m])) if m.any() else float("nan")

    return dict(
        pct_total=pct(np.ones_like(sat, dtype=bool)),
        pct_rampa=pct(t_reg < rampa),
        pct_regime_vazio=pct((t_reg >= rampa) & (t_reg < t_carga)),
        pct_apos_carga=pct(t_reg >= t_carga),
        razao_maxima=float(np.max(razao)),
    )


def _eventos(motor, t_carga, tf):
    return an.eventos_do_teste(t_carga, tf, float(motor.Tnom),
                               float(motor.speed_nom) * 60 / (2 * np.pi), float(motor.Tnom))


def _analise(t, y_raw, grandeza, eventos):
    ys = an.media_movel(t, y_raw)
    saida = []
    for k, ev in enumerate(eventos[grandeza]):
        y_ini = 0.0 if k == 0 else an.valor_pre_evento(t, ys, ev.t_ini)
        saida.append((ev, an.analisar(t, ys, ev, y_ini)))
    return ys, saida


def _fim_do_transitorio(analises):
    tempos = [r[k] for _, r in analises for k in ("t_acom", "t_sub1", "t_pk") if r[k] is not None]
    return max(tempos) if tempos else None


def janelas_de_zoom(t, velocidade_rpm, conjugado, motor, t_carga, tf, rampa):
    """Escolhe janelas de zoom que enquadram o transitório de cada evento."""
    eventos = _eventos(motor, t_carga, tf)
    fim_partida, fim_carga = [], []
    for grandeza, y in (("velocidade", velocidade_rpm), ("conjugado", conjugado)):
        _, analises = _analise(t, y, grandeza, eventos)
        fim_partida.append(_fim_do_transitorio(analises[:1]))
        fim_carga.append(_fim_do_transitorio(analises[1:]))

    fim1 = max([v for v in fim_partida if v is not None], default=rampa + 0.3)
    x1_partida = min(t_carga - 0.05, max(rampa + 0.3, 1.15 * fim1))
    fim2 = max([v for v in fim_carga if v is not None], default=t_carga + 0.5)
    x1_carga = min(tf, t_carga + max(0.3, 1.2 * (fim2 - t_carga)))
    return (0.0, x1_partida), (t_carga - 0.1, x1_carga)


def _dec(x, y, n=25000):
    if len(x) <= n:
        return x, y
    passo = int(np.ceil(len(x) / n))
    return x[::passo], y[::passo]


def figura_foc(t, velocidade_rpm, conjugado, motor, t_carga, tf, titulo, janela, eventos_mostrados,
               largura_px=LARGURA_PX, altura_px=ALTURA_PX, y_extra=None, fonte=None):
    """Subplot velocidade (em cima) x conjugado (embaixo), tempos alinhados e com marcações.

    `eventos_mostrados` é uma lista de índices (0 = entrada em velocidade nominal,
    1 = após a entrada da carga).
    """
    x0, x1 = janela
    largo = (x1 - x0) > 0.6 * tf
    fonte = fonte or (9 if largo else 11)
    eventos = _eventos(motor, t_carga, tf)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06)
    m = (t >= x0) & (t <= x1)
    linhas = (
        (1, "velocidade", velocidade_rpm, COR_VELOCIDADE, "Velocidade (RPM)", (3, 1)),
        (2, "conjugado", conjugado, COR_CONJUGADO, "Conjugado (N·m)", (3, 2)),
    )
    for row, grandeza, bruto, cor, rotulo_y, casas in linhas:
        ys, analises = _analise(t, bruto, grandeza, eventos)
        xr, yr = _dec(t[m], bruto[m])
        xs, yv = _dec(t[m], ys[m])
        fig.add_trace(go.Scatter(x=xr, y=yr, name="Sinal bruto", line=dict(color=cor, width=1),
                                 opacity=0.35, showlegend=row == 1, legendgroup="bruto"), row=row, col=1)
        fig.add_trace(go.Scatter(x=xs, y=yv, name=f"Média móvel ({an.SUAVIZACAO_S * 1000:.0f} ms)",
                                 line=dict(color=cor, width=2.5), showlegend=row == 1,
                                 legendgroup="suave"), row=row, col=1)
        y_lim = [float(np.min(yv)), float(np.max(yv))] + list((y_extra or {}).get(row, []))
        eixo = "x" if row == 1 else "x2"
        eixo_y = "y" if row == 1 else "y2"

        for k in eventos_mostrados:
            ev, res = analises[k]
            a, b = max(ev.t_ini, x0), min(ev.t_fim, x1)
            fig.add_shape(type="line", x0=a, x1=b, y0=res["ref"], y1=res["ref"], row=row, col=1,
                          line=dict(color="black", dash="dash", width=1.5))
            for nivel in (res["tubo_sup"], res["tubo_inf"]):
                fig.add_shape(type="line", x0=a, x1=b, y0=nivel, y1=nivel, row=row, col=1,
                              line=dict(color="gray", dash="dot", width=1.5))
            y_lim += [res["tubo_inf"], res["tubo_sup"]]

            def ponto(x, y, nome, cor_p, simbolo, ax, ay, texto):
                if not (x0 <= x <= x1):
                    return False
                if (x - x0) / (x1 - x0) > 0.55:
                    ax = -abs(ax) - 40
                fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers", name=nome, showlegend=False,
                                         marker=dict(color=cor_p, size=10, symbol=simbolo,
                                                     line=dict(color="white", width=1))), row=row, col=1)
                fig.add_annotation(x=x, y=y, xref=eixo, yref=eixo_y, text=texto, showarrow=True,
                                   arrowhead=2, ax=ax, ay=ay, font=dict(size=fonte, color=cor_p),
                                   bgcolor="rgba(255,255,255,0.88)", bordercolor=cor_p)
                return True

            def valor(tt, yy):
                return an._rotulo(grandeza, casas, tt, yy)

            rot_pk = "Máx. sobressinal" if res["ha_sobressinal"] else "Máx. atingido"
            notas = []
            if not ponto(res["t_pk"], res["y_pk"], rot_pk, an.COR_PICO, "circle", 60, -45,
                         f"{rot_pk} ({res['sobressinal_pct']:+.1f}%)<br>{valor(res['t_pk'], res['y_pk'])}"):
                notas.append(f"{rot_pk} ({res['sobressinal_pct']:+.1f}%): {valor(res['t_pk'], res['y_pk'])}")
            if res["t_acom"] is not None:
                ok = ponto(res["t_acom"], res["y_acom"], "Acomodação", an.COR_ACOMODACAO, "square", 60, 50,
                           f"Acomodação em {res['tempo_acom']:.3f} s<br>{valor(res['t_acom'], res['y_acom'])}")
                if not ok:
                    notas.append(f"Acomodação em {res['tempo_acom']:.3f} s ({valor(res['t_acom'], res['y_acom'])})")
            else:
                notas.append("Não acomoda no tubo ±5%")
            if not ponto(res["t_reg"], res["y_reg"], "Regime", an.COR_REGIME, "diamond", -70, -50,
                         f"Regime permanente<br>{valor(res['t_reg'], res['y_reg'])}"):
                notas.append(f"Regime permanente: {valor(res['t_reg'], res['y_reg'])}")
            if res["t_sub0"] is not None:
                for xv, rot, lado in ((res["t_sub0"], "início da subida", "top left"),
                                      (res["t_sub1"], "fim da subida", "top right")):
                    if x0 <= xv <= x1:
                        fig.add_vline(x=xv, row=row, col=1, line=dict(color=an.COR_SUBIDA, width=1.5),
                                      annotation_text=f"{rot} {xv:.3f} s", annotation_position=lado,
                                      annotation_font=dict(color=an.COR_SUBIDA, size=fonte - 1))
                if not (x0 <= res["t_sub0"] <= x1 and x0 <= res["t_sub1"] <= x1):
                    notas.append(f"Subida 10–90%: {res['t_sub0']:.3f} → {res['t_sub1']:.3f} s "
                                 f"({res['tempo_subida']:.3f} s)")
            if notas:
                fig.add_annotation(xref=f"{eixo} domain", yref=f"{eixo_y} domain", x=0.995,
                                   y=0.04 + 0.2 * k, xanchor="right", showarrow=False,
                                   text="<br>".join(notas), align="right",
                                   font=dict(size=fonte, color=an.COR_REGIME),
                                   bgcolor="rgba(255,255,255,0.88)", bordercolor=an.COR_REGIME)

        pad = 0.18 * (max(y_lim) - min(y_lim) or 1.0)
        fig.update_yaxes(range=[min(y_lim) - pad, max(y_lim) + pad], title_text=rotulo_y, row=row, col=1)

    legendas = (
        ("Referência", dict(color="black", dash="dash", width=1.5)),
        ("Tubo de acomodação ±5%", dict(color="gray", dash="dot", width=1.5)),
        ("Subida 10–90%", dict(color=an.COR_SUBIDA, width=1.5)),
    )
    for nome, linha in legendas:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=nome, line=linha), row=1, col=1)
    for nome, cor_p, simbolo in (("Máx. sobressinal", an.COR_PICO, "circle"),
                                 ("Acomodação", an.COR_ACOMODACAO, "square"),
                                 ("Regime permanente", an.COR_REGIME, "diamond")):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=nome,
                                 marker=dict(color=cor_p, size=10, symbol=simbolo)), row=1, col=1)

    fig.update_xaxes(range=[x0, x1])
    fig.update_xaxes(title_text="Tempo (s)", row=2, col=1)
    fig.update_layout(title=dict(text=titulo, font=dict(size=18)), width=largura_px, height=altura_px,
                      legend=dict(orientation="h", yanchor="top", y=-0.07, x=0, font=dict(size=13)),
                      margin=dict(t=70, b=90, l=80, r=30), font=dict(family="Arial"))
    return fig
