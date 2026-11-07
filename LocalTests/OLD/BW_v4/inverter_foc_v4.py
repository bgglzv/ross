"""Variante do InverterFOC com TODOS os ganhos (iqs, ids, w) desacoplados em
(zeta, wn) e escalados por uma única constante universal `C`.

Herda de `InverterFOCv2` (ki_iqs fixo + anti-windup, já validado) como
referência C=1 — nenhuma mudança adicional quando C=1.

Fundamentação (análise de parâmetros do motor, ver Relatorio_parametros.docx
desta pasta): o mesmo ganho de malha fechada, derivado só da frequência de
chaveamento (fs/8), representa uma "agressividade relativa" muito maior em
MIT_G do que em MIT_P, porque as constantes de tempo da própria planta são
muito mais lentas em MIT_G:

    tau_elec (Lsline/Rs, Lss/Rs): ~40-45x mais lento em MIT_G
    tau_r    (Lrr/Rr):            ~28x mais lento em MIT_G
    Is_nom   (limiar de saturação, iqs_max=3*Is_nom): ~100x maior em MIT_G

O v3 (BW_v3) tentou compensar isso escalando só ki_iqs com a frequência de
acionamento — mas aumentar ki sem aumentar kp na mesma proporção REDUZ o
fator de amortecimento (zeta) da malha (zeta = kp/(2*wn*L), wn = sqrt(ki/L)):
em MIT_G isso bastou para impedir a reconvergência após o afundamento de
velocidade a 60 Hz.

Esta versão corrige esse erro de desenho: escala kp e ki de forma que o
fator de amortecimento de cada malha NÃO mude, só a banda (wn):

    kp_novo = C * kp_original
    ki_novo = C² * ki_original

Prova: wn = sqrt(ki/L) -> wn_novo = sqrt(C²*ki/L) = C*wn_original.
       zeta = kp/(2*wn*L) -> zeta_novo = (C*kp)/(2*C*wn*L) = zeta_original.

Aplicado às três malhas (iqs, ids, w) com a MESMA constante C, para os dois
motores — "universal" no sentido de não depender da frequência de
acionamento nem ser recalculada por motor (ao contrário do v3).

Para a malha de w, kp_w = J*2*pi*(BWp_w+BWi_w) - KL já subtrai o termo de
desacoplamento KL (constante de carga) do ganho proporcional "puro"; só a
parte "pura" (kp_w + KL) deve ser escalada por C, preservando o
desacoplamento:

    kp_w_novo = C*(kp_w_original + KL) - KL
    ki_w_novo = C² * ki_w_original
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v2"))

from inverter_foc_v2 import InverterFOCv2


class InverterFOCv4(InverterFOCv2):
    """`InverterFOCv2` com kp/ki de iqs, ids e w escalados por uma
    constante universal `C` que preserva o fator de amortecimento de cada
    malha (ver módulo). `C=1` reproduz exatamente o v2."""

    def __init__(self, *args, C=1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.C = float(C)

        torque_nom = kwargs["torque_nom"]
        KL = float(torque_nom) / (self.np_pairs * self.speed_nom)

        self.kp_iqs = self.C * self.kp_iqs
        self.ki_iqs = (self.C**2) * self.ki_iqs

        self.kp_ids = self.C * self.kp_ids
        self.ki_ids = (self.C**2) * self.ki_ids

        kp_w_puro = self.kp_w + KL
        self.kp_w = self.C * kp_w_puro - KL
        self.ki_w = (self.C**2) * self.ki_w
