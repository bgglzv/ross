import ross
print("O PACOTE ROSS ESTÁ SENDO CARREGADO DE:", ross.__file__)
"""MIT_RePlan.py — Motor de Indução Trifásico M-C-5283001 (REPLAN).

Instancia o MIT WEG do compressor de gás de reciclo da Unidade de
Hidrotratamento de Diesel IV (U-5283, REPLAN) e executa uma simulação de
regime transitório de 20 s com a carga nominal aplicada em t = 10 s.

Parâmetros do circuito equivalente
-----------------------------------
Extraídos da folha 4 do datasheet I-FD-5270.00-52313-712-BI4-102 (col. Sₙ)
e convertidos de p.u. para Ω pela função ``pu_to_ohm()`` definida neste arquivo.

    Uₙ (linha)  = 4000 V      Iₙ = 422,7 A     Pₙ = 2474 kW
    fₙ = 60 Hz  nₙ = 1791 rpm  p  = 4 polos

    Sbase = √3 · Uₙ · Iₙ  →  Zbase = Uₙ² / Sbase = 5,46345 Ω

    r₁ = 0,005 pu  X₁ = 0,131 pu  r₂ = 0,005 pu  X₂ = 0,105 pu  Xₘ = 3,363 pu

Parâmetros de simulação
-----------------------
    tf    = 20 s      tempo total
    dt    = 1 ms      passo de avaliação
    Tload = 10 s      instante de aplicação da carga nominal (100 %)

Gráficos gerados (domínio do tempo e da frequência)
----------------------------------------------------
    1.  Conjugados — tempo           plot_torque()
    2.  Conjugados — frequência      plot_torque(domain="frequency")
    3.  Velocidade — tempo           plot_speed()
    4.  Velocidade — frequência      plot_speed(domain="frequency")
    5.  Correntes a-b-c — tempo      plot_phase_currents(reference_frame="a-b-c")
    6.  Correntes a-b-c — freq.      plot_phase_currents(reference_frame="a-b-c", domain="frequency")
    7.  Correntes α-β — tempo        plot_phase_currents(reference_frame="alpha-beta")
    8.  Correntes α-β — freq.        plot_phase_currents(reference_frame="alpha-beta", domain="frequency")
    9.  Correntes d-q — tempo        plot_phase_currents(reference_frame="d-q")
    10. Correntes d-q — freq.        plot_phase_currents(reference_frame="d-q", domain="frequency")
    11. Tensões de fase — tempo      plot_phase_voltages()
    12. Tensões de fase — freq.      plot_phase_voltages(domain="frequency")
    13. Tensões de linha — tempo     plot_line_voltages()
    14. Tensões de linha — freq.     plot_line_voltages(domain="frequency")

Saída em disco
--------------
Cada uma das 14 figuras é gravada em dois formatos, sob ``figs/``:
um arquivo ``.html`` (interativo, aberto em qualquer navegador) e um
``.png`` (estático, via ``kaleido``, para relatórios/apresentações).
A cada execução, o diretório ``figs/`` é apagado e recriado do zero
(ver seção 6), de modo que a saída nunca mistura figuras de execuções
diferentes.

Dependências
------------
``kaleido`` é necessário para a exportação em PNG (``fig.write_image``).
Instale com ``pip install kaleido`` caso ainda não esteja no ambiente.

Uso
---
    python MIT_RePlan.py
"""

import numpy as np

from ross.motors.motor_element import MotorElement
from ross.units import Q_


# =============================================================================
# 1. Conversão p.u. → Ω
# =============================================================================


def pu_to_ohm(r1_pu, X1_pu, r2_pu, X2_pu, Xm_pu, voltage_line, current_rated):
    """Converte parâmetros do circuito equivalente de p.u. para Ohm.

    Calcula a impedância base pelo método da potência aparente trifásica:

        Sbase = √3 · Uₙ · Iₙ
        Zbase = Uₙ² / Sbase

    Cada parâmetro em p.u. é multiplicado por Zbase.
    A tensão de fase (linha-neutro) também é retornada, pois é o valor
    esperado por ``MotorElement`` nos campos ``voltage_nom`` e ``voltage_net``.

    Parameters
    ----------
    r1_pu : float
        Resistência do estator [pu].
    X1_pu : float
        Reatância de dispersão do estator [pu].
    r2_pu : float
        Resistência do rotor referida ao estator [pu].
    X2_pu : float
        Reatância de dispersão do rotor referida ao estator [pu].
    Xm_pu : float
        Reatância de magnetização [pu].
    voltage_line : float
        Tensão de linha nominal Uₙ [V].
    current_rated : float
        Corrente nominal de linha Iₙ [A].

    Returns
    -------
    dict
        Chaves: ``Sbase``, ``Zbase``, ``r1``, ``X1``, ``r2``, ``X2``,
        ``Xm``, ``voltage_phase`` — todos em SI (VA, Ω ou V).
    """
    Sbase = np.sqrt(3.0) * voltage_line * current_rated
    Zbase = voltage_line ** 2 / Sbase
    voltage_phase = voltage_line / np.sqrt(3.0)

    return {
        "Sbase":         Sbase,
        "Zbase":         Zbase,
        "r1":            r1_pu  * Zbase,
        "X1":            X1_pu  * Zbase,
        "r2":            r2_pu  * Zbase,
        "X2":            X2_pu  * Zbase,
        "Xm":            Xm_pu  * Zbase,
        "voltage_phase": voltage_phase,
    }


# =============================================================================
# 2. Dados do motor M-C-5283001 (datasheet I-FD-5270.00-52313-712-BI4-102)
# =============================================================================

# --- Dados nominais (folha 2) ---
UN_LINE   = 4000.0   # V    (campo 9)
IN        = 422.7    # A    (campo 15)
PN_W      = 2474e3   # W    (campo 8)
FN_HZ     = 60.0     # Hz   (campo 10)
N_POLES   = 4        #      (campo 12)
SPEED_RPM = 1791.0   # rpm  (campo 12)
JP_MOTOR  = 57.5     # kg·m² (campo 37)
JP_LOAD   = 0.0      # kg·m² — inércia da carga omitida neste script
                     #         (inércia do compressor = 140 kg·m² aumentaria
                     #          o tempo de partida além dos 20 s disponíveis;
                     #          os valores de regime permanente são independentes
                     #          de Ip_load)

# --- Parâmetros em p.u. — coluna Sₙ (folha 4, campos 102–107) ---
R1_PU = 0.005
X1_PU = 0.131
R2_PU = 0.005
X2_PU = 0.105
XM_PU = 3.363

# --- Parâmetros de simulação ---
TF        = 24.0   # s   — tempo total
DT        = 1e-3   # s   — passo de avaliação
TIME_STEP = 1e-4   # s   — passo interno do integrador RK4
T_LOAD    = 16.0   # s   — instante de aplicação da carga nominal


# =============================================================================
# 3. Instanciação do MotorElement
# =============================================================================

p = pu_to_ohm(R1_PU, X1_PU, R2_PU, X2_PU, XM_PU, UN_LINE, IN)

motor = MotorElement(
    n=0,
    tag="M-C-5283001",
    power_nom=PN_W,
    voltage_nom=p["voltage_phase"],      # tensão de fase RMS [V]
    speed_nom=Q_(SPEED_RPM, "RPM"),
    frequency_nom=Q_(FN_HZ, "Hz"),
    n_poles=N_POLES,
    stator_resistance=p["r1"],
    rotor_resistance=p["r2"],
    stator_reactance=p["X1"],
    rotor_reactance=p["X2"],
    mutual_reactance=p["Xm"],
    Ip_motor=JP_MOTOR,
    viscosity_coeff=0.0,
    Ip_load=JP_LOAD,
    voltage_net=p["voltage_phase"],
    frequency_net=Q_(FN_HZ, "Hz"),
)


# =============================================================================
# 4. Simulação
# =============================================================================

t = np.arange(0.0, TF + DT, DT)

results = motor.run_direct_on_line(
    t,
    time_step=TIME_STEP,
    load_torque_entrance_time=T_LOAD,
    load_torque_ratio=1.0,
)


# =============================================================================
# 5. Pós-processamento — console
# =============================================================================

def _ss_mask(t_arr, t_start, t_end=None):
    t_end = t_arr[-1] if t_end is None else t_end
    return (t_arr >= t_start) & (t_arr <= t_end)

def _rms(signal):
    return float(np.sqrt(np.mean(signal ** 2)))

mask_nl  = _ss_mask(results.t, t_start=8.0,  t_end=9.9)
mask_nom = _ss_mask(results.t, t_start=16.0, t_end=TF)

ia_rms_nl   = _rms(results.currents["a"][mask_nl])
speed_nl    = float(np.mean(results.speed[mask_nl]))  * 60.0 / (2.0 * np.pi)
ia_rms_nom  = _rms(results.currents["a"][mask_nom])
ia_peak_nom = float(np.max(np.abs(results.currents["a"][mask_nom])))
speed_nom   = float(np.mean(results.speed[mask_nom])) * 60.0 / (2.0 * np.pi)
te_nom      = float(np.mean(results.electric_torque[mask_nom]))
slip_nom    = (1800.0 - speed_nom) / 1800.0

print("=" * 60)
print(f"  Motor: {motor.tag}")
print("=" * 60)
print("\n--- Conversão p.u. → Ω ---")
print(f"  Sbase        = {p['Sbase']:>14.2f}  VA")
print(f"  Zbase        = {p['Zbase']:>14.5f}  Ω")
print(f"  Tensão fase  = {p['voltage_phase']:>14.3f}  V")
print(f"  r1 = {p['r1']:.5f} Ω  |  X1 = {p['X1']:.5f} Ω")
print(f"  r2 = {p['r2']:.5f} Ω  |  X2 = {p['X2']:.5f} Ω  |  Xm = {p['Xm']:.5f} Ω")
print("\n--- Regime a vazio  [t = 8–10 s] ---")
print(f"  Corrente RMS  = {ia_rms_nl:>10.2f} A")
print(f"  Velocidade    = {speed_nl:>10.1f} rpm  (síncrona: 1800 rpm)")
print("\n--- Carga nominal  [t = 16–20 s] ---")
print(f"  Corrente RMS  = {ia_rms_nom:>10.2f} A   (datasheet: 422,7 A)")
print(f"  Corrente pico = {ia_peak_nom:>10.2f} A")
print(f"  Velocidade    = {speed_nom:>10.1f} rpm  (datasheet: 1791 rpm)")
print(f"  Conjugado     = {te_nom:>10.1f} N·m  (datasheet: 13 192 N·m)")
print(f"  Escorregamento= {slip_nom*100:>10.3f} %%  (esperado: 0,500 %%)")
print("=" * 60)


# =============================================================================
# 6. Geração de gráficos
# =============================================================================
# Todos os métodos de plotagem disponíveis em MotorResponseResults são chamados
# abaixo, nas duas variantes de domínio (tempo e frequência) e, para as
# correntes, nas três referências possíveis (a-b-c, alpha-beta, d-q).
#
# Os gráficos são gravados como arquivos HTML independentes (um por figura),
# para que possam ser abertos em qualquer navegador sem dependência adicional,
# e também como PNG (via kaleido) para uso em relatórios/apresentações.
#
# O diretório de saída é apagado (shutil.rmtree) e recriado no início desta
# seção, de modo que cada execução do script substitui integralmente as
# figuras da execução anterior — nunca ficam arquivos órfãos em figs/.
#
# Estrutura de arquivos gerada (para cada nome-base, um .html e um .png):
#   figs/01_conjugados_tempo
#   figs/02_conjugados_freq
#   figs/03_velocidade_tempo
#   figs/04_velocidade_freq
#   figs/05_correntes_abc_tempo
#   figs/06_correntes_abc_freq
#   figs/07_correntes_alphabeta_tempo
#   figs/08_correntes_alphabeta_freq
#   figs/09_correntes_dq_tempo
#   figs/10_correntes_dq_freq
#   figs/11_tensoes_fase_tempo
#   figs/12_tensoes_fase_freq
#   figs/13_tensoes_linha_tempo
#   figs/14_tensoes_linha_freq
# =============================================================================

import os
import shutil

OUTPUT_DIR = "figs"
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def _save(fig, basename):
    """Grava a figura como HTML e PNG e confirma no console."""
    html_path = os.path.join(OUTPUT_DIR, f"{basename}.html")
    png_path = os.path.join(OUTPUT_DIR, f"{basename}.png")
    fig.write_html(html_path)
    fig.write_image(png_path)
    print(f"  [OK] {html_path}")
    print(f"  [OK] {png_path}")


print(f"\nGerando gráficos em '{OUTPUT_DIR}/'...")

# ------------------------------------------------------------------
# 1–2  Conjugados eletromagnético e de carga
# ------------------------------------------------------------------
fig = results.plot_torque(domain="time")
_save(fig, "01_conjugados_tempo")

fig = results.plot_torque(domain="frequency")
_save(fig, "02_conjugados_freq")

# ------------------------------------------------------------------
# 3–4  Velocidade do rotor
# ------------------------------------------------------------------
fig = results.plot_speed(domain="time", speed_units="RPM")
_save(fig, "03_velocidade_tempo")

fig = results.plot_speed(domain="frequency", speed_units="RPM")
_save(fig, "04_velocidade_freq")

# ------------------------------------------------------------------
# 5–6  Correntes — referencial a-b-c
# ------------------------------------------------------------------
fig = results.plot_phase_currents(reference_frame="a-b-c", domain="time")
_save(fig, "05_correntes_abc_tempo")

fig = results.plot_phase_currents(reference_frame="a-b-c", domain="frequency")
_save(fig, "06_correntes_abc_freq")

# ------------------------------------------------------------------
# 7–8  Correntes — referencial α-β (Clarke)
# ------------------------------------------------------------------
fig = results.plot_phase_currents(reference_frame="alpha-beta", domain="time")
_save(fig, "07_correntes_alphabeta_tempo")

fig = results.plot_phase_currents(reference_frame="alpha-beta", domain="frequency")
_save(fig, "08_correntes_alphabeta_freq")

# ------------------------------------------------------------------
# 9–10  Correntes — referencial d-q (Park)
# ------------------------------------------------------------------
fig = results.plot_phase_currents(reference_frame="d-q", domain="time")
_save(fig, "09_correntes_dq_tempo")

fig = results.plot_phase_currents(reference_frame="d-q", domain="frequency")
_save(fig, "10_correntes_dq_freq")

# ------------------------------------------------------------------
# 11–12  Tensões de fase (linha-neutro)
# ------------------------------------------------------------------
fig = results.plot_phase_voltages(domain="time")
_save(fig, "11_tensoes_fase_tempo")

fig = results.plot_phase_voltages(domain="frequency")
_save(fig, "12_tensoes_fase_freq")

# ------------------------------------------------------------------
# 13–14  Tensões de linha (linha-linha)
# ------------------------------------------------------------------
fig = results.plot_line_voltages(domain="time")
_save(fig, "13_tensoes_linha_tempo")

fig = results.plot_line_voltages(domain="frequency")
_save(fig, "14_tensoes_linha_freq")

print(f"\n14 gráficos (28 arquivos: 14 HTML + 14 PNG) gravados em '{OUTPUT_DIR}/'.")
