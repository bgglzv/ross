"""MIT_RePlan_Comparativo2.py — Comparação de acionamentos a 50% da velocidade.

Simula o MIT M-C-5283001 (REPLAN) — os mesmos parâmetros elétricos e de
simulação de ``MIT_RePlan.py`` (ver ``mit_replan_common.py``) — sob duas
formas de acionamento com referência de frequência reduzida a 30 Hz (metade
da frequência nominal de 60 Hz, ou seja, ~50 % da velocidade síncrona), com
a carga nominal aplicada em t = T_LOAD:

    1. Inversor V/F (controle escalar
       em malha aberta)                    .run_with_inverter_vf()
    2. Inversor FOC (controle vetorial
       por orientação de campo, malha
       fechada)                            .run_with_inverter_foc()

Não há cenário de fonte AC direta aqui: a fonte ideal opera sempre na
frequência da rede (60 Hz) e não admite uma referência de frequência
reduzida — por isso este comparativo se restringe aos dois acionamentos
por inversor.

Para cada uma das grandezas abaixo, é gerado um único gráfico sobrepondo
os dois cenários (uma curva por acionamento).

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
    python MIT_RePlan_Comparativo2.py
"""

from ross.units import Q_

import mit_replan_common as common
import mit_replan_plots as plots


OUTPUT_DIR = "figs_comparativo_2"
FREQUENCY_REF = Q_(30.0, "Hz")   # 50% da frequência/velocidade síncrona nominal


# =============================================================================
# 1. Motor e vetor de tempo (compartilhados entre os dois cenários)
# =============================================================================

motor, p = common.build_motor()
t = common.time_vector()


# =============================================================================
# 2. Simulação dos dois cenários de acionamento
# =============================================================================

print("Simulando cenário 1/2 — Inversor V/F (30 Hz)...")
results_vf = motor.run_with_inverter_vf(
    t,
    frequency_s=common.FREQUENCY_S,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_ref=FREQUENCY_REF,
)

print("Simulando cenário 2/2 — Inversor FOC (30 Hz)...")
results_foc = motor.run_with_inverter_foc(
    t,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_s=common.FREQUENCY_S,
    frequency_ref=FREQUENCY_REF,
)

results_by_scenario = {
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
    title="Comparativo 2 — Conjugados (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Torque (N·m)",
    reference_signal=plots.get_load_torque,
    reference_name="Load Torque (reference)",
)
plots.save_figure(fig, OUTPUT_DIR, "01_conjugados_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_speed_rpm,
    title="Comparativo 2 — Velocidade (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Speed (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "02_velocidade_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_current_a,
    title="Comparativo 2 — Corrente de Fase A (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Current (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "03_corrente_fase_a_tempo")

# ------------------------------------------------------------------
# Domínio da frequência
# ------------------------------------------------------------------
fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_electric_torque,
    title="Comparativo 2 — Conjugados (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Torque magnitude (N·m)",
)
plots.save_figure(fig, OUTPUT_DIR, "04_conjugados_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_speed_rpm,
    title="Comparativo 2 — Velocidade (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Speed magnitude (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "05_velocidade_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_current_a,
    title="Comparativo 2 — Corrente de Fase A (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Current magnitude (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "06_corrente_fase_a_freq")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_line_voltage_ab,
    title="Comparativo 2 — Tensão de Linha AB (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Voltage magnitude (V)",
)
plots.save_figure(fig, OUTPUT_DIR, "07_tensao_linha_ab_freq")

print(f"\n7 gráficos comparativos (14 arquivos: 7 HTML + 7 PNG) gravados em '{OUTPUT_DIR}/'.")
