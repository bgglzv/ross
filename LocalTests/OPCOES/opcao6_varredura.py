"""Opção 6 (ajuste fino) — varredura do piso do fator de fluxo K_MIN no enfraquecimento de campo.

Motor pequeno (1,5 hp), FOC, 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s,
barramento padrão (1,35 × V_linha). Só muda o piso K_MIN do fator de fluxo k_fw
(0,5 já simulado na Opção 6; 1,0 equivale ao FOC original, sem enfraquecimento).

    python opcao6_varredura.py simular <k_min>
    python opcao6_varredura.py montar
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opcao6

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "opcao6_varredura_dados"
FIGURAS = PASTA / "opcao6_varredura_figuras"
NOVOS = (0.6, 0.7, 0.8, 0.9)
FATOR_BARRAMENTO = 1.35


def simular(k_min):
    opcao6.K_MIN = k_min
    opcao6.DADOS = DADOS / f"execucao_{k_min}"
    opcao6.simular(FATOR_BARRAMENTO)
    for extensao in ("json", "npz"):
        origem = opcao6.DADOS / f"fator_{FATOR_BARRAMENTO}.{extensao}"
        origem.replace(DADOS / f"kmin_{k_min}.{extensao}")
    opcao6.DADOS.rmdir()


def montar():
    from montar_varredura import montar as montar_documento

    montar_documento()


if __name__ == "__main__":
    if sys.argv[1] == "simular":
        simular(float(sys.argv[2]))
    else:
        montar()
