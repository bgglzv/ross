"""BW_v6: filtro síncrono na realimentação de iqs/ids — com a janela do
filtro dimensionada pela PRÓPRIA banda de malha de cada motor (regra
geral motor-aware), em vez de um período de chaveamento fixo igual para
qualquer máquina.

Histórico (3 rodadas até chegar nesta regra):

1) Janela fixa = um período de chaveamento (Ts = 1/fs), igual nos dois
   motores: melhorou MIT_G a 55-62 Hz, mas PIOROU MIT_P em toda a faixa
   (30-62 Hz) — o espectro de iq de MIT_P passou a ter um pico dominante
   NOVO perto de fs/2 = 2500 Hz, uma auto-oscilação sub-harmônica.

2) Primeira tentativa de correção: janela de iqs dimensionada pela banda
   de iqs (BWp_iqs) e janela de ids dimensionada pela banda de ids
   (BWp_ids), cada uma independente — T_filt_X = min(Ts, THETA_MAX /
   (pi*BWp_X)). Para MIT_P isso deu n_iqs=105, n_ids=200 (ids continuava
   cheio, pois sua própria banda, 145 Hz, "tolerava" o atraso). RESULTADO:
   a ressonância em fs/2 PERSISTIU quase inalterada (618% de ripple em
   iq). Um teste isolado (variando n_iqs e n_ids separadamente) mostrou a
   causa: a ressonância aparece sempre que n_ids fica perto do período
   cheio, INDEPENDENTE do valor de n_iqs — ou seja, é o atraso em ids,
   não em iqs, que desestabiliza. Faz sentido olhando a equação de
   vqs_ref (a saída da malha RÁPIDA de iqs): ela carrega o termo de
   desacoplamento Lss*w_sync*ids — um ids atrasado entra como disturbio
   atrasado DENTRO da malha de iqs, mesmo que a malha de ids em si (mais
   lenta) não tivesse problema com esse atraso isoladamente.

3) Regra final (esta versão): as duas janelas (iqs e ids) usam o MESMO
   valor, dimensionado pela banda da malha MAIS RÁPIDA — que neste desenho
   é sempre BWp_iqs (kp_iqs/ki_iqs são sempre mais rápidos que kp_ids/
   ki_ids nos dois motores, por construção do BW_v5). Isso evita que um
   atraso grande em QUALQUER um dos dois buffers vaze, via o termo de
   acoplamento cruzado, para dentro da malha mais exigente:

    T_filt = min( Ts , THETA_MAX / (pi * BWp_iqs) )
    (mesmo T_filt usado para o buffer de iqs e para o de ids)

Onde:
  - Ts = 1/fs (período de chaveamento) — teto: nunca maior que um período.
  - BWp_iqs é a banda de malha fechada de iqs que o BW_v5 já calcula
    (motor-aware: vem do polo elétrico da própria planta).
  - THETA_MAX é a única constante nova deste estudo — orçamento de atraso
    de fase (rad) que a malha RÁPIDA tolera na sua própria banda de
    cruzamento. Validado empiricamente por varredura: THETA_MAX=0,2 ainda
    caía na faixa de ressonância para MIT_P (n≈105, ripple de iq ~66% já
    em degradação, mas o ponto crítico é o buffer de ids ficar perto do
    período cheio); THETA_MAX=0,05 manteve os dois motores fora da faixa
    de ressonância (MIT_P: ripple de iq ~43%, igual ao original sem
    filtro; MIT_G: ripple de iq ~36,9% e de torque ~10,3%, quase idêntico
    ao resultado do filtro de período cheio que já funcionava bem para
    essa máquina — 36,5%/9,4%). THETA_MAX = 0.05 rad (~2,9°) é o valor
    adotado.

Resultado numérico desta regra: MIT_P fica com janela de ~26 amostras (de
200) nos dois buffers — bem dentro da faixa seguramente testada (15-50
amostras, todas sem ressonância). MIT_G fica com janela de ~177 amostras
(de 200) — ainda muito perto do período cheio, porque sua banda de malha
(BWp_iqs≈90 Hz) é baixa o bastante para tolerar quase todo o atraso sem
ressoar; o resultado para MIT_G fica a poucos pontos percentuais do
filtro de período cheio original.

iqs_filt/ids_filt (mesma janela, cada um com seu próprio buffer) substituem
iqs/ids em todo lugar que a malha original usava a medição — erro do PI e
termos de desacoplamento feedforward. Ganhos de malha (kp_iqs, ki_iqs,
kp_ids, ki_ids) continuam exatamente os do BW_v5.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v5"))

from inverter_foc_v5 import InverterFOCv5

THETA_MAX = 0.05  # rad — orçamento de atraso de fase na banda de cruzamento da malha mais rápida (iqs)


class InverterFOCv6(InverterFOCv5):
    """`InverterFOCv5` (ganhos motor-aware, inalterados) com média móvel
    de iqs/ids na realimentação — mesma janela para os dois buffers,
    dimensionada pela banda da malha mais rápida (iqs, ver módulo) — em
    vez de um período de chaveamento fixo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        fs_hz = self.frequency_s / (2 * np.pi)
        ts = 1.0 / fs_hz

        t_filt = min(ts, THETA_MAX / (np.pi * self.bwp_iqs_hz))

        self._ts_chaveamento = ts
        self._t_filt = t_filt

    def initialize_control_state(self, dt, theta_0=0.0):
        super().initialize_control_state(dt, theta_0)
        n_filt = max(1, round(self._t_filt / dt))
        self.control_state["n_filt"] = n_filt
        self.control_state["buf_iqs"] = np.zeros(n_filt)
        self.control_state["buf_ids"] = np.zeros(n_filt)
        self.control_state["buf_idx"] = 0

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        """Igual a `InverterFOCv5.get_current_state` (herdado de
        InverterFOCv2), exceto por iqs e ids passarem por uma média móvel
        com a mesma janela (ver módulo) antes de entrar no erro do PI e
        nos termos de desacoplamento."""
        from ross.motors.utils import (
            clarke_transform,
            inverse_clarke_transform,
            park_transform,
        )

        state = self.control_state

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        u_prop = self.kp_w * err_w
        u_int = self.ki_w * state["int_err_w"]
        iqs_ref_unsat = u_prop + u_int

        iqs_max = 3.0 * self.Is_rated
        iqs_ref = np.clip(iqs_ref_unsat, -iqs_max, iqs_max)

        wsl = (1 / self.taur) * (iqs_ref / self.ids_ref)
        w_sync = wsl + self.np_pairs * rotor_speed

        state["theta"] += w_sync * dt

        i_alpha, i_beta = clarke_transform(ia, ib, ic)
        d_std, q_std = park_transform(i_alpha, i_beta, state["theta"])

        iqs_inst, ids_inst = d_std, -q_std

        idx = state["buf_idx"]
        state["buf_iqs"][idx] = iqs_inst
        state["buf_ids"][idx] = ids_inst
        state["buf_idx"] = (idx + 1) % len(state["buf_iqs"])
        iqs = float(state["buf_iqs"].mean())
        ids = float(state["buf_ids"].mean())

        err_iqs = iqs_ref - iqs
        vqs_ref_unsat = (
            self.kp_iqs * err_iqs
            + self.ki_iqs * state["int_err_iqs"]
            + self.Rs * iqs
            + self.Lss * w_sync * ids
        )
        vqs_ref = vqs_ref_unsat

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

        if (not saturated) or (np.sign(err_iqs) != np.sign(vqs_ref_unsat)):
            state["int_err_iqs"] += err_iqs * dt

        current_saturated = abs(iqs_ref_unsat) > iqs_max

        any_saturated = saturated or current_saturated
        if (not any_saturated) or (np.sign(err_w) != np.sign(iqs_ref_unsat)):
            state["int_err_w"] += err_w * dt

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return w_sync, van, vbn, vcn
