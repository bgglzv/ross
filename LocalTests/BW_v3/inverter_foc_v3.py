"""Variante do InverterFOC com `ki_iqs` desacoplado de `kp_iqs` e dependente
da frequência de acionamento.

Herda de `InverterFOCv2` (`../BW_v2/inverter_foc_v2.py`): mantém o
anti-windup já validado (trava `state["int_err_iqs"]` durante saturação de
tensão) e todo o resto da malha de controle sem alteração. A única mudança
é a fórmula de `ki_iqs`.

Contexto: com ki_iqs fixo (mesmo BWi_iqs = BWp_iqs/8 em qualquer frequência,
v2), o ripple melhorou mais em MIT_P a 60 Hz (+33,8%) do que nas frequências
mais baixas, e quase não melhorou em MIT_G. Isso é consistente com a causa
identificada: o termo de desacoplamento feedforward (Lss*w_sync*ids) escala
com a velocidade síncrona, então o resíduo que o integrador precisa
rejeitar é maior justamente perto de 60 Hz — mas o ganho ki_iqs do v2 não
sabe disso, é o mesmo em qualquer frequência de acionamento.

Proposta (desacoplando Kp de Ki):

    kp_iqs continua EXATAMENTE igual ao original (só função de frequency_s,
    a frequência de chaveamento — não muda com a frequência de
    acionamento). Mantém a margem de fase/discretização já validada: não há
    motivo para arriscar a resposta rápida (Kp) que já funciona.

    ki_iqs passa a crescer com a razão entre a frequência de acionamento
    (frequency_ref) e a frequência nominal (frequency_nom), dobrando a
    banda do integrador (BWi_iqs) ao chegar em 60 Hz:

        BWi_iqs(frequency_ref) = (BWp_iqs / 8) * (1 + frequency_ref/frequency_nom)
        ki_iqs = Lsline * 4*pi**2 * BWp_iqs * BWi_iqs(frequency_ref)

    Em 30 Hz (razão 0,5): BWi_iqs = 1,5 x o valor fixo do v2.
    Em 45 Hz (razão 0,75): BWi_iqs = 1,75 x.
    Em 55 Hz (razão 0,917): BWi_iqs = 1,917 x.
    Em 60 Hz (razão 1,0): BWi_iqs = 2,0 x.

    O natural frequency resultante (sqrt(BWp_iqs*BWi_iqs), em Hz) sobe de
    ~221 Hz (v2, fixo) para ~221-313 Hz (v3, conforme a frequência de
    acionamento) — ainda uma década abaixo de fs/2 (2500 Hz) e abaixo de
    BWp_iqs (625 Hz), preservando a margem de fase frente à discretização
    (Ts = 1/fs) que o método BW/8 original já reservava.

Escopo: só essa fórmula de ki_iqs (+ o anti-windup herdado do v2). Nenhuma
outra mudança (ids, w, kp_iqs permanecem idênticos à biblioteca original).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v2"))

from inverter_foc_v2 import InverterFOCv2


class InverterFOCv3(InverterFOCv2):
    """`InverterFOCv2` (ki_iqs + anti-windup) com `ki_iqs` desacoplado de
    `kp_iqs` e escalado pela razão frequency_ref/frequency_nom."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        frequency_s_hz = self.frequency_s / (2 * np.pi)
        BWp_iqs = frequency_s_hz / 8
        razao_freq = self.frequency_ref / self.frequency_nom
        BWi_iqs = (BWp_iqs / 8) * (1 + razao_freq)
        self.ki_iqs = self.Lsline * 4 * (np.pi**2) * BWp_iqs * BWi_iqs
