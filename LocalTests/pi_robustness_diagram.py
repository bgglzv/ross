"""pi_robustness_diagram.py — Diagrama de blocos da malha em cascata (FOC).

Gera uma imagem estática (PNG, fundo branco, estilo industrial minimalista)
do diagrama de blocos da malha de controle sob teste no protocolo de
robustez de sintonia PI: velocidade (externa) -> corrente (interna) ->
inversor -> motor -> carga, com realimentação de velocidade e corrente.
Usada no relatório .docx e na apresentação .pptx.

Não é executado diretamente pelos outros scripts do estudo — rode-o uma
vez (ou sempre que quiser regenerar a imagem):

    python pi_robustness_diagram.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ACCENT = "#0E5C68"
ACCENT_WASH = "#E3EEF0"
TEXT = "#1A2027"
MUTED = "#5B6672"
BORDER = "#C3CAD1"


def _box(ax, x, y, w, h, label, sublabel=None, accent=False):
    face = ACCENT_WASH if accent else "white"
    edge = ACCENT if accent else BORDER
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.4, edgecolor=edge, facecolor=face,
    )
    ax.add_patch(box)
    cy = y + h / 2 + (0.05 if sublabel else 0)
    ax.text(x + w / 2, cy, label, ha="center", va="center",
            fontsize=11, color=TEXT, fontweight="medium")
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.09, sublabel, ha="center", va="center",
                fontsize=8.5, color=MUTED, family="monospace")


def _arrow(ax, x0, y0, x1, y1, color=MUTED, style="-|>", lw=1.3, ls="-"):
    arrow = FancyArrowPatch(
        (x0, y0), (x1, y1), arrowstyle=style, mutation_scale=12,
        color=color, linewidth=lw, linestyle=ls,
    )
    ax.add_patch(arrow)


def build_diagram(output_path="figs_pi_robustness/diagram_malha_controle.png"):
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=200)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    y_main = 2.3
    h = 0.75

    # Reference input
    ax.text(0.05, y_main + h / 2, r"$\omega_{ref}$", fontsize=11, color=ACCENT, va="center")
    _arrow(ax, 0.55, y_main + h / 2, 0.95, y_main + h / 2)

    # Sum 1
    ax.add_patch(plt.Circle((1.1, y_main + h / 2), 0.13, facecolor="white", edgecolor=BORDER, linewidth=1.3))
    ax.text(1.1, y_main + h / 2, "+/-", fontsize=7, ha="center", va="center", color=MUTED)
    _arrow(ax, 1.23, y_main + h / 2, 1.55, y_main + h / 2)

    _box(ax, 1.55, y_main, 1.15, h, "PI", "velocidade", accent=True)
    _arrow(ax, 2.7, y_main + h / 2, 3.05, y_main + h / 2)
    ax.text(2.87, y_main + h / 2 + 0.16, r"$i_q^*$", fontsize=9, color=MUTED, ha="center")

    # Sum 2
    ax.add_patch(plt.Circle((3.2, y_main + h / 2), 0.13, facecolor="white", edgecolor=BORDER, linewidth=1.3))
    ax.text(3.2, y_main + h / 2, "+/-", fontsize=7, ha="center", va="center", color=MUTED)
    _arrow(ax, 3.33, y_main + h / 2, 3.65, y_main + h / 2)

    _box(ax, 3.65, y_main, 1.15, h, "PI", "corrente", accent=True)
    _arrow(ax, 4.8, y_main + h / 2, 5.2, y_main + h / 2)

    _box(ax, 5.2, y_main, 1.3, h, "Inversor", "PWM / SVM")
    _arrow(ax, 6.5, y_main + h / 2, 6.9, y_main + h / 2)

    _box(ax, 6.9, y_main, 1.4, h, "Motor de", "indução")
    _arrow(ax, 8.3, y_main + h / 2, 8.7, y_main + h / 2)

    _box(ax, 8.7, y_main, 1.4, h, "Carga /", "eixo mecânico")

    # Load disturbance injection
    _arrow(ax, 9.4, 3.55, 9.4, y_main + h, color="#B3452C")
    ax.text(9.4, 3.68, "T_carga\n(degrau)", fontsize=8.5, color="#B3452C", ha="center", va="bottom")

    # Speed feedback path
    fb_y = 0.55
    _arrow(ax, 9.4, y_main, 9.4, fb_y, color=MUTED, style="-")
    _arrow(ax, 9.4, fb_y, 1.1, fb_y, color=MUTED, style="-")
    _arrow(ax, 1.1, fb_y, 1.1, y_main, color=MUTED)
    ax.text(5.2, fb_y - 0.22, r"$\omega$ medida (realimentação de velocidade)",
            fontsize=8.5, color=MUTED, ha="center")

    # Current feedback path
    fb_y2 = 1.35
    _arrow(ax, 7.6, y_main, 7.6, fb_y2, color=MUTED, style="-")
    _arrow(ax, 7.6, fb_y2, 3.2, fb_y2, color=MUTED, style="-")
    _arrow(ax, 3.2, fb_y2, 3.2, y_main, color=MUTED)
    ax.text(5.4, fb_y2 - 0.22, r"$i_q$ medida (realimentação de corrente)",
            fontsize=8.5, color=MUTED, ha="center")

    # Reference step annotation
    ax.text(1.1, 3.55, "degrau de referência\naplicado aqui", fontsize=8.5,
            color=ACCENT, ha="center", va="bottom")
    _arrow(ax, 1.1, 3.4, 1.1, y_main + h, color=ACCENT)

    ax.text(5.5, -0.15,
            "Ganhos de PIω e PIi: os mesmos já sintonizados para o Motor A — não são reajustados no Ensaio 3.",
            fontsize=8.5, color=MUTED, ha="center", style="italic")

    fig.tight_layout()
    fig.savefig(output_path, facecolor="white", bbox_inches="tight")
    print(f"[OK] {output_path}")


if __name__ == "__main__":
    import os

    os.makedirs("figs_pi_robustness", exist_ok=True)
    build_diagram()
