"""Cria, ao lado deste repositorio, as tres versoes do ROSS usadas na comparacao.

Uso:  python harness/setup_worktrees.py [--remoto origin]

Cria worktrees "detached" (nao conflitam com a branch que voce ja tem em uso):
    cmp_jg       commit 0ec7dad5 (feature-motor do jguarato)
    cmp_bose     ponta de feature-motor-bose
    cmp_arismar  ponta de feature-motor-bose-arismar
Se uma pasta ja existir, ela e mantida. Para atualizar, rode "git pull" na branch
correspondente do seu clone e apague a pasta cmp_* antes de rodar este script.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARISMAR, BOSE, JG, REPO  # noqa: E402

VERSOES = [
    (JG, "0ec7dad5"),
    (BOSE, "feature-motor-bose"),
    (ARISMAR, "feature-motor-bose-arismar"),
]


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def resolve(ref, remoto):
    for candidato in (f"{remoto}/{ref}", ref):
        if git("rev-parse", "--verify", "--quiet", candidato + "^{commit}").returncode == 0:
            return candidato
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remoto", default="origin")
    args = ap.parse_args()
    git("fetch", args.remoto)
    for pasta, ref in VERSOES:
        if pasta.exists():
            print(f"[mantida] {pasta}")
            continue
        alvo = resolve(ref, args.remoto)
        if alvo is None:
            sys.exit(f"Nao encontrei '{ref}'. Rode: git fetch {args.remoto}")
        r = git("worktree", "add", "--detach", str(pasta), alvo)
        if r.returncode != 0:
            sys.exit(r.stderr)
        print(f"[criada]  {pasta}  <- {alvo}")


if __name__ == "__main__":
    main()
