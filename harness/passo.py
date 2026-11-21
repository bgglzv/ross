"""Sensibilidade ao passo de integracao (NS amostras por periodo de chaveamento)."""
import json
import numpy as np
import analyze as an

rows = {}
cases = [("jg", "FOC", [20, 100]), ("bose", "FOC", [20, 100]), ("ari", "FOC", [20, 40, 100]),
         ("bose", "VF", [20, 100]), ("ari", "VF", [20, 40, 100])]
for v, mode, nss in cases:
    for ns in nss:
        name = f"{v}_{mode}" + ("" if ns == 100 else f"_ns{ns}")
        import pathlib
        p = an.RUNS / f"{name}.npz"
        d = np.load(p); d = {k: d[k] for k in d.files}
        m = an.metrics(d)
        rows[f"{v}_{mode}_NS{ns}"] = m
        print("PASSO", v, mode, "NS=%3d" % ns, "THDi=%.2f%%  ripple=%.1f%%  torque_vazio=[%.2f, %.2f]  I1=%.2f  f1=%.2f  vel=%.1f" % (
            m["THD_corrente_pct"], m["ripple_torque_rms_pct"], m["torque_vazio_min_Nm"], m["torque_vazio_max_Nm"], m["I1_pico_A"], m["f1_hz"], m["velocidade_final_rpm"]))
(an.REPORT / "metricas_passo.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
