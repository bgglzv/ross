"""Monta o documento comparando o FOC original (a cada passo de simulação) nos dois
passos internos já usados antes (1e-5 e 1e-6 s), depois da correção do cálculo de
banda dos PIs em ``ross/motors/inverters.py`` (``InverterFOC.__init__``).

O barramento CC é opcional (padrão da biblioteca, 1,35 × V_linha, se omitido) e
precisa já ter sido simulado com ``passo_tempo.py <passo_s> [fator_barramento]``.

    python montar_correcao_bw.py                # barramento padrão (1,35 x V_linha)
    python montar_correcao_bw.py 1.414           # barramento 1,414 x V_linha
"""

import json
import sys
from pathlib import Path

from lado_a_lado import montar_documento

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "passo_dados"

ROTULOS = {"1e-05": "1e-5", "1e-06": "1e-6"}


def _sufixo(passo, fator):
    return f"passo_{passo}" + (f"_fator_{fator:g}" if fator is not None else "")


def _carregar(passo, fator):
    d = json.loads((DADOS / f"{_sufixo(passo, fator)}.json").read_text())
    d.setdefault("fator", fator if fator is not None else 1.35)
    return d


def _texto(fator_rotulo):
    return (
        f"Correção da banda dos PIs do FOC — controle original (a cada passo de "
        f"simulação), passo 1e-5 × 1e-6 s, barramento {fator_rotulo} × V_linha",
        [
            ("O que mudou", [
                "A biblioteca calculava a banda dos PIs como frequency_s / 8, mas frequency_s é guardada em "
                "rad/s (não em Hz), enquanto as fórmulas dos ganhos (kp = 2π · L · BW) esperam BW em Hz. O "
                "resultado era um ganho cerca de 2π (≈ 6,28 ×) maior do que o pretendido pelo método de banda "
                "passante.",
                "A correção converte frequency_s para Hz antes de dividir por 8 (InverterFOC.__init__), sem "
                "alterar mais nada: nem o período de chaveamento, nem o modulador, nem os limites de corrente.",
            ]),
            ("O que foi testado", [
                f"Motor pequeno (1,5 hp), 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s, barramento "
                f"{fator_rotulo} × V_linha, controle a cada passo de simulação — o mesmo modo de execução "
                "nativo da biblioteca, sem o controle digital uma vez por chaveamento testado na Opção 7.",
                "Repetido nos dois passos internos de simulação já usados antes: 1e-5 s (20 amostras por "
                "período de chaveamento) e 1e-6 s (200 amostras por período).",
            ]),
            ("Resultado", [
                "Com os ganhos corrigidos, a saturação da referência de corrente cai de forma acentuada em "
                "relação aos ganhos antigos nos dois passos — ver a tabela ao final.",
                "O resultado é próximo entre os dois passos de simulação (1e-5 e 1e-6 s), como esperado: a "
                "correção atua na sintonia dos ganhos, não na resolução numérica do integrador.",
            ]),
        ],
    )


def montar(fator=None):
    fator_rotulo = f"{fator:g}".replace(".", ",") if fator is not None else "1,35 (padrão)"
    sufixo_doc = f"_fator_{fator:g}" if fator is not None else ""
    figuras = PASTA / f"figuras_correcao_bw{sufixo_doc}"
    nome_documento = f"Correcao-BW_original_1e-5_vs_1e-6{sufixo_doc}.docx"

    dados = {p: _carregar(p, fator) for p in ROTULOS}
    linhas = [(f"Passo {ROTULOS[p]} s", dados[p]) for p in ROTULOS]
    montar_documento(
        list(ROTULOS), figuras,
        lambda v, d: f"FOC original, ganhos corrigidos — passo {ROTULOS[v]} s, barramento {fator_rotulo} × V_linha — {d}",
        lambda v: str(DADOS / _sufixo(v, fator)) + ".npz", linhas,
        f"Correção de banda dos PIs — resumo da saturação (FOC original, 60 Hz, motor pequeno, "
        f"barramento {fator_rotulo} × V_linha)",
        PASTA / nome_documento, texto=_texto(fator_rotulo))


if __name__ == "__main__":
    montar(float(sys.argv[1]) if len(sys.argv) > 1 else None)
