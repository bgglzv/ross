"""Estudo preliminar: K_IQS deixa de ser uma constante fixa e passa a ser
função de frequency_ref — mantendo toda a estrutura já validada do BW_v5
(teto em fs/8, piso por média geométrica, zeta_iqs=sqrt(2) preservado por
construção, anti-windup) — só a LEI que gera K_IQS muda.

Motivação física: o termo de desacoplamento feedforward que a malha de
iqs precisa compensar (Lss·w_sync·ids) escala linearmente com a
velocidade síncrona, isto é, com frequency_ref. Se a malha precisa
rejeitar um resíduo proporcionalmente maior perto da frequência nominal,
faz sentido que a banda relativa ao polo elétrico da planta (K_IQS) também
cresça com frequency_ref — em vez de ser a mesma em qualquer operação,
como o K_IQS=10 fixo do v5.

Lei testada neste estudo preliminar (a mais simples, diretamente ligada à
motivação acima — proporcional, como o próprio termo de desacoplamento):

    K_IQS(frequency_ref) = K_IQS_NOM * (frequency_ref_hz / frequency_nom_hz)

Com K_IQS_NOM = 10 (o mesmo valor fixo já validado no v5) ancorado em
frequency_nom (60 Hz) — ou seja, a 60 Hz esta lei reproduz exatamente o
v5; abaixo de 60 Hz, K_IQS cai proporcionalmente (malha mais "calma",
testando se isso reduz ainda mais o ripple nas frequências onde o resíduo
a rejeitar já é menor); acima de 60 Hz, K_IQS sobe proporcionalmente.

Importante: diferente do BW_v3 (que escalava ki_iqs diretamente com a
frequência e quebrou o fator de amortecimento), aqui a dependência entra
só em K_IQS, que por sua vez só desloca BWp_iqs — a razão BWi_iqs =
BWp_iqs/8 é recalculada a partir do NOVO BWp_iqs, preservando
zeta_iqs=sqrt(2) automaticamente, qualquer que seja o valor de K_IQS.

K_IDS (malha de ids) permanece fixo em 10, igual ao v5 — escopo deste
estudo é só iqs.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v5"))

from inverter_foc_v5 import InverterFOCv5

FREQ_NOM_HZ = 60.0
K_IQS_NOM = 10.0


def k_iqs_linear(frequency_ref_hz):
    """K_IQS proporcional à frequência de acionamento, ancorado em 10 a
    60 Hz (reproduz o v5 exatamente no ponto nominal)."""
    return K_IQS_NOM * (frequency_ref_hz / FREQ_NOM_HZ)


class InverterFOCv6(InverterFOCv5):
    """`InverterFOCv5` com K_IQS recalculado por `lei_k_iqs(frequency_ref_hz)`
    em vez do valor fixo K_IQS=10. ids e w não mudam."""

    def __init__(self, *args, lei_k_iqs=k_iqs_linear, **kwargs):
        super().__init__(*args, **kwargs)

        frequency_ref_hz = self.frequency_ref / (2 * np.pi)
        k_iqs = lei_k_iqs(frequency_ref_hz)

        fs_hz = self.frequency_s / (2 * np.pi)
        teto_hz = fs_hz / 8
        polo_iqs_hz = self.Rs / (2 * np.pi * self.Lsline)
        bwp_iqs_teto = min(k_iqs * polo_iqs_hz, teto_hz)
        bwp_iqs = np.sqrt(bwp_iqs_teto * teto_hz)
        bwi_iqs = bwp_iqs / 8
        self.kp_iqs = 2 * np.pi * self.Lsline * bwp_iqs
        self.ki_iqs = self.Lsline * 4 * (np.pi**2) * bwp_iqs * bwi_iqs

        self.k_iqs_usado = k_iqs
        self.bwp_iqs_hz = bwp_iqs
        self.polo_iqs_hz = polo_iqs_hz
