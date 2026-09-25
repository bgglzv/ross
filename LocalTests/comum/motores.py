"""Definição dos dois motores e dos parâmetros de simulação dos testes de 60 Hz.

Motor pequeno (P): motor de 1,5 hp dos tutoriais oficiais (tutorial_motor_part_1/2/3).
Motor grande (G): MIT M-C-5283001 (REPLAN), datasheet I-FD-5270.00-52313-712-BI4-102.

Os parâmetros elétricos e de simulação são exatamente os usados nos ensaios
anteriores, para que a comparação com o código "suspeito" seja justa.
"""

from dataclasses import dataclass

import numpy as np

from ross.motors.motor_element import MotorElement
from ross.units import Q_


@dataclass(frozen=True)
class Simulacao:
    nome: str
    tf: float               # tempo total [s]
    dt: float               # passo de avaliação [s]
    t_carga: float          # instante do degrau de carga nominal [s]
    rampa: float            # rampa de aceleração até a referência [s]
    frequencia_chaveamento: object  # pint.Quantity
    time_step: object       # passo interno (None = Ts/200, padrão da biblioteca)
    time_step_dol: float    # passo interno do acionamento direto (sem chaveamento)
    zoom_antes: float       # janela de zoom antes da carga [s]
    zoom_depois: float      # janela de zoom depois da carga [s]

    def vetor_tempo(self):
        return np.arange(0.0, self.tf + self.dt, self.dt)


SIM_PEQUENO = Simulacao(
    nome="Motor de pequeno porte (1,5 hp)",
    tf=3.0,
    dt=1e-3,
    t_carga=1.5,
    rampa=0.6667,
    frequencia_chaveamento=Q_(5000.0, "Hz"),
    time_step=1e-5,
    time_step_dol=1e-5,
    zoom_antes=0.1,
    zoom_depois=0.2,
)

SIM_GRANDE = Simulacao(
    nome="Motor de grande porte (M-C-5283001)",
    tf=24.0,
    dt=1e-3,
    t_carga=16.0,
    rampa=8.0,
    frequencia_chaveamento=Q_(5000.0, "Hz"),
    time_step=None,
    time_step_dol=1e-4,
    zoom_antes=0.5,
    zoom_depois=1.0,
)

FREQ_REFERENCIA_HZ = 60.0


def motor_pequeno():
    """Motor de 1,5 hp / 127 V / 60 Hz / 4 polos / 1710 RPM."""
    return MotorElement(
        n=0,
        tag="P_1p5hp",
        power_nom=Q_(1.5, "hp"),
        voltage_nom=127.0,
        speed_nom=Q_(1710.0, "RPM"),
        frequency_nom=Q_(60.0, "Hz"),
        n_poles=4,
        stator_resistance=2.5,
        rotor_resistance=1.8,
        stator_reactance=1.3,
        rotor_reactance=1.3,
        mutual_reactance=43.08,
        Ip_motor=0.0372,
        viscosity_coeff=0.0,
        Ip_load=0.0,
        voltage_net=127.0,
        frequency_net=Q_(60.0, "Hz"),
    )


def _pu_para_ohm(r1, x1, r2, x2, xm, tensao_linha, corrente_nominal):
    s_base = np.sqrt(3.0) * tensao_linha * corrente_nominal
    z_base = tensao_linha**2 / s_base
    return {
        "r1": r1 * z_base,
        "X1": x1 * z_base,
        "r2": r2 * z_base,
        "X2": x2 * z_base,
        "Xm": xm * z_base,
        "tensao_fase": tensao_linha / np.sqrt(3.0),
    }


def motor_grande():
    """MIT M-C-5283001: 2474 kW / 4000 V / 60 Hz / 4 polos / 1791 RPM."""
    p = _pu_para_ohm(0.005, 0.131, 0.005, 0.105, 3.363, 4000.0, 422.7)
    return MotorElement(
        n=0,
        tag="G_M-C-5283001",
        power_nom=2474e3,
        voltage_nom=p["tensao_fase"],
        speed_nom=Q_(1791.0, "RPM"),
        frequency_nom=Q_(60.0, "Hz"),
        n_poles=4,
        stator_resistance=p["r1"],
        rotor_resistance=p["r2"],
        stator_reactance=p["X1"],
        rotor_reactance=p["X2"],
        mutual_reactance=p["Xm"],
        Ip_motor=57.5,
        viscosity_coeff=0.0,
        Ip_load=0.0,
        voltage_net=p["tensao_fase"],
        frequency_net=Q_(60.0, "Hz"),
    )
