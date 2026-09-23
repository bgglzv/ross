"""TPIM_Comparativo2.py — Comparação de acionamentos a 50% da velocidade (TPIM 1.5hp).

Equivalente a ``MIT_RePlan_Comparativo2.py``, aplicado ao motor de 1.5 hp
de ``tpim_1p5hp_example.py``: compara Inversor V/F e Inversor FOC com
referência de frequência reduzida a 30 Hz (50% da nominal de 60 Hz), carga
nominal aplicada em t = T_LOAD. Sem cenário DOL (a fonte AC ideal não
admite referência de frequência reduzida).

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
    python TPIM_Comparativo2.py
"""

import pandas as pd

from ross.units import Q_

import mit_replan_plots as plots
import pi_robustness_common as pi
import tpim_1p5hp_example as common


OUTPUT_DIR = "figs_tpim_comparativo_2"
FREQUENCY_REF = Q_(30.0, "Hz")   # 50% da frequência/velocidade síncrona nominal


# =============================================================================
# 1. Motor e vetor de tempo (compartilhados entre os dois cenários)
# =============================================================================

motor = common.build_motor()
t = common.time_vector(tf=common.TF, dt=common.DT)


# =============================================================================
# 2. Simulação dos dois cenários de acionamento
# =============================================================================

print("Simulando cenário 1/2 — Inversor V/F (30 Hz)...")
results_vf = motor.run_with_inverter_vf(
    t,
    time_step=common.TUTORIAL_TIME_STEP,
    frequency_s=common.FREQUENCY_S,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_ref=FREQUENCY_REF,
)

print("Simulando cenário 2/2 — Inversor FOC (30 Hz)...")
results_foc = motor.run_with_inverter_foc(
    t,
    time_step=common.TUTORIAL_TIME_STEP,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_s=common.FREQUENCY_S,
    frequency_ref=FREQUENCY_REF,
)

results_by_scenario = {
    "Inversor V/F": results_vf,
    "Inversor FOC": results_foc,
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
    title="TPIM 1.5hp — Comparativo 2 — Conjugados (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Torque (N·m)",
    reference_signal=plots.get_load_torque,
    reference_name="Torque de carga (referência)",
)
plots.save_figure(fig, OUTPUT_DIR, "01_conjugados_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_speed_rpm,
    title="TPIM 1.5hp — Comparativo 2 — Velocidade (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Velocidade (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "02_velocidade_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_current_a,
    title="TPIM 1.5hp — Comparativo 2 — Corrente de Fase A (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Corrente (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "03_corrente_fase_a_tempo")

# ------------------------------------------------------------------
# Domínio da frequência
# ------------------------------------------------------------------
fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_electric_torque,
    title="TPIM 1.5hp — Comparativo 2 — Conjugados (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Magnitude do torque (N·m)",
)
plots.save_figure(fig, OUTPUT_DIR, "04_conjugados_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_speed_rpm,
    title="TPIM 1.5hp — Comparativo 2 — Velocidade (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Magnitude da velocidade (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "05_velocidade_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_current_a,
    title="TPIM 1.5hp — Comparativo 2 — Corrente de Fase A (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Magnitude da corrente (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "06_corrente_fase_a_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_line_voltage_ab,
    title="TPIM 1.5hp — Comparativo 2 — Tensão de Linha AB (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Magnitude da tensão (V)",
)
plots.save_figure(fig, OUTPUT_DIR, "07_tensao_linha_ab_freq")

print(f"\n7 gráficos comparativos (14 arquivos: 7 HTML + 7 PNG) gravados em '{OUTPUT_DIR}/'.")


# =============================================================================
# 4. Métricas de resposta ao degrau de carga (protocolo "Robustez da Sintonia PI")
# =============================================================================

torque_final = motor.Tnom
speed_final_by_scenario = {
    name: pi.pre_step_baseline(r.t, r.speed, common.T_LOAD)
    for name, r in results_by_scenario.items()
}

table_torque = pi.build_comparison_table(
    results_by_scenario,
    plots.get_electric_torque,
    {name: torque_final for name in results_by_scenario},
    "Degrau de carga - Torque",
    t_start=common.T_LOAD,
)
table_speed = pi.build_comparison_table(
    results_by_scenario,
    lambda r: r.speed,
    speed_final_by_scenario,
    "Degrau de carga - Velocidade",
    t_start=common.T_LOAD,
)

metrics_table = pd.concat([table_torque, table_speed], ignore_index=True)
metrics_csv = f"{OUTPUT_DIR}/metrics_degrau_carga.csv"
metrics_table.to_csv(metrics_csv, index=False)
print(f"\n[OK] {metrics_csv}")
print(metrics_table.to_string(index=False))
