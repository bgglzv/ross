"""Opção 4 — Anti-windup por retro-cálculo (back-calculation) no PI de velocidade.

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s,
limite de corrente da biblioteca (3·Is_nom), ganhos nativos intactos.

A biblioteca congela o integrador da velocidade sempre que há saturação (de
corrente ou de tensão) no mesmo sentido do erro. A 60 Hz a tensão já está no
limite, então o integrador fica congelado quase o tempo todo. Aqui o integrador
continua atuando e é "puxado" para o valor que o atuador realmente entrega:

    d(int_err_w)/dt = err_w + (iq_ach − iq_ref_sem_limite) / kp_w

que equivale a retro-cálculo com constante de tempo Tt = Ti = kp_w / ki_w. O
valor entregue `iq_ach` é a referência limitada em corrente e, quando a tensão
satura, a corrente q medida (o que o inversor de fato conseguiu impor).
A biblioteca não é alterada: a subclasse reescreve só o método de controle.

    python opcao4.py simular <fator_barramento>
    python opcao4.py montar
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
DADOS = PASTA / "opcao4_dados"
FIGURAS = PASTA / "opcao4_figuras"
FATORES = (1.35, 1.414)
MULTIPLO_CORRENTE = 3.0


class FOCRetroCalculo(InverterFOC):
    """FOC com anti-windup por retro-cálculo no PI de velocidade."""

    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registro_t = []
        self.registro_razao = []
        self.iqs_max = float(MULTIPLO_CORRENTE * self.Is_nom)
        FOCRetroCalculo.instancias.append(self)

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        state = self.control_state

        wref = self.speed_control(t, frequency_ref)
        err_w = wref - rotor_speed

        iqs_ref_unsat = self.kp_w * err_w + self.ki_w * state["int_err_w"]
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
        iq_entregue = iqs_ref
        if saturated:
            scale = Vmax / Vref
            vqs_ref *= scale
            vds_ref *= scale
            iq_entregue = float(np.clip(iqs, -iqs_max, iqs_max))

        state["int_err_w"] += (err_w + (iq_entregue - iqs_ref_unsat) / self.kp_w) * dt

        v_alpha, v_beta = park_transform(vqs_ref, -vds_ref, -state["theta"])
        va_ref, vb_ref, vc_ref = inverse_clarke_transform(v_alpha, v_beta)
        van, vbn, vcn = self._svpwm(t, va_ref, vb_ref, vc_ref)
        return w_sync, van, vbn, vcn


def simular(fator):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    print(f"Simulando FOC (retro-cálculo) com barramento CC = {fator} x V_linha...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento,
                                     sim.time_step, Q_(motores.FREQ_REFERENCIA_HZ, "Hz"),
                                     fator_barramento=fator, inversor_classe=FOCRetroCalculo)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"fator_{fator}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(fator=fator, iqs_max=FOCRetroCalculo.instancias[-1].iqs_max,
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
        linhas.append(("Original (congela o integrador)",
                       json.loads((barramento.DADOS / f"fator_{f}.json").read_text())))
        linhas.append(("Opção 4 (retro-cálculo)", json.loads((DADOS / f"fator_{f}.json").read_text())))
    montar_documento(
        [str(f) for f in FATORES], FIGURAS,
        lambda v, d: f"Opção 4 — Barramento {rotulo(float(v))} × V_linha — {d}",
        lambda v: DADOS / f"fator_{v}.npz", linhas,
        "Opção 4 — Resumo da saturação (FOC, 60 Hz, motor pequeno, rampa de 0,6667 s)",
        PASTA / "Opcao4-Anti-windup-retro-calculo_CC-135x1414.docx")


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        montar()
