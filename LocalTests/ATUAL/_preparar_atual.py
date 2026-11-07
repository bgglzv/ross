"""Copia de OLD/ os arquivos de BW_v2/v5/v6 necessarios e adapta aos nomes da
biblioteca atualizada (feature-motor de jguarato): inverters -> motor_drive,
*_nom -> *_rated.

    python _preparar_atual.py
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "OLD"
DESTINO = RAIZ / "ATUAL"

ARQUIVOS = [
    "comum/__init__.py",
    "comum/motores.py",
    "BW_v2/inverter_foc_v2.py",
    "BW_v5/inverter_foc_v5.py",
    "BW_v5/simular_v5.py",
    "BW_v6/inverter_foc_v6.py",
    "BW_v6/simular_v6.py",
]

SUBSTITUICOES = [
    ("ross.motors.inverters", "ross.motors.motor_drive"),
    ("ross/motors/inverters.py", "ross/motors/motor_drive.py"),
    ("Is_nom", "Is_rated"),
]

for arq in ARQUIVOS:
    texto = (ORIGEM / arq).read_text(encoding="utf-8-sig")
    for velho, novo in SUBSTITUICOES:
        texto = texto.replace(velho, novo)
    destino = DESTINO / arq
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    print(arq)
