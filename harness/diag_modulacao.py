"""Indice de modulacao do FOC (arismar) com ids_ref = 3,2 A e com o valor calculado."""
import sys, numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ARISMAR  # noqa: E402

sys.path.insert(0, str(ARISMAR))
from ross.motors import motor_drive as md
from ross.motors.motor_element import motor_example
from ross.units import Q_
ids = None if sys.argv[1] == "calc" else float(sys.argv[1])
log = []
orig = md.Inverter._svpwm
def hook(self, t, va, vb, vc):
    start = self._is_period_start()
    out = orig(self, t, va, vb, vc)
    if start:
        log.append((t, self.modulation_index))
    return out
md.Inverter._svpwm = hook
m = motor_example()
t = np.arange(0, 3.001, 1e-3)
r = m.run_with_inverter_foc(t, time_step=2e-6, load_torque_entrance_time=1.0, load_torque_ratio=6.16 / m.T_rated,
                            frequency_s=Q_(5000, "Hz"), time_ramp=0.6667, frequency_ref=Q_(60, "Hz"), ids_ref=ids)
a = np.array(log); six = 2 * np.sqrt(3) / np.pi
reg = (a[:, 0] > 2.0)
M = a[reg, 1]
print("DIAG ids_ref=%s  M medio=%.3f  M max=%.3f  frac(M>1, sobremodulacao)=%.3f  frac(saturado em seis passos)=%.3f" % (
    sys.argv[1], M.mean(), M.max(), np.mean(M > 1), np.mean(M >= six * (1 - 1e-6))), flush=True)
