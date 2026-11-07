"""Variante do InverterFOC em que a banda de malha fechada de iqs e ids não
vem só da frequência de chaveamento (fs/8, igual para qualquer motor), mas
é recalculada a partir dos PARÂMETROS FÍSICOS de cada máquina — ao trocar
de motor, os ganhos recalculam sozinhos, sem precisar de uma nova
varredura empírica (diferente do C do BW_v4, achado por tentativa).

Motivação (ver BW_v4/Relatorio_Final_Sintonia_FOC.docx, fato 7): o método
original fixa a banda fechada (BWp_iqs = BWp_ids = fs/8 = 625 Hz nesse
estudo) só a partir da frequência de chaveamento — a mesma banda nos dois
motores, mesmo a planta elétrica de cada um tendo constantes de tempo
muito diferentes:

    tau_elec,iqs = Lsline/Rs   (ms): MIT_P ~2,7   MIT_G ~123,5  (~45x mais lento)
    tau_elec,ids = Lss/Rs      (ms): MIT_P ~47,1  MIT_G ~1853,6 (~39x mais lento)

A banda de malha fechada relativa ao próprio polo da planta (BWp*tau_elec)
é ~1,7x em MIT_P e ~77x em MIT_G — a "agressividade relativa" do mesmo
ganho é ~45x maior em MIT_G, mesmo essa sendo a máquina de maior porte.

Proposta: ancorar a banda fechada de cada malha num MÚLTIPLO do polo
elétrico da própria planta, não só na frequência de chaveamento:

    polo_iqs_hz = Rs / (2*pi*Lsline) = 1 / (2*pi*tau_elec,iqs)
    BWp_iqs     = min(K_IQS * polo_iqs_hz, fs_hz / 8)

    polo_ids_hz = Rs / (2*pi*Lss) = 1 / (2*pi*tau_elec,ids)
    BWp_ids     = min(K_IDS * polo_ids_hz, fs_hz / 8)

K_IQS e K_IDS são as únicas constantes universais fixas (razão
adimensional entre a banda de malha fechada desejada e o polo natural da
própria planta — um critério clássico de projeto de malha de corrente,
aqui usado em 10x por padrão). O teto em fs/8 preserva a margem de
discretização já validada: a malha nunca fica MAIS rápida do que o método
original já permitia, só mais lenta quando o motor pedir.

O fator de amortecimento é preservado nos mesmos valores já validados:
zeta_iqs = sqrt(2) (igual ao BW_v2/BW_v4), zeta_ids = 1 (igual ao
original, BWp_ids=BWi_ids no método original). kp_w/ki_w (malha de
velocidade) NÃO são alterados nesta primeira versão — escopo desta rodada
é só iqs/ids, que respondem diretamente pelo ripple de conjugado. O
anti-windup de iqs (já validado no BW_v2) é herdado sem alteração.

Primeira rodada (só o teto acima): excelente em MIT_P (+66,3% de ripple
vs. o original), catastrófico em MIT_G (velocidade negativa já no
primeiro segundo pós-carga, nunca recupera). Causa: BWp_ids caiu a
0,86 Hz — bem mais lento que a própria malha de velocidade (78,1 Hz,
inalterada) — e os ganhos resultantes (kp_ids=0,55, ki_ids=1,5) ficaram
pequenos demais para gerar autoridade de correção relevante frente à
escala de tensão/corrente da máquina.

Piso (este ajuste): em vez de travar BWp num múltiplo fixo de BWp_w (o
que, testado à mão, entra em conflito com o teto em tau_elec — teria que
FORÇAR BWp_ids de MIT_P para cima de ~150 Hz, desfazendo o ganho que fez
esse motor funcionar tão bem), o piso é a MÉDIA GEOMÉTRICA entre o alvo
casado com a planta (teto) e o valor original do método (fs/8):

    BWp_X = sqrt( min(K_X * polo_X_hz, fs_hz/8) * (fs_hz/8) )

Não introduz nenhuma constante nova: usa só K_IQS/K_IDS (já definidos
para o teto) e fs_hz (parâmetro do acionamento, não do motor). Quando o
alvo casado com a planta já está perto de fs/8 (motor "rápido", como
MIT_P em iqs), a média geométrica muda pouco. Quando o alvo cai muito
abaixo de fs/8 (motor "lento", como MIT_G), a média geométrica funciona
como um piso suave: nunca deixa a banda desabar para perto de zero, mas
também não força de volta ao valor original — fica na média geométrica
dos dois, que cresce com a própria raiz do quanto o motor se afasta do
caso rápido (nenhum "k" extra para escolher por fora)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "BW_v2"))

from inverter_foc_v2 import InverterFOCv2

K_IQS = 10.0
K_IDS = 10.0


class InverterFOCv5(InverterFOCv2):
    """`InverterFOCv2` (anti-windup de iqs já validado) com kp/ki de iqs e
    ids recalculados a partir dos parâmetros físicos do motor (ver
    módulo), em vez de só da frequência de chaveamento. kp_w/ki_w
    permanecem os da biblioteca original.

    As razões internas BWi/BWp de cada malha são mantidas EXATAMENTE como
    no método original (BWi_iqs=BWp_iqs/8; BWi_ids=BWp_ids), só a base
    (BWp) passa a vir do polo da planta — isso preserva o mesmo fator de
    amortecimento já validado (zeta_iqs=sqrt(2), zeta_ids=1), mudando só a
    banda (wn), exatamente como a constante C do BW_v4 fazia, mas agora
    com a base motor-aware em vez de um multiplicador achado por busca."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        fs_hz = self.frequency_s / (2 * np.pi)
        teto_hz = fs_hz / 8

        polo_iqs_hz = self.Rs / (2 * np.pi * self.Lsline)
        bwp_iqs_teto = min(K_IQS * polo_iqs_hz, teto_hz)
        bwp_iqs = np.sqrt(bwp_iqs_teto * teto_hz)
        bwi_iqs = bwp_iqs / 8
        self.kp_iqs = 2 * np.pi * self.Lsline * bwp_iqs
        self.ki_iqs = self.Lsline * 4 * (np.pi**2) * bwp_iqs * bwi_iqs

        polo_ids_hz = self.Rs / (2 * np.pi * self.Lss)
        bwp_ids_teto = min(K_IDS * polo_ids_hz, teto_hz)
        bwp_ids = np.sqrt(bwp_ids_teto * teto_hz)
        bwi_ids = bwp_ids
        self.kp_ids = self.Lss * 2 * np.pi * (bwp_ids + bwi_ids)
        self.ki_ids = self.Lss * 4 * (np.pi**2) * bwp_ids * bwi_ids

        self.bwp_iqs_hz = bwp_iqs
        self.bwp_ids_hz = bwp_ids
        self.polo_iqs_hz = polo_iqs_hz
        self.polo_ids_hz = polo_ids_hz
