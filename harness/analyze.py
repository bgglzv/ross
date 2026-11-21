"""Metricas e figuras: validacao do port (arismar x codigo original) e comparacao das versoes.

Le runs/*.npz (60 Hz, passo 2e-6 s, 3 s, carga nominal em 1 s) e grava metricas.json e as
figuras em ../report/figuras_arismar/.
"""

import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import sys  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import BOSE, REPORT, RUNS  # noqa: E402

FIGS = REPORT / "figuras_arismar"
FIGS.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("motor_utils", str(BOSE / "ross" / "motors" / "utils.py"))
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)
thd_fn = utils.total_harmonic_distortion
windowed_dfft = utils.windowed_dfft

T_LOAD = 1.0
WINDOW = (2.0, 3.0)

NAMES = {
    "standalone": "Código do Arismar (referência)",
    "jg": "feature-motor (jguarato)",
    "bose": "feature-motor-bose",
    "ari": "feature-motor-bose-arismar",
    "ari_def": "feature-motor-bose-arismar (ids_ref calculado)",
    "ari_rsc": "feature-motor-bose-arismar (Rsc igualado ao do Arismar)",
}
COLORS = {"standalone": "k", "jg": "tab:gray", "bose": "tab:blue", "ari": "tab:red", "ari_def": "tab:orange", "ari_rsc": "tab:green"}


def load(version, mode):
    path = RUNS / f"{version}_{mode}.npz"
    if not path.exists():
        return None
    d = np.load(path)
    return {k: d[k] for k in d.files}


def blocks(t, x, k):
    n = len(t) // k * k
    return t[:n].reshape(-1, k).mean(1), x[:n].reshape(-1, k).mean(1)


def metrics(d):
    t = d["t"].astype(float)
    dt = float(d["dt"])
    sel = (t >= WINDOW[0]) & (t <= WINDOW[1])
    ia = d["ia"][sel].astype(float)
    va = d["va"][sel].astype(float)
    thd_i, f1 = thd_fn(ia, dt)
    thd_v, _ = thd_fn(va, dt, f1)
    w = np.hanning(sel.sum())
    tt = t[sel]
    i1 = 2 * abs(np.sum(ia * w * np.exp(-2j * np.pi * f1 * tt))) / w.sum()
    pre = (t > 0.85) & (t < T_LOAD)
    kb = int(round(1e-3 / dt))
    _, te_pre = blocks(t[pre], d["Te"][pre].astype(float), kb)
    all_i = np.max(np.abs(np.stack([d["ia"], d["ib"], d["ic"]])), axis=0)
    te = d["Te"][sel].astype(float)
    final = float(d["speed_rpm"][sel].mean())
    t95 = float(t[np.argmax(d["speed_rpm"] >= 0.95 * final)])
    return {
        "t_95_velocidade_s": t95,
        "f1_hz": f1,
        "I1_pico_A": i1,
        "I_rms_A": float(np.sqrt(np.mean(ia**2))),
        "THD_corrente_pct": 100 * thd_i,
        "THD_tensao_fase_pct": 100 * thd_v,
        "velocidade_final_rpm": float(d["speed_rpm"][sel].mean()),
        "velocidade_antes_carga_rpm": float(d["speed_rpm"][pre].mean()),
        "torque_medio_Nm": float(te.mean()),
        "ripple_torque_rms_pct": 100 * float(te.std() / te.mean()),
        "torque_vazio_min_Nm": float(te_pre.min()),
        "torque_vazio_max_Nm": float(te_pre.max()),
        "pico_corrente_partida_A": float(all_i[t < T_LOAD].max()),
        "queda_velocidade_apos_carga_rpm": float(
            d["speed_rpm"][(t > T_LOAD) & (t < T_LOAD + 0.5)].min() - d["speed_rpm"][pre].mean()
        ),
    }


def compare(a, b, lag=0):
    """Diferencas entre o port (a) e a referencia (b); lag = deslocamento de indice de a.

    Retorna o numero de amostras iniciais em que a corrente de fase A coincide (< 1e-5 A) e as
    diferencas de medias em blocos de 1 ms de velocidade e torque.
    """
    n = min(len(a["t"]) - lag, len(b["t"]))
    kb = int(round(1e-3 / float(a["dt"])))
    out = {}
    ia = np.abs(a["ia"][lag : lag + n].astype(float) - b["ia"][:n].astype(float))
    out["amostras_iniciais_coincidentes"] = int(np.argmax(ia > 1e-5)) if np.any(ia > 1e-5) else int(n)
    for key, label in (("speed_rpm", "velocidade_rpm"), ("Te", "torque_Nm")):
        _, xa = blocks(a["t"][:n], a[key][lag : lag + n].astype(float), kb)
        _, xb = blocks(b["t"][:n], b[key][:n].astype(float), kb)
        m = min(len(xa), len(xb))
        diff = xa[:m] - xb[:m]
        out[label] = {"max_abs": float(np.max(np.abs(diff))), "rms": float(np.sqrt(np.mean(diff**2)))}
    return out


def main():
    results = {}
    for mode in ("VF", "FOC"):
        for version in NAMES:
            d = load(version, mode)
            if d is None:
                continue
            results[f"{version}_{mode}"] = metrics(d)
    comparisons = {}
    for key, version, mode, lag in (
        ("VF", "ari", "VF", 0),
        ("FOC (Rsc do ROSS)", "ari", "FOC", 1),
        ("FOC (Rsc igualado)", "ari_rsc", "FOC", 1),
    ):
        a, b = load(version, mode), load("standalone", mode)
        if a is not None and b is not None:
            comparisons[key] = compare(a, b, lag)
    (REPORT / "metricas.json").write_text(
        json.dumps({"metricas": results, "port_vs_standalone": comparisons}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    for k, v in results.items():
        print("MET", k, {kk: round(vv, 3) for kk, vv in v.items()})
    for k, v in comparisons.items():
        print("CMP", k, v)

    for mode in ("VF", "FOC"):
        figure_validation(mode)
        figure_versions(mode)


def figure_validation(mode):
    version = "ari" if mode == "VF" else "ari_rsc"
    a, b = load(version, mode), load("standalone", mode)
    if a is None or b is None:
        return
    if mode == "FOC":
        a = {k: (v[1:] if isinstance(v, np.ndarray) and v.ndim == 1 and len(v) > 10 else v) for k, v in a.items()}
    kb = int(round(1e-3 / float(a["dt"])))
    fig, ax = plt.subplots(4, 1, figsize=(12, 13))
    for d, key in ((b, "standalone"), (a, version)):
        t = d["t"].astype(float)
        tb, sb = blocks(t, d["speed_rpm"].astype(float), kb)
        _, eb = blocks(t, d["Te"].astype(float), kb)
        ax[0].plot(tb, sb, color=COLORS[key], lw=1.2 if key == "standalone" else 0.8, ls="-" if key == "standalone" else "--", label=NAMES[key])
        ax[1].plot(tb, eb, color=COLORS[key], lw=1.2 if key == "standalone" else 0.8, ls="-" if key == "standalone" else "--", label=NAMES[key])
    ax[0].set_ylabel("Velocidade (rpm)")
    ax[1].set_ylabel("Torque (N·m)\n(média em 1 ms)")
    ax[0].legend()
    n = min(len(a["t"]), len(b["t"]))
    _, sa = blocks(a["t"][:n].astype(float), a["speed_rpm"][:n].astype(float), kb)
    _, sb_ = blocks(b["t"][:n].astype(float), b["speed_rpm"][:n].astype(float), kb)
    tb2, ea = blocks(a["t"][:n].astype(float), a["Te"][:n].astype(float), kb)
    _, eb_ = blocks(b["t"][:n].astype(float), b["Te"][:n].astype(float), kb)
    ax[2].plot(tb2, sa - sb_, color="tab:red", lw=0.8)
    ax[2].set_ylabel("Δ velocidade (rpm)\n(port − referência)")
    ax[3].plot(tb2, ea - eb_, color="tab:red", lw=0.8)
    ax[3].set_ylabel("Δ torque (N·m)")
    ax[3].set_xlabel("Tempo (s)")
    for x in ax:
        x.grid(alpha=0.3)
        x.axvline(T_LOAD, color="gray", ls=":")
    fig.suptitle(f"Validação do port ({mode}, 60 Hz): {NAMES[version]} × código original do Arismar")
    fig.tight_layout()
    fig.savefig(FIGS / f"validacao_{mode}.png", dpi=100)
    plt.close(fig)


def figure_versions(mode):
    versions = [v for v in ("jg", "bose", "ari") if load(v, mode) is not None]
    if not versions:
        return
    fig = plt.figure(figsize=(14, 16))
    gs = fig.add_gridspec(4, 2)
    ax_s = fig.add_subplot(gs[0, :])
    ax_t = fig.add_subplot(gs[1, :])
    ax_i = fig.add_subplot(gs[2, 0])
    ax_f = fig.add_subplot(gs[2, 1])
    ax_v = fig.add_subplot(gs[3, 0])
    ax_p = fig.add_subplot(gs[3, 1])
    for v in versions:
        d = load(v, mode)
        t = d["t"].astype(float)
        dt = float(d["dt"])
        kb = int(round(1e-3 / dt))
        tb, sb = blocks(t, d["speed_rpm"].astype(float), kb)
        _, eb = blocks(t, d["Te"].astype(float), kb)
        ax_s.plot(tb, sb, color=COLORS[v], lw=1, label=NAMES[v])
        ax_t.plot(tb, eb, color=COLORS[v], lw=0.8, label=NAMES[v])
        z = (t >= 2.0) & (t <= 2.05)
        ax_i.plot(t[z], d["ia"][z], color=COLORS[v], lw=0.7, label=NAMES[v])
        w = (t >= WINDOW[0]) & (t <= WINDOW[1])
        f, m = windowed_dfft(d["ia"][w].astype(float), dt)
        band = f <= 1500
        ax_f.plot(f[band], m[band], color=COLORS[v], lw=0.7, label=NAMES[v])
        k200 = int(round(200e-6 / dt))
        va = d["va"][z].astype(float)
        n = len(va) // k200 * k200
        ax_v.plot(t[z][:n].reshape(-1, k200).mean(1), va[:n].reshape(-1, k200).mean(1), color=COLORS[v], lw=0.9, label=NAMES[v])
        fq, pq = windowed_dfft(d["Te"][w].astype(float), dt)
        ax_p.plot(fq[fq <= 1500], pq[fq <= 1500], color=COLORS[v], lw=0.7, label=NAMES[v])
    ax_s.set_ylabel("Velocidade (rpm)")
    ax_s.legend(fontsize=8)
    ax_t.set_ylabel("Torque (N·m)\n(média em 1 ms)")
    ax_i.set_ylabel("Corrente fase A (A)")
    ax_i.set_xlabel("Tempo (s)")
    ax_f.set_yscale("log")
    ax_f.set_ylim(1e-4, 20)
    ax_f.set_ylabel("Espectro da corrente (A)")
    ax_f.set_xlabel("Frequência (Hz)")
    ax_v.set_ylabel("Tensão fase A, média por período PWM (V)")
    ax_v.set_xlabel("Tempo (s)")
    ax_p.set_yscale("log")
    ax_p.set_ylim(1e-5, 20)
    ax_p.set_ylabel("Espectro do torque (N·m)")
    ax_p.set_xlabel("Frequência (Hz)")
    for x in (ax_s, ax_t, ax_i, ax_f, ax_v, ax_p):
        x.grid(alpha=0.3)
    ax_s.axvline(T_LOAD, color="gray", ls=":")
    ax_t.axvline(T_LOAD, color="gray", ls=":")
    fig.suptitle(f"{mode} a 60 Hz: feature-motor × feature-motor-bose × feature-motor-bose-arismar (carga nominal em 1 s)")
    fig.tight_layout()
    fig.savefig(FIGS / f"versoes_{mode}.png", dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    main()
