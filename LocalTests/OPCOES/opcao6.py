"""Opção 6 — Enfraquecimento de campo (redução do fluxo quando a tensão satura).

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s,
ganhos, limite de corrente (3·Is_nom) e anti-windup da biblioteca intactos.

O teste do barramento mostrou que, a 60 Hz, o controle não tem margem de tensão
(Vdc/√3 fica abaixo do pico de fase nominal) e perde o controle do torque. Aqui o
fluxo de referência é escalado por um fator k_fw ∈ [K_MIN, 1] ajustado por um
integrador lento de tensão:

    d(k_fw)/dt = −(|V_ref|/V_max − V_ALVO) / TAU        se |V_ref| acima do alvo
    d(k_fw)/dt = −(|V_ref|/V_max − V_ALVO) / TAU · GANHO_RECUPERACAO   caso contrário

isto é, o fluxo cai enquanto o vetor de tensão comandado passa de 95% do limite e
volta devagar quando há folga. A corrente de fluxo e o escorregamento do controle
indireto usam ids_ref · k_fw (o escorregamento precisa da mesma corrente de fluxo
que o controle de corrente de fato impõe). A biblioteca não é alterada.

    python opcao6.py simular <fator_barramento>
    python opcao6.py montar
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comum_opcoes as co
from comum import motores
from ross.motors.inverters import InverterFOC
from ross.motors.utils import clarke_transform, inverse_clarke_transform, park_transform
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "opcao6_dados"
FIGURAS = PASTA / "opcao6_figuras"
FATORES = (1.35, 1.414)
MULTIPLO_CORRENTE = 3.0
V_ALVO = 0.95
TAU = 0.05
K_MIN = 0.5
GANHO_RECUPERACAO = 0.2


class FOCEnfraquecimentoCampo(InverterFOC):
    """FOC com redução do fluxo de referência quando o vetor de tensão se aproxima do limite."""

    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registro_t = []
        self.registro_razao = []
        self.registro_kfw = []
        self.iqs_max = float(MULTIPLO_CORRENTE * self.Is_nom)
        self.k_fw = 1.0
        FOCEnfraquecimentoCampo.instancias.append(self)

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        state = self.control_state

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        iqs_ref_unsat = self.kp_w * err_w + self.ki_w * state["int_err_w"]
        iqs_max = self.iqs_max
        iqs_ref = np.clip(iqs_ref_unsat, -iqs_max, iqs_max)
        self.registro_t.append(t)
        self.registro_razao.append(abs(iqs_ref_unsat) / iqs_max)
        self.registro_kfw.append(self.k_fw)

        ids_ref = self.ids_ref * self.k_fw

        wsl = (1 / self.taur) * (iqs_ref / ids_ref)
        w_sync = wsl + self.np_pairs * rotor_speed
        state["theta"] += w_sync * dt

        i_alpha, i_beta = clarke_transform(ia, ib, ic)
        d_std, q_std = park_transform(i_alpha, i_beta, state["theta"])
        iqs, ids = d_std, -q_std

        err_iqs = iqs_ref - iqs
        vqs_ref = self.kp_iqs * err_iqs + self.Rs * iqs + self.Lss * w_sync * ids

        err_ids = ids_ref - ids
        state["int_err_ids"] += err_ids * dt
        vds_ref = (
            self.kp_ids * err_ids
            + self.ki_ids * state["int_err_ids"]
            + self.Rs * ids
            - self.Lsline * w_sync * iqs
        )

        Vmax = self.voltage_dc / np.sqrt(3)
        Vref = np.sqrt(vqs_ref**2 + vds_ref**2)
        excesso = Vref / Vmax - V_ALVO
        taxa = -excesso / TAU
        if excesso <= 0:
            taxa *= GANHO_RECUPERACAO
        self.k_fw = float(np.clip(self.k_fw + taxa * dt, K_MIN, 1.0))

        saturated = Vref > Vmax
        if saturated:
            scale = Vmax / Vref
            vqs_ref *= scale
            vds_ref *= scale

        current_saturated = abs(iqs_ref_unsat) > iqs_max
        any_saturated = saturated or current_saturated
        if (not any_saturated) or (np.sign(err_w) != np.sign(iqs_ref_unsat)):
            state["int_err_w"] += err_w * dt

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)
        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)
        return w_sync, van, vbn, vcn


def simular(fator):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    print(f"Simulando FOC (enfraquecimento de campo) com barramento CC = {fator} x V_linha...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"),
                                     fator_barramento=fator, inversor_classe=FOCEnfraquecimentoCampo)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"fator_{fator}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    inv = FOCEnfraquecimentoCampo.instancias[-1]
    kfw = np.array(inv.registro_kfw)
    vazio = (t_reg >= sim.rampa) & (t_reg < sim.t_carga)
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(fator=fator, iqs_max=inv.iqs_max,
               kfw_minimo=float(kfw.min()), kfw_medio_vazio=float(kfw[vazio].mean()),
               kfw_final=float(kfw[-1]),
               conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"fator_{fator}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


def montar():
    import barramento
    from lado_a_lado import montar_documento

    def rotulo(f):
        return f"{f:.4g}".replace(".", ",")

    linhas = []
    for f in FATORES:
        linhas.append(("Original (fluxo constante)",
                       json.loads((barramento.DADOS / f"fator_{f}.json").read_text())))
        linhas.append(("Opção 6 (enfraquecimento de campo)",
                       json.loads((DADOS / f"fator_{f}.json").read_text())))
    montar_documento(
        [str(f) for f in FATORES], FIGURAS,
        lambda v, d: f"Opção 6 — Barramento {rotulo(float(v))} × V_linha — {d}",
        lambda v: DADOS / f"fator_{v}.npz", linhas,
        "Opção 6 — Resumo da saturação (FOC, 60 Hz, motor pequeno, rampa de 0,6667 s)",
        PASTA / "Opcao6-Enfraquecimento-de-campo_CC-135x1414.docx")


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        montar()
