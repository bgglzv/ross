"""inverter_foc_adaptativo.py — Esquema de sintonia adaptativa (2 estados).

Estende `InverterFOCNovo` (`inverter_foc_novo.py`) com uma máquina de dois
estados que alterna a sintonia da malha de velocidade e a resolução de
chaveamento conforme a condição observada, em vez de usar uma única
sintonia fixa o tempo todo:

    ESTADO "regime" — condição detectada: o torque (aproximado pela
    corrente iqs medida, proporcional a ele) ficou com o valor RMS
    variando no máximo `steady_state_rms_tol` (padrão 5%) ao longo dos
    últimos `steady_state_cycles` (padrão 20) períodos de chaveamento.
    Ação: a frequência de chaveamento é multiplicada por
    `steady_state_freq_multiplier` (padrão 3x) — o período de chaveamento
    (`Ts`) menor reduz diretamente a amplitude do ripple de corrente/torque
    (ver nota de investigação no final de `inverter_foc_novo.py`: variar os
    GANHOS da malha de corrente, sozinho, não reduziu o ripple; ele é
    dominado pela própria discretização de chaveamento, então a alavanca
    que funciona é a frequência de chaveamento em si). Os ganhos da malha
    de velocidade voltam para o conjunto "normal" (mesma sintonia validada
    em `InverterFOCNovo`).

    ESTADO "transitório" — condição detectada: a referência de corrente de
    torque (`iqs_ref`, a saída do PI de velocidade — é literalmente "o
    valor de referência" que o controlador está impondo à malha de
    corrente) mudou mais que `transient_ref_tol` (padrão 10%, em relação a
    `iqs_max`) numa janela de `transient_window_s`. Note que isso NÃO é o
    mesmo que "o erro de velocidade mudou": numa primeira versão deste
    módulo o gatilho usava o erro de velocidade, e ele nunca disparava no
    instante de um degrau de carga bem rejeitado — a malha reage rápido o
    bastante para a velocidade não desviar muito, mesmo que o torque
    comandado já tenha saltado fortemente. `iqs_ref` captura os dois casos
    (degrau de carga OU de referência de velocidade) de forma unificada,
    porque é exatamente essa variável que "pede" o torque extra em ambos.
    Ação: a frequência de chaveamento volta ao valor base
    (`Ts_normal`) — a malha de corrente precisa da resolução plena para
    reagir rápido — e os ganhos da malha de velocidade trocam para o
    conjunto "transitório", com uma razão BWp_w/BWi_w mais alta
    (`transient_speed_i_ratio`, padrão 13) para reduzir o sobressinal
    teórico do modelo linear de ~6,9% (razão 8, valor da regra "normal")
    para ~5% — ver a derivação em `_overshoot_pct_linear` abaixo.

Fora desses dois estados (ex.: durante a rampa de partida, ainda não
caracterizada como "regime" nem como um evento transitório abrupto), usa a
sintonia "normal" de `InverterFOCNovo` e a frequência de chaveamento base.

Este módulo reimplementa (copia e modifica) o corpo de
`InverterFOC.get_current_state`, porque a detecção de regime precisa da
corrente `iqs` medida a cada passo, que o método original calcula
internamente e não expõe.

Não é executado diretamente — importado pelos scripts de teste.
"""

import numpy as np

from ross.motors.utils import clarke_transform, park_transform, inverse_clarke_transform

from inverter_foc_novo import InverterFOCNovo, compute_speed_bandwidths
from ross.units import check_units


def _overshoot_pct_linear(r):
    """Sobressinal percentual teórico do modelo linear do laço mecânico
    (dois polos reais em `-2*pi*BWp_w` e `-2*pi*BWi_w`, r = BWp_w/BWi_w)
    após um degrau de torque de carga — ver a derivação completa no
    histórico de investigação desta sessão. Independente de J e da largura
    de banda absoluta, só depende de `r`. Usado apenas para escolher
    `transient_speed_i_ratio`, não para prever o comportamento real (que
    inclui ripple de chaveamento, saturação e anti-windup — todos fora
    deste modelo simplificado).
    """
    if r <= 1:
        raise ValueError("r deve ser > 1")
    t_star = 2 * np.log(r) / (r - 1)
    ratio = 1 - (r / (r - 1)) * np.exp(-r * t_star) + (1 / (r - 1)) * np.exp(-t_star)
    return (ratio - 1) * 100.0


class InverterFOCAdaptativo(InverterFOCNovo):
    """`InverterFOCNovo` com sintonia adaptativa de 2 estados (ver docstring
    do módulo).

    Parameters
    ----------
    (mesmos parâmetros de `InverterFOCNovo`, mais:)
    steady_state_cycles : int, optional
        Nº de períodos de chaveamento usados para avaliar a estabilidade
        do RMS do torque (proxy: `iqs` medido). Default 20.
    steady_state_rms_tol : float, optional
        Variação relativa máxima, `(max-min)/média`, do RMS por ciclo
        dentro da janela acima, para considerar "em regime". Default 0.05.
    steady_state_freq_multiplier : float, optional
        Fator de multiplicação da frequência de chaveamento no estado de
        regime. Default 3.0.
    transient_ref_tol : float, optional
        Variação mínima de `iqs_ref` (referência de corrente de torque),
        em fração de `iqs_max = 3 x Is_nom`, dentro de `transient_window_s`,
        para caracterizar um evento transitório. Default 0.10.
    transient_window_s : float, optional
        Janela de tempo usada para medir a variação da referência de
        velocidade. Default 0.005 (5 ms).
    transient_speed_i_ratio : float, optional
        `speed_i_ratio` (ver `compute_speed_bandwidths`) usado no estado
        transitório — mais alto que o "normal" (default 8) para reduzir o
        sobressinal teórico linear a ~5%. Default calibrado
        analiticamente: 13.0 (ver `_overshoot_pct_linear`).
    """

    @check_units
    def __init__(
        self,
        voltage_dc,
        frequency_s,
        voltage_nom,
        frequency_nom,
        n_poles,
        speed_nom,
        torque_nom,
        stator_resistance,
        rotor_resistance,
        stator_reactance,
        rotor_reactance,
        mutual_reactance,
        Ip_motor,
        time_ramp=1.0,
        frequency_ref=None,
        speed_dip_fraction=0.001,
        speed_i_ratio=8.0,
        current_trip_multiple=3.6,
        steady_state_cycles=20,
        steady_state_rms_tol=0.05,
        steady_state_freq_multiplier=3.0,
        transient_ref_tol=0.10,
        transient_window_s=0.005,
        transient_speed_i_ratio=13.0,
    ):
        super().__init__(
            voltage_dc,
            frequency_s,
            voltage_nom,
            frequency_nom,
            n_poles,
            speed_nom,
            torque_nom,
            stator_resistance,
            rotor_resistance,
            stator_reactance,
            rotor_reactance,
            mutual_reactance,
            Ip_motor,
            time_ramp=time_ramp,
            frequency_ref=frequency_ref,
            speed_dip_fraction=speed_dip_fraction,
            speed_i_ratio=speed_i_ratio,
            current_trip_multiple=current_trip_multiple,
        )

        # Conjunto "normal" (o que o InverterFOCNovo ja calculou acima)
        self.kp_w_normal = self.kp_w
        self.ki_w_normal = self.ki_w

        # Conjunto "transitorio" — mais amortecido (r=13 -> ~5% de
        # sobressinal teorico no modelo linear, contra ~6.9% de r=8)
        BWp_w_t, BWi_w_t, _ = compute_speed_bandwidths(
            Ip_motor,
            self.speed_nom,
            float(torque_nom),
            speed_dip_fraction=speed_dip_fraction,
            speed_i_ratio=transient_speed_i_ratio,
        )
        J = float(Ip_motor)
        KL = float(torque_nom) / (self.np_pairs * self.speed_nom)
        self.kp_w_transiente = J * 2 * np.pi * (BWp_w_t + BWi_w_t) - KL
        self.ki_w_transiente = J * 4 * (np.pi**2) * BWp_w_t * BWi_w_t
        self.transient_speed_i_ratio = transient_speed_i_ratio
        self.transient_overshoot_pct_teorico = _overshoot_pct_linear(transient_speed_i_ratio)

        # Tempo mínimo de permanência no modo "transiente" antes de deixar
        # sair para "regime"/"normal" — sem isso, a janela curta do
        # detector de regime (steady_state_cycles ciclos de chaveamento,
        # poucos ms) pode indicar "RMS estável" bem antes de o transitório
        # mecânico realmente ter atingido seu pico, revertendo a sintonia
        # amortecida no pior momento possível. 3 constantes de tempo do
        # polo mais lento (BWi_w) é uma regra prática (>95% do transitório
        # dominante já decorrido).
        self.transient_min_duration_s = 3.0 / (2 * np.pi * BWi_w_t)

        # Frequencia de chaveamento: base (normal/transitorio) e "regime"
        self.Ts_normal = self.Ts
        self.Ts_regime = self.Ts / steady_state_freq_multiplier
        self.steady_state_freq_multiplier = steady_state_freq_multiplier

        self.steady_state_cycles = steady_state_cycles
        self.steady_state_rms_tol = steady_state_rms_tol
        self.transient_ref_tol = transient_ref_tol
        self.transient_window_s = transient_window_s

        self.mode = "normal"   # "normal" | "transiente" | "regime"
        self.mode_switch_log = []   # [(t, modo_novo), ...] para depuracao/graficos

    def initialize_control_state(self, dt, theta_0=0.0):
        super().initialize_control_state(dt, theta_0)
        cs = self.control_state
        cs["cycle_sq_sum"] = 0.0
        cs["cycle_n"] = 0
        cs["cycle_len"] = max(1, int(round(self.Ts_normal / dt)))
        cs["rms_buffer"] = []
        cs["iqs_ref_hist"] = []   # [(t, iqs_ref), ...] só a janela recente
        # Estado PERSISTENTE (não recalculado do zero a cada passo!) — só
        # é atualizado quando um ciclo de chaveamento se fecha; nos passos
        # intermediários mantém o último valor conhecido. Sem isso, a
        # máquina de estados via "regime_estavel = False" default a cada
        # chamada e cai fora do regime quase imediatamente (chattering).
        cs["regime_estavel"] = False
        cs["mode_entry_time"] = 0.0

    def _update_mode(self, t, err_w, iqs_ref, iqs):
        cs = self.control_state

        # --- 1. Atualiza o RMS do ciclo de chaveamento atual (proxy de torque) ---
        # `regime_estavel` só é reavaliado quando um ciclo se fecha; nos
        # demais passos, mantém o último valor (persistente em `cs`).
        # Histerese: exige uma variação MAIOR (2x a tolerância de entrada)
        # para sair do regime, evitando chattering na fronteira do critério
        # (sem isso, uma variação de RMS oscilando em torno de 5% liga e
        # desliga o modo "regime" a cada ciclo de chaveamento).
        cs["cycle_sq_sum"] += iqs**2
        cs["cycle_n"] += 1
        if cs["cycle_n"] >= cs["cycle_len"]:
            rms = np.sqrt(cs["cycle_sq_sum"] / cs["cycle_n"])
            cs["cycle_sq_sum"] = 0.0
            cs["cycle_n"] = 0
            buf = cs["rms_buffer"]
            buf.append(rms)
            if len(buf) > self.steady_state_cycles:
                buf.pop(0)
            if len(buf) == self.steady_state_cycles:
                media = np.mean(buf)
                variacao = (max(buf) - min(buf)) / media if media > 1e-9 else 0.0
                limiar = (
                    self.steady_state_rms_tol
                    if not cs["regime_estavel"]
                    else self.steady_state_rms_tol * 2.0
                )
                cs["regime_estavel"] = variacao <= limiar
            else:
                cs["regime_estavel"] = False
        regime_estavel = cs["regime_estavel"]

        # --- 2. Detecta evento transitorio: iqs_ref (referência de torque
        # comandada pelo PI de velocidade) mudando mais que a tolerância,
        # em relação ao limite de corrente iqs_max ---
        hist = cs["iqs_ref_hist"]
        hist.append((t, iqs_ref))
        while hist and t - hist[0][0] > self.transient_window_s:
            hist.pop(0)
        iqs_max = 3.0 * self.Is_nom
        iqs_ref_change = abs(iqs_ref - hist[0][1]) / iqs_max if hist else 0.0
        evento_transitorio = iqs_ref_change > self.transient_ref_tol

        # --- 3. Maquina de estados ---
        # Um novo evento transitório sempre tem prioridade (reentra e
        # reinicia a contagem do tempo mínimo). Sair do modo "transiente"
        # só é permitido depois de `transient_min_duration_s` — ver
        # docstring de `transient_min_duration_s` no __init__ — mesmo que
        # o RMS já indique "regime estável" antes disso (motivo: a janela
        # curta do detector de regime pode achar "RMS estável" no meio do
        # transitório, bem antes de o pico realmente acontecer).
        tempo_no_modo = t - cs["mode_entry_time"]

        if evento_transitorio:
            novo_modo = "transiente"
        elif self.mode == "transiente":
            ainda_no_periodo_minimo = tempo_no_modo < self.transient_min_duration_s
            novo_modo = "transiente" if (ainda_no_periodo_minimo or not regime_estavel) else "regime"
        elif regime_estavel:
            novo_modo = "regime"
        else:
            # nem transitório nem regime estável (ex.: durante a rampa,
            # antes de o RMS se estabilizar) — sintonia "normal".
            novo_modo = "normal"

        if novo_modo != self.mode:
            self.mode_switch_log.append((t, novo_modo))
            cs["mode_entry_time"] = t

            kp_w_antigo, ki_w_antigo = self.kp_w, self.ki_w
            if novo_modo == "transiente":
                kp_w_novo, ki_w_novo = self.kp_w_transiente, self.ki_w_transiente
                self.Ts = self.Ts_normal
            elif novo_modo == "regime":
                kp_w_novo, ki_w_novo = self.kp_w_normal, self.ki_w_normal
                self.Ts = self.Ts_regime
            else:  # "normal"
                kp_w_novo, ki_w_novo = self.kp_w_normal, self.ki_w_normal
                self.Ts = self.Ts_normal

            # Transferência sem solavancos ("bumpless transfer"): sem isso,
            # trocar kp_w/ki_w mantendo o integrador como estava produz um
            # salto instantâneo na saída do PI (kp_w*err_w + ki_w*int_err_w)
            # — foi isso, não uma limitação do modelo linear, que explicava
            # o sobressinal de ~43% observado nos primeiros testes deste
            # esquema (bem PIOR que os ~19,7% da sintonia fixa "antiga",
            # mesmo a sintonia "transiente" sendo mais amortecida). Reajusta
            # o integrador para que a saída não pule no instante da troca.
            saida_antiga = kp_w_antigo * err_w + ki_w_antigo * cs["int_err_w"]
            if abs(ki_w_novo) > 1e-12:
                cs["int_err_w"] = (saida_antiga - kp_w_novo * err_w) / ki_w_novo

            self.kp_w, self.ki_w = kp_w_novo, ki_w_novo
            self.mode = novo_modo

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        """Cópia modificada de `InverterFOC.get_current_state` — insere a
        atualização da máquina de estados adaptativa (`_update_mode`) logo
        após calcular `iqs`/`ids` medidos, ponto em que o método original
        não expõe esses valores. Ver docstring do módulo."""
        if self.tripped:
            return self.np_pairs * rotor_speed, 0.0, 0.0, 0.0

        current_limit = self.current_trip_multiple * self.Is_nom
        if max(abs(ia), abs(ib), abs(ic)) > current_limit:
            self.tripped = True
            self.trip_time = t
            return self.np_pairs * rotor_speed, 0.0, 0.0, 0.0

        state = self.control_state

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        u_prop = self.kp_w * err_w
        u_int = self.ki_w * state["int_err_w"]
        iqs_ref_unsat = u_prop + u_int

        iqs_max = 3.0 * self.Is_nom
        iqs_ref = np.clip(iqs_ref_unsat, -iqs_max, iqs_max)

        wsl = (1 / self.taur) * (iqs_ref / self.ids_ref)
        w_sync = wsl + self.np_pairs * rotor_speed

        state["theta"] += w_sync * dt

        i_alpha, i_beta = clarke_transform(ia, ib, ic)
        d_std, q_std = park_transform(i_alpha, i_beta, state["theta"])
        iqs, ids = d_std, -q_std

        # --- Ponto de instrumentação: atualiza a máquina de estados adaptativa ---
        self._update_mode(t, err_w, iqs_ref, iqs)

        err_iqs = iqs_ref - iqs
        vqs_ref = self.kp_iqs * err_iqs + self.Rs * iqs + self.Lss * w_sync * ids

        err_ids = self.ids_ref - ids
        state["int_err_ids"] += err_ids * dt

        vds_ref = (
            self.kp_ids * err_ids
            + self.ki_ids * state["int_err_ids"]
            + self.Rs * ids
            - self.Lsline * w_sync * iqs
        )

        Vmax = self.voltage_dc / np.sqrt(3)
        Vref = np.sqrt(vqs_ref**2 + vds_ref**2)
        saturated = Vref > Vmax
        if saturated:
            scale = Vmax / Vref
            vqs_ref *= scale
            vds_ref *= scale

        current_saturated = abs(iqs_ref_unsat) > iqs_max
        any_saturated = saturated or current_saturated
        if (not any_saturated) or (np.sign(err_w) != np.sign(iqs_ref_unsat)):
            state["int_err_w"] += err_w * dt

        iqs_ref = self.kp_w * err_w + self.ki_w * state["int_err_w"]

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return w_sync, van, vbn, vcn
