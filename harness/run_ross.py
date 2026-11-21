"""Executa uma versao do ROSS (worktree) em V/f ou FOC a 60 Hz.

Uso: run_ross.py DIR_DO_ROSS VF|FOC VARIANTE NS T_TOTAL T_CARGA SAIDA.npz
VARIANTE: jg (feature-motor), bose (feature-motor-bose), ari (arismar, ids_ref=3,2),
          ari_def (arismar, ids_ref calculado)
"""
import sys, time
import numpy as np

root, mode, variant, NS, T_TOTAL, T_CARGA, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), sys.argv[7]
sys.path.insert(0, root)
import ross  # noqa: E402
from ross.motors.motor_element import motor_example  # noqa: E402
from ross.units import Q_  # noqa: E402

assert str(ross.__file__).lower().startswith(root.lower()), ross.__file__
fs = Q_(5000, "Hz")
dt = 1 / (5000 * NS)
t = np.arange(0, T_TOTAL + 1e-3, 1e-3)
m = motor_example()
common = dict(time_step=dt, load_torque_entrance_time=T_CARGA, load_torque_ratio=6.16 / m.T_rated,
              frequency_s=fs, time_ramp=0.6667, frequency_ref=Q_(60, "Hz"))
t0 = time.time()
if mode == "VF":
    extra = {}
    r = m.run_with_inverter_vf(t, **common, **extra)
else:
    extra = {}
    if variant == "bose":
        extra["inverter_options"] = {"frequency_max": Q_(60, "Hz")}
    if variant in ("ari", "ari_rsc"):
        extra["ids_ref"] = 3.2
    if variant == "ari_rsc":
        # iguala a resistencia de curto-circuito da rede a do codigo do Arismar (Vnet de linha)
        v_net = 127 * np.sqrt(3)
        zsc = v_net**2 / (m.short_circuit_ratio_net * m.power_rated)
        xsc = zsc * m.XR_ratio_net / np.sqrt(1 + m.XR_ratio_net**2)
        m.short_circuit_resistance = xsc / m.XR_ratio_net
        print("Rsc =", m.short_circuit_resistance)
    r = m.run_with_inverter_foc(t, **common, **extra)
d = dict(t=np.asarray(r.t, dtype=np.float32), dt=dt,
         speed_rpm=(np.asarray(r.speed) * 30 / np.pi).astype(np.float32),
         Te=np.asarray(r.electric_torque, dtype=np.float32),
         ia=np.asarray(r.currents["a"], dtype=np.float32), ib=np.asarray(r.currents["b"], dtype=np.float32),
         ic=np.asarray(r.currents["c"], dtype=np.float32),
         va=np.asarray(r.voltages["a"], dtype=np.float32), vb=np.asarray(r.voltages["b"], dtype=np.float32),
         vc=np.asarray(r.voltages["c"], dtype=np.float32))
np.savez(out, **d)
print("DONE", variant, mode, NS, "%.0fs" % (time.time() - t0), flush=True)
