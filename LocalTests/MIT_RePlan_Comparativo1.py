"""MIT_RePlan_Comparativo1.py — Comparação de acionamentos à velocidade nominal.

Simula o MIT M-C-5283001 (REPLAN) — os mesmos parâmetros elétricos e de
simulação de ``MIT_RePlan.py`` (ver ``mit_replan_common.py``) — sob três
formas de acionamento distintas, todas visando a velocidade/frequência
nominal, com a carga nominal aplicada em t = T_LOAD:

    1. Fonte AC ideal, tensão nominal aplicada diretamente
       (partida direta - DOL)              .run_direct_on_line()
    2. Inversor V/F (controle escalar
       em malha aberta)                    .run_with_inverter_vf()
    3. Inversor FOC (controle vetorial
       por orientação de campo, malha
       fechada)                            .run_with_inverter_foc()

Para cada uma das grandezas abaixo, é gerado um único gráfico sobrepondo
os três cenários (uma curva por acionamento), permitindo comparar
diretamente o comportamento transitório e de regime.

Domínio do tempo
-----------------
    1. Conjugados (eletromagnético + carga de referência)
    2. Velocidade do rotor
    3. Corrente de estator — fase A

Domínio da frequência
----------------------
    4. Conjugados (eletromagnético)
    5. Velocidade do rotor
    6. Corrente de estator — fase A
    7. Tensão de linha AB

Uso
---
    python MIT_RePlan_Comparativo1.py
"""

from ross.units import Q_

import mit_replan_common as common
import mit_replan_plots as plots


OUTPUT_DIR = "figs_comparativo_1"


# =============================================================================
# 1. Motor e vetor de tempo (compartilhados entre os três cenários)
# =============================================================================

motor, p = common.build_motor()
t = common.time_vector()


# =============================================================================
# 2. Simulação dos três cenários de acionamento
# =============================================================================

print("Simulando cenário 1/3 — Fonte AC direta (DOL)...")
results_ac = motor.run_direct_on_line(
    t,
    time_step=common.TIME_STEP,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
)

print("Simulando cenário 2/3 — Inversor V/F...")
results_vf = motor.run_with_inverter_vf(
    t,
    frequency_s=common.FREQUENCY_S,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_ref=Q_(common.FN_HZ, "Hz"),
)

print("Simulando cenário 3/3 — Inversor FOC...")
results_foc = motor.run_with_inverter_foc(
    t,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_s=common.FREQUENCY_S,
    frequency_ref=Q_(common.FN_HZ, "Hz"),
)

results_by_scenario = {
    "AC Source (DOL)": results_ac,
    "V/F Inverter": results_vf,
    "FOC Inverter": results_foc,
}


# =============================================================================
# 3. Geração dos gráficos comparativos
# =============================================================================

plots.reset_output_dir(OUTPUT_DIR)
print(f"\nGerando gráficos comparativos em '{OUTPUT_DIR}/'...")

# ------------------------------------------------------------------
# Domínio do tempo
# ------------------------------------------------------------------
fig = plots.compare_time(
    results_by_scenario,
    plots.get_electric_torque,
    title="Comparativo 1 — Conjugados (velocidade nominal)",
    yaxis_title="Torque (N·m)",
    reference_signal=plots.get_load_torque,
    reference_name="Load Torque (reference)",
)
plots.save_figure(fig, OUTPUT_DIR, "01_conjugados_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_speed_rpm,
    title="Comparativo 1 — Velocidade (velocidade nominal)",
    yaxis_title="Speed (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "02_velocidade_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_current_a,
    title="Comparativo 1 — Corrente de Fase A (velocidade nominal)",
    yaxis_title="Current (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "03_corrente_fase_a_tempo")

# ------------------------------------------------------------------
# Domínio da frequência
# ------------------------------------------------------------------
fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_electric_torque,
    title="Comparativo 1 — Conjugados (FFT, velocidade nominal)",
    yaxis_title="Torque magnitude (N·m)",
)
plots.save_figure(fig, OUTPUT_DIR, "04_conjugados_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_speed_rpm,
    title="Comparativo 1 — Velocidade (FFT, velocidade nominal)",
    yaxis_title="Speed magnitude (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "05_velocidade_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_current_a,
    title="Comparativo 1 — Corrente de Fase A (FFT, velocidade nominal)",
    yaxis_title="Current magnitude (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "06_corrente_fase_a_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_line_voltage_ab,
    title="Comparativo 1 — Tensão de Linha AB (FFT, velocidade nominal)",
    yaxis_title="Voltage magnitude (V)",
)
plots.save_figure(fig, OUTPUT_DIR, "07_tensao_linha_ab_freq")

print(f"\n7 gráficos comparativos (14 arquivos: 7 HTML + 7 PNG) gravados em '{OUTPUT_DIR}/'.")
