"""Compara o vetor medio aplicado: Bose da feature-motor-bose x Bose do arismar (tabelas)."""
import sys, numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARISMAR, BOSE  # noqa: E402

sys.path.insert(0, str(ARISMAR))
from ross.motors.motor_drive import InverterVF
from ross.units import Q_
import importlib.util
spec = importlib.util.spec_from_file_location("overmodulation", str(BOSE / "ross" / "motors" / "overmodulation.py"))
ov = importlib.util.module_from_spec(spec); spec.loader.exec_module(ov)
VDC = 296.96
inv = InverterVF(voltage_dc=VDC, frequency_s=Q_(5000, "Hz"), voltage_rated=220.0, frequency_rated=Q_(60, "Hz"))
Ts = inv.Ts
def avg_vec(peak, ang):
    refs = (peak*np.cos(ang), peak*np.cos(ang-2*np.pi/3), peak*np.cos(ang+2*np.pi/3))
    S, T1, T2, T0, _ = inv._dwell_times(*refs)
    vec = np.array([inv.V0, *inv.actv_vet[S-1], inv.V7]) - 1
    poles = VDC*(inv.sw_table[:, vec] @ np.array([T0/2, T1, T2, T0/2]))/Ts
    poles -= poles.mean()
    return poles[0], (poles[1]-poles[2])/np.sqrt(3)
for m in (0.80, 0.92, 0.94, 0.95, 0.96, 0.98, 0.995, 1.0, 1.1):
    peak = m*2*VDC/np.pi
    dmax = 0
    for ang in np.linspace(0.001, 2*np.pi-0.001, 721):
        a = avg_vec(peak, ang)
        b = ov.bose_vector(peak*np.cos(ang), peak*np.sin(ang), VDC)[:2]
        dmax = max(dmax, np.hypot(a[0]-b[0], a[1]-b[1]))
    print("BOSE m=%.3f  max|v_arismar - v_bose| = %.3g V (|v|=%.1f V)" % (m, dmax, peak))
