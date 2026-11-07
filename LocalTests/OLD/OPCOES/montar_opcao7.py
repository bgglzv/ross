"""Monta os documentos da Opção 7 (controle a cada passo x controle digital), com texto.

    python montar_opcao7.py            # os dois casos (1e-05 e 1e-06)
    python montar_opcao7.py 1e-06      # só o caso de passo 1e-6
"""

import json
from pathlib import Path

import barramento
import opcao7
from lado_a_lado import montar_documento

PASTA = Path(__file__).resolve().parent
PASSO_DADOS = PASTA / "passo_dados"

CASOS = {
    "1e-05": dict(
        rotulo="1e-5",
        amostras=20,
        original=(barramento.DADOS / "fator_1.35"),
        digital=(opcao7.DADOS / "passo_1e-05"),
        nome="Opcao7-Controle-digital_passo-1e-5.docx",
    ),
    "1e-06": dict(
        rotulo="1e-6",
        amostras=200,
        original=(PASSO_DADOS / "passo_1e-06"),
        digital=(opcao7.DADOS / "passo_1e-06"),
        nome="Opcao7-Controle-digital_passo-1e-6.docx",
    ),
}


def _carregar(base):
    d = json.loads(Path(str(base) + ".json").read_text())
    d.setdefault("fator", 1.35)
    return d


def _num(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


def _texto(caso, orig, dig):
    p, n = caso["rotulo"].replace("e-", " × 10⁻"), caso["amostras"]
    return (
        f"Opção 7 — Controle digital (uma vez por chaveamento) — passo de simulação {caso['rotulo']} s: principais pontos",
        [
            ("O que foi testado", [
                "Na biblioteca, a malha de controle do FOC roda a cada passo de simulação e usa a corrente instantânea, "
                "com o ripple do chaveamento. Num acionamento real, a malha é discreta: a corrente é amostrada de forma "
                "síncrona com o PWM, a malha roda uma vez por período de chaveamento e a tensão de referência fica "
                "segurada até a próxima amostra.",
                f"Aqui a malha foi executada uma vez por período de chaveamento (Ts = 200 µs, a 5 kHz), amostrando a "
                f"corrente no vale da portadora e segurando as tensões de referência; o modulador continua rodando a cada "
                f"passo ({n} amostras por período com o passo de {caso['rotulo']} s). Ganhos dos PIs, limite de corrente "
                "(3 × a corrente nominal) e anti-windup são os nativos da biblioteca; os integradores avançam com Ts.",
                "Motor pequeno (1,5 hp), 60 Hz, rampa de 0,6667 s, carga nominal em 1,5 s, barramento 1,35 × V_linha. "
                "À esquerda das figuras está o controle da biblioteca (a cada passo) e à direita o controle digital.",
            ]),
            ("Resultado", [
                f"Com o controle digital e os ganhos nativos, o motor não acompanha a rampa. A velocidade chega a "
                f"{_num(dig['v_1_4'], 0)} RPM em 1,4 s (controle a cada passo: {_num(orig['v_1_4'], 0)} RPM), fica em "
                f"{_num(dig['v_2_5'], 0)} RPM em 2,5 s e termina em {_num(dig['v_fim'], 0)} RPM: com a carga nominal aplicada, "
                "o motor inverte o sentido de giro.",
                f"O conjugado máximo é de apenas {_num(dig['conjugado_maximo'], 1)} N·m (controle a cada passo: "
                f"{_num(orig['conjugado_maximo'], 1)} N·m). A referência de corrente fica saturada em "
                f"{_num(dig['pct_rampa'], 1)}% da rampa, {_num(dig['pct_regime_vazio'], 1)}% do tempo em vazio e "
                f"{_num(dig['pct_apos_carga'], 1)}% após a carga. O conjugado mínimo pequeno "
                f"({_num(dig['conjugado_minimo'], 2)} N·m) não deve ser lido como melhora: o motor quase não produz torque.",
                "O resultado praticamente não depende do passo de simulação (1e-5 ou 1e-6 s), o que indica que a causa "
                "está no período de execução da malha (Ts), e não na resolução do modulador.",
            ]),
            ("Diagnóstico (primeiros 240 ms, passo de 1e-5 s)", [
                "A referência de corrente de torque (iq) fica saturada em 18 A, mas a corrente iq medida fica em 3 a 4 A. "
                "A corrente de fluxo (id) é regulada corretamente (3,7 a 3,8 A, referência de 3,78 A).",
                "A tensão de eixo q comandada tem média de cerca de 20 V (com picos de 150 a 170 V), muito abaixo do que o "
                "erro de corrente exigiria de um controlador proporcional funcionando.",
            ]),
            ("Causa consistente com os números (cálculo, sem alterar ganhos)", [
                "A biblioteca calcula a banda dos PIs como frequency_s / 8. Como frequency_s é guardada em rad/s "
                "(31 416 rad/s para 5 kHz), o valor usado é 3 927, e as fórmulas dos ganhos multiplicam esse valor por 2π "
                "(kp_iqs = 2π · L · BW), como se BW estivesse em Hz.",
                "Resultado: kp_iqs = 167,7 V/A, com L = 6,80 mH. A frequência de cruzamento da malha de corrente é "
                "kp / L = 24 674 rad/s, ou 3 927 Hz, equivalente a 0,79 da frequência de chaveamento (5 kHz).",
                "Em tempo discreto com período Ts, o ganho de malha é kp · Ts / L = 4,93. O limite de estabilidade é 2; com "
                "4,93 o polo discreto fica em cerca de −3,9, ou seja, a malha é instável. Se a banda fosse fs/8 em Hz "
                "(625 Hz), kp seria 26,7 V/A e o ganho de malha 0,79, estável.",
                "Isso é coerente com o que se observa: os ganhos nativos só funcionam quando a malha roda a cada passo de "
                "simulação (100 kHz com passo de 1e-5 s e 1 MHz com 1e-6 s), isto é, como um controlador quase contínuo. "
                "Não são utilizáveis numa malha que roda a 5 kHz.",
                "Isto é uma hipótese de causa apoiada em cálculo e no comportamento observado. Não foi testada com ganhos "
                "corrigidos, porque os ganhos dos PIs não foram alterados, conforme combinado.",
            ]),
            ("Limitações", [
                "Implementação simplificada: não há compensação do atraso computacional nem do retentor de ordem zero, "
                "que os acionamentos reais costumam fazer. O ângulo do fluxo é integrado com Ts a cada amostra.",
                "Só o motor pequeno, a 60 Hz e com barramento padrão foi simulado.",
            ]),
            ("Próximos passos possíveis (aguardam sua decisão)", [
                "Repetir o controle digital com a banda interpretada em Hz (625 Hz), para confirmar a causa.",
                "Comparar o controle a cada passo da biblioteca com os mesmos ganhos reduzidos, para ver quanto do "
                "ripple, da saturação e do torque negativo observados nas opções anteriores vêm da banda excessiva.",
            ]),
        ],
    )


def _metricas_extras(base):
    import numpy as np

    from comum import anotacoes as an

    d = np.load(str(base) + ".npz")
    t = d["t"]
    v = an.media_movel(t, d["velocidade_rpm"])
    return dict(v_1_4=float(v[np.searchsorted(t, 1.4)]), v_2_5=float(v[np.searchsorted(t, 2.5)]),
                v_fim=float(v[-100:].mean()))


def montar(chaves=None):
    for chave in chaves or CASOS:
        caso = CASOS[chave]
        orig, dig = _carregar(caso["original"]), _carregar(caso["digital"])
        orig.update(_metricas_extras(caso["original"]))
        dig.update(_metricas_extras(caso["digital"]))
        rot = caso["rotulo"]
        linhas = [("Controle a cada passo (biblioteca)", orig), ("Controle digital (1× por chaveamento)", dig)]
        pasta_figuras = opcao7.FIGURAS / f"passo_{chave}"
        opcao7.FIGURAS.mkdir(exist_ok=True)
        titulos = {
            "original": f"Opção 7 — Controle a cada passo (biblioteca), passo {rot} s",
            "digital": f"Opção 7 — Controle digital (1× por chaveamento), passo {rot} s",
        }
        montar_documento(
            ["original", "digital"], pasta_figuras,
            lambda v, d, titulos=titulos: f"{titulos[v]} — {d}",
            lambda v, caso=caso: str(caso[v]) + ".npz", linhas,
            f"Opção 7 — Resumo da saturação (FOC, 60 Hz, motor pequeno, passo {rot} s)",
            PASTA / caso["nome"], texto=_texto(caso, orig, dig))


if __name__ == "__main__":
    import sys

    desconhecidas = [c for c in sys.argv[1:] if c not in CASOS]
    if desconhecidas:
        raise SystemExit(f"Casos desconhecidos {desconhecidas}; use {list(CASOS)}")
    montar(sys.argv[1:] or None)
