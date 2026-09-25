"""Opção 2 — Limitar a corrente pelo módulo do vetor, com prioridade ao fluxo.

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s.
Em vez de limitar só o eixo q a 3·Is_nom, limita-se o módulo do vetor de corrente
ao mesmo teto (3·Is_nom) e o eixo d recebe a corrente de fluxo que precisa
(prioridade ao fluxo):

    iq_max = sqrt((3·Is_nom)² − ids_ref²)

O resto da malha (sintonia, anti-windup, SVPWM) é idêntico ao da biblioteca; a
biblioteca não é alterada: a subclasse abaixo reescreve só o método de controle.

    python opcao2.py simular <fator_barramento>
    python opcao2.py montar
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
DADOS = PASTA / "opcao2_dados"
FIGURAS = PASTA / "opcao2_figuras"
FATORES = (1.35, 1.414)
MULTIPLO_CORRENTE = 3.0


class FOCModuloVetor(InverterFOC):
    """FOC com limite de corrente aplicado ao módulo do vetor (prioridade ao fluxo)."""

    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registro_t = []
        self.registro_razao = []
        self.iqs_max = float(np.sqrt((MULTIPLO_CORRENTE * self.Is_nom) ** 2 - self.ids_ref**2))
        FOCModuloVetor.instancias.append(self)

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        state = self.control_state

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        u_prop = self.kp_w * err_w
        u_int = self.ki_w * state["int_err_w"]
        iqs_ref_unsat = u_prop + u_int

        iqs_max = self.iqs_max
        iqs_ref = np.clip(iqs_ref_unsat, -iqs_max, iqs_max)
        self.registro_t.append(t)
        self.registro_razao.append(abs(iqs_ref_unsat) / iqs_max)

        wsl = (1 / self.taur) * (iqs_ref / self.ids_ref)
        w_sync = wsl + self.np_pairs * rotor_speed
        state["theta"] += w_sync * dt

        i_alpha, i_beta = clarke_transform(ia, ib, ic)
        d_std, q_std = park_transform(i_alpha, i_beta, state["theta"])
        iqs, ids = d_std, -q_std

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

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)
        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)
        return w_sync, van, vbn, vcn


def simular(fator):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    print(f"Simulando FOC (módulo do vetor) com barramento CC = {fator} x V_linha...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"),
                                     fator_barramento=fator, inversor_classe=FOCModuloVetor)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"fator_{fator}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(fator=fator, iqs_max=FOCModuloVetor.instancias[-1].iqs_max,
               conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"fator_{fator}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        from montar_opcao2 import montar

        montar()
