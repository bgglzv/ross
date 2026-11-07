"""Variante do InverterFOC com `ki_iqs` incluído.

A malha de iqs (corrente produtora de torque) na biblioteca, hoje, é só
proporcional + feedforward de desacoplamento (`Rs*iqs + Lss*w_sync*ids`),
sem integrador — diferente de `ids` e de `w`, que são PI completos. Como o
termo de desacoplamento escala com `w_sync` (cresce quanto mais perto de
60 Hz o acionamento está), qualquer resíduo de cancelamento entra
amplificado e a malha, sendo só P, não tem como "escoar" esse erro — o que
é consistente com o ripple de conjugado crescente observado ao se aproximar
de 60 Hz nos dois motores.

`InverterFOCv2` adiciona `ki_iqs`, calculado com o mesmo padrão de banda já
usado em `ids` (banda do integrador = banda do proporcional / 8):

    BWi_iqs = BWp_iqs / 8
    ki_iqs  = Lsline * 4*pi**2 * BWp_iqs * BWi_iqs

Uma primeira rodada sem anti-windup piorou o ripple na maioria dos casos
(ciclo-limite: a malha de iqs satura com frequência — limite de corrente
iqs_max e limite de tensão de barramento Vmax — porque sua referência varia
bastante, ao contrário de ids, cuja referência é quase constante em
regime). Esta versão trava state["int_err_iqs"] durante saturação de
tensão, mesmo mecanismo que a malha de w já usa para state["int_err_w"]:
não integra quando a tensão está saturada, a não ser que o sinal do erro
já esteja puxando o comando de volta para fora da saturação.

Escopo desta pasta: ki_iqs + esse anti-windup (nenhuma outra mudança do BW
method — sem desvincular Kp/Ki via (zeta, wn), sem escalar banda com a
frequência de operação, sem checagem de polos discretos, sem anti-windup em
ids). Implementado como subclasse, sem tocar `ross/motors/motor_drive.py`,
para não afetar as demais simulações do estudo enquanto essa variante é
avaliada isoladamente.
"""

import numpy as np

from ross.motors.motor_drive import InverterFOC


class InverterFOCv2(InverterFOC):
    """`InverterFOC` com integrador na malha de iqs (`ki_iqs`).

    Mesmos parâmetros de `InverterFOC.__init__`. Todo o resto do método de
    controle (`get_current_state`) é idêntico ao da classe-base; a única
    diferença é a adição do termo integral em `vqs_ref`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        frequency_s_hz = self.frequency_s / (2 * np.pi)
        BWp_iqs = frequency_s_hz / 8
        BWi_iqs = BWp_iqs / 8
        self.ki_iqs = self.Lsline * 4 * (np.pi**2) * BWp_iqs * BWi_iqs

    def initialize_control_state(self, dt, theta_0=0.0):
        super().initialize_control_state(dt, theta_0)
        self.control_state["int_err_iqs"] = 0.0

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        """Igual a `InverterFOC.get_current_state`, exceto por `vqs_ref`
        ganhar o termo integral `ki_iqs * int_err_iqs` (ver módulo), com
        anti-windup gated pela saturação de tensão."""
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

        iqs, ids = d_std, -q_std

        err_iqs = iqs_ref - iqs
        # Integral do passo anterior (state["int_err_iqs"] só é atualizado
        # mais abaixo, depois de sabermos se a tensão saturou neste passo).
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

        # Anti-windup da malha de iqs: mesmo mecanismo já usado para
        # state["int_err_w"] mais abaixo, mas em cima da saturação de
        # tensão (é essa que satura vqs_ref, não o limite de corrente).
        if (not saturated) or (np.sign(err_iqs) != np.sign(vqs_ref_unsat)):
            state["int_err_iqs"] += err_iqs * dt

        current_saturated = abs(iqs_ref_unsat) > iqs_max

        any_saturated = saturated or current_saturated
        if (not any_saturated) or (np.sign(err_w) != np.sign(iqs_ref_unsat)):
            state["int_err_w"] += err_w * dt

        iqs_ref = self.kp_w * err_w + self.ki_w * state["int_err_w"]

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)

        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)

        return w_sync, van, vbn, vcn
