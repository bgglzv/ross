"""Executa a comparacao completa (V/f e FOC a 60 Hz) e gera metricas, figuras e relatorio.

Uso:
    python harness/run_all.py                 # caso do relatorio: 100 amostras por periodo, 3 s
    python harness/run_all.py --ns 100 --passo  # inclui a sensibilidade ao passo (NS = 20 e 40)
    python harness/run_all.py --paralelo 8      # numero de simulacoes simultaneas

As execucoes ficam em runs/*.npz (nao versionadas). Use o mesmo Python em que o ROSS roda.
Tempo aproximado com NS = 100 e 3 s: 2 a 6 minutos por simulacao.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARISMAR, BOSE, JG, RUNS  # noqa: E402

HERE = Path(__file__).resolve().parent


def trabalhos(ns, t_total, t_carga, passo):
    py = sys.executable
    runs = []

    def standalone(modo):
        return [py, str(HERE / "run_standalone.py"), modo, str(ns), str(t_total), str(t_carga), str(RUNS / f"standalone_{modo}.npz")]

    def ross(raiz, modo, variante, n, sufixo=""):
        return [py, str(HERE / "run_ross.py"), str(raiz), modo, variante, str(n), str(t_total), str(t_carga), str(RUNS / f"{variante}_{modo}{sufixo}.npz")]

    for modo in ("VF", "FOC"):
        runs.append((f"standalone {modo}", standalone(modo)))
        runs.append((f"jg {modo}", ross(JG, modo, "jg", ns)))
        runs.append((f"bose {modo}", ross(BOSE, modo, "bose", ns)))
        runs.append((f"ari {modo}", ross(ARISMAR, modo, "ari", ns)))
    runs.append(("ari_def FOC", ross(ARISMAR, "FOC", "ari_def", ns)))
    runs.append(("ari_rsc FOC", ross(ARISMAR, "FOC", "ari_rsc", ns)))
    if passo:
        for n in (20, 40):
            runs.append((f"ari FOC NS={n}", ross(ARISMAR, "FOC", "ari", n, f"_ns{n}")))
            runs.append((f"ari VF NS={n}", ross(ARISMAR, "VF", "ari", n, f"_ns{n}")))
        runs.append(("bose FOC NS=20", ross(BOSE, "FOC", "bose", 20, "_ns20")))
        runs.append(("bose VF NS=20", ross(BOSE, "VF", "bose", 20, "_ns20")))
        runs.append(("jg FOC NS=20", ross(JG, "FOC", "jg", 20, "_ns20")))
    return runs


def executar(lista, paralelo):
    ativos = []
    pendentes = list(lista)
    falhas = []
    while pendentes or ativos:
        while pendentes and len(ativos) < paralelo:
            nome, cmd = pendentes.pop(0)
            print(f"[inicio] {nome}", flush=True)
            ativos.append((nome, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)))
        for item in list(ativos):
            nome, proc = item
            if proc.poll() is not None:
                ativos.remove(item)
                if proc.returncode != 0:
                    falhas.append(nome)
                    print(f"[FALHOU] {nome}\n{proc.stderr.read()[-800:]}", flush=True)
                else:
                    print(f"[ok]     {nome}", flush=True)
        time.sleep(1)
    return falhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", type=int, default=100, help="amostras por periodo de chaveamento (5 kHz)")
    ap.add_argument("--t-total", type=float, default=3.0)
    ap.add_argument("--t-carga", type=float, default=1.0)
    ap.add_argument("--passo", action="store_true", help="inclui NS = 20 e 40")
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--sem-analise", action="store_true")
    args = ap.parse_args()

    for pasta in (JG, BOSE, ARISMAR):
        if not pasta.exists():
            sys.exit(f"Falta {pasta}. Rode antes: python harness/setup_worktrees.py")
    RUNS.mkdir(parents=True, exist_ok=True)
    falhas = executar(trabalhos(args.ns, args.t_total, args.t_carga, args.passo), args.paralelo)
    if falhas:
        sys.exit(f"Falharam: {falhas}")
    if args.sem_analise:
        return
    for script in ("analyze.py",) + (("passo.py",) if args.passo else ()) + ("make_report.py",):
        print(f"[analise] {script}", flush=True)
        subprocess.run([sys.executable, str(HERE / script)], check=True)
    print("Pronto. Relatorio regenerado em report/relatorio_comparativo_arismar_regenerado.md; figuras em report/figuras_arismar/.")


if __name__ == "__main__":
    main()
