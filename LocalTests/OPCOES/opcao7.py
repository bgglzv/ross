"""Opção 7 — Controle digital: a malha executa uma vez por período de chaveamento.

No FOC da biblioteca, `get_current_state` roda a cada passo de simulação e usa a
corrente instantânea (com o ripple do chaveamento). Num acionamento real, a
malha é discreta: a corrente é amostrada de forma síncrona com o PWM (aqui, no
vale da portadora, onde o ripple de um PWM simétrico é o valor médio), a malha
roda uma vez por período de chaveamento (Ts) e as tensões de referência ficam
seguradas (retentor de ordem zero) até a próxima amostra. Só o modulador
continua rodando a cada passo.

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s,
barramento padrão (1,35 × V_linha), sintonia, limites e anti-windup da
biblioteca intactos (integradores avançam com Ts). A biblioteca não é alterada.

Aproximação: o ângulo do fluxo é integrado com Ts a cada amostra e o vetor de
tensão é segurado em coordenadas estacionárias; não há compensação do atraso
computacional nem do retentor (o que os acionamentos reais costumam fazer).

    python opcao7.py <passo_s>
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
from ross.units import Q_

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "opcao7_dados"
FIGURAS = PASTA / "opcao7_figuras"
MULTIPLO_CORRENTE = 3.0


class FOCDigital(InverterFOC):
    """FOC com malha executada uma vez por período de chaveamento e referências seguradas."""

    instancias = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registro_t = []
        self.registro_razao = []
        self._capturando = False
        self._referencias = (0.0, 0.0, 0.0)
        self._w_sync = 0.0
        FOCDigital.instancias.append(self)

    def _svpwm(self, t, va_ref, vb_ref, vc_ref):
        if self._capturando:
            self._referencias = (va_ref, vb_ref, vc_ref)
            return 0.0, 0.0, 0.0
        return super()._svpwm(t, va_ref, vb_ref, vc_ref)

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        state = self.control_state
        n = state["n_samples"]
        if (state["carrier_index"] - 1) % n == 0:
            err_w = self.speed_control(t, frequency_ref) - rotor_speed
            iqs_ref_unsat = self.kp_w * err_w + self.ki_w * state["int_err_w"]
            self.registro_t.append(t)
            self.registro_razao.append(abs(iqs_ref_unsat) / (MULTIPLO_CORRENTE * self.Is_nom))
            self._capturando = True
            self._w_sync, _, _, _ = super().get_current_state(
                t, dt * n, rotor_speed, ia, ib, ic, frequency_ref)
            self._capturando = False
        van, vbn, vcn = super()._svpwm(t, *self._referencias)
        return self._w_sync, van, vbn, vcn


def simular(passo):
    sim = motores.SIM_PEQUENO
    motor = motores.motor_pequeno()
    t = sim.vetor_tempo()
    print(f"Simulando FOC digital (uma vez por chaveamento), passo interno {passo:g} s "
          f"({2e-4 / passo:.0f} amostras por período)...")
    t0 = time.perf_counter()
    r, t_reg, razao = co.simular_foc(motor, t, sim.rampa, sim.t_carga, sim.frequencia_chaveamento, passo,
                                     Q_(motores.FREQ_REFERENCIA_HZ, "Hz"), inversor_classe=FOCDigital)
    print(f"  concluído em {time.perf_counter() - t0:.1f} s")
    os.makedirs(DADOS, exist_ok=True)
    np.savez_compressed(DADOS / f"passo_{passo:g}.npz", t=r.t, velocidade_rpm=r.speed * 60 / (2 * np.pi),
                        conjugado=r.electric_torque, corrente_a=r.currents["a"])
    est = co.estatisticas_saturacao(t_reg, razao, sim.rampa, sim.t_carga)
    est.update(passo=passo, fator=1.35, conjugado_minimo=float(np.min(r.electric_torque)),
               conjugado_maximo=float(np.max(r.electric_torque)),
               corrente_pico_a=float(np.max(np.abs(r.currents["a"]))))
    (DADOS / f"passo_{passo:g}.json").write_text(json.dumps(est, indent=2))
    print(json.dumps(est, indent=2))


if __name__ == "__main__":
    simular(float(sys.argv[1]))
