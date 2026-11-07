"""Roda BW_v5 e BW_v6 (MIT_P e MIT_G) em 30, 45, 55, 60 e 62 Hz com a
biblioteca atualizada, em paralelo, um processo por caso.

    python rodar_tudo.py [n_trabalhadores]
"""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PASTA = Path(__file__).resolve().parent
FREQS = (30, 45, 55, 60, 62)
MOTORES = ("G", "P")
VERSOES = (("BW_v5", "simular_v5.py"), ("BW_v6", "simular_v6.py"))


def caso(args):
    pasta, script, motor, freq = args
    saida = PASTA / pasta / "dados" / f"{motor}_{freq:g}Hz_foc_{pasta[-2:]}.npz"
    if saida.exists():
        return f"{pasta} {motor} {freq} Hz: ja existe, pulado"
    inicio = time.time()
    r = subprocess.run(
        [sys.executable, script, motor, str(freq)],
        cwd=PASTA / pasta, capture_output=True, text=True,
    )
    duracao = time.time() - inicio
    status = "OK" if r.returncode == 0 and saida.exists() else f"FALHOU (codigo {r.returncode})"
    if status != "OK":
        (PASTA / pasta / f"erro_{motor}_{freq}.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    return f"{pasta} {motor} {freq} Hz: {status} em {duracao / 60:.1f} min"


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    casos = [(p, s, m, f) for m in MOTORES for p, s in VERSOES for f in FREQS]
    with ThreadPoolExecutor(max_workers=n) as pool:
        for linha in pool.map(caso, casos):
            print(linha, flush=True)
