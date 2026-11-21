"""Executa o codigo original do Arismar (Codigos_MIT-SVPWM_Final) sem graficos.

Uso: run_standalone.py VF|FOC NS T_TOTAL T_CARGA SAIDA.npz
Replica o laco principal de main_vf_v2.py / main_foc_v2.py (mesmos parametros).
"""
import sys, time
import numpy as np

mode, NS, T_TOTAL, T_CARGA, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CODIGOS_ARISMAR  # noqa: E402

FOLDER = str(CODIGOS_ARISMAR / mode)
sys.path.insert(0, FOLDER)

from motor_element import MotorElement  # noqa: E402

Pn, Nn, fn, NP, Tn, Jm = 1.5, 1710, 60, 4, 6.16, 0.0372
Vn = 127 * np.sqrt(3)
Rs, Rr, Xls, Xlr, Xm = 2.5, 1.8, 1.3, 1.3, 43.08
Vcc, fs = 1.35 * Vn, 5000
deltat = 1 / (fs * NS)
N_ref, tramp = 1800, 0.6667
t = np.arange(0, T_TOTAL, deltat)
Nt = len(t)

kw = dict(n=0, Pnom=Pn * 735.499, Vnom=Vn, RPMnom=Nn, fnom=fn, npol=NP, Rs=Rs, Rr=Rr,
          Xls=Xls, Xlr=Xlr, Xm=Xm, Jm=Jm, Bm=0.0, Jl=0.0)
if mode == "VF":
    motor = MotorElement(**kw, Vnet=Vn)
else:
    motor = MotorElement(**kw)

out_arr = {k: np.zeros(Nt, dtype=np.float32) for k in ("speed_rpm", "Te", "ia", "ib", "ic", "va", "vb", "vc")}
t0 = time.time()
if mode == "VF":
    from inverter_vf_v2 import inverter_vf
    inv = inverter_vf(Vcc=Vcc, fs=fs, deltat=deltat, Vn=Vn, fn=fn, tramp=tramp)
    fref = N_ref * NP / 120
    for i in range(Nt):
        tt = t[i]
        TL = 0.0 if tt < T_CARGA else Tn
        va, vb, vc, freq = inv.calc(fref, tt)
        r = motor.calc(deltat, tt, va, vb, vc, TL, 2 * np.pi * freq)
        out_arr["speed_rpm"][i] = r["RPM"]; out_arr["Te"][i] = r["TE"]
        out_arr["ia"][i] = r["Ias"]; out_arr["ib"][i] = r["Ibs"]; out_arr["ic"][i] = r["Ics"]
        out_arr["va"][i] = va; out_arr["vb"][i] = vb; out_arr["vc"][i] = vc
else:
    from inverter_foc_v2 import inverter_foc
    wref = N_ref * np.pi / 30
    inv = inverter_foc(vcc=Vcc, fs=fs, fn=fn, deltat=deltat, motor=motor, tramp=tramp, ids_ref=3.2, N_ref=N_ref)
    wr = ia = ib = ic = 0.0
    for i in range(Nt):
        tt = t[i]
        TL = 0.0 if tt < T_CARGA else Tn
        ri = inv.calc(wref, tt, wr, ia, ib, ic, deltat)
        va, vb, vc, weixo = ri["va"], ri["vb"], ri["vc"], ri["weixo"]
        r = motor.calc(deltat, tt, va, vb, vc, TL, weixo)
        wr, ia, ib, ic = r["wr"], r["Ias"], r["Ibs"], r["Ics"]
        out_arr["speed_rpm"][i] = r["RPM"]; out_arr["Te"][i] = r["TE"]
        out_arr["ia"][i] = ia; out_arr["ib"][i] = ib; out_arr["ic"][i] = ic
        out_arr["va"][i] = va; out_arr["vb"][i] = vb; out_arr["vc"][i] = vc
np.savez(out, t=t.astype(np.float32), dt=deltat, **out_arr)
print("DONE standalone", mode, NS, "%.0fs" % (time.time() - t0), flush=True)
