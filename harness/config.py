"""Caminhos da comparacao. Ajuste com a variavel ROSS_COMPARACAO_RAIZ, se necessario.

Layout esperado (criado por setup_worktrees.py):

    <RAIZ>/cmp_jg        feature-motor do jguarato (0ec7dad5)
    <RAIZ>/cmp_bose      branch feature-motor-bose
    <RAIZ>/cmp_arismar   branch feature-motor-bose-arismar

RAIZ e, por padrao, a pasta que contem este repositorio (a branch comparacao-arismar).
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAIZ = Path(os.environ.get("ROSS_COMPARACAO_RAIZ", REPO.parent)).resolve()
JG = RAIZ / "cmp_jg"
BOSE = RAIZ / "cmp_bose"
ARISMAR = RAIZ / "cmp_arismar"
CODIGOS_ARISMAR = REPO / "arismar" / "Codigos_MIT-SVPWM_Final"
RUNS = REPO / "runs"
REPORT = REPO / "report"
