"""TPIM_Comparativo2_novo.py — Teste da nova regra de sintonia a 50% da velocidade.

Equivalente a `TPIM_Comparativo1_novo.py`, mas na condição do Comparativo 2:
referência de frequência reduzida a 30 Hz (50% da nominal), sem cenário de
partida direta (a fonte AC ideal não admite referência reduzida). Compara:

    1. Inversor V/F (malha aberta)               .run_with_inverter_vf()
    2. Inversor FOC — regra antiga (`InverterFOC`, cascata fixa /8/8/8)
    3. Inversor FOC — regra nova (`InverterFOCNovo`, ver
       `inverter_foc_novo.py`)

Objetivo: verificar se a regra nova, calibrada e validada em
`TPIM_Comparativo1_novo.py` à velocidade nominal (60 Hz), continua se
comportando de forma limpa também a 50% da velocidade — condição em que o
Comparativo 2 "normal" já mostrou o V/F com desvio de velocidade bem maior
que a 60 Hz (ver `figs_tpim_comparativo_2/`).

Saída: `figs_tpim_comparativo_2_novo/`.

Uso
---
    python TPIM_Comparativo2_novo.py
"""

import pandas as pd

from ross.units import Q_
from ross.motors.utils import line_to_dc_bus, phase_to_line

from ross.motors.inverters import InverterFOC

import inverter_foc_novo as novo
import mit_replan_plots as plots
import pi_robustness_common as pi
import tpim_1p5hp_example as common


OUTPUT_DIR = "figs_tpim_comparativo_2_novo"
FREQUENCY_REF = Q_(30.0, "Hz")   # 50% da frequência/velocidade síncrona nominal


# =============================================================================
# 1. Motor e vetor de tempo (compartilhados entre os três cenários)
# =============================================================================

motor = common.build_motor()
t = common.time_vector(tf=common.TF, dt=common.DT)


# =============================================================================
# 2. Simulação dos três cenários de acionamento
# =============================================================================

print("Simulando cenário 1/3 — Inversor V/F (30 Hz)...")
results_vf = motor.run_with_inverter_vf(
    t,
    time_step=common.TUTORIAL_TIME_STEP,
    frequency_s=common.FREQUENCY_S,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_ref=FREQUENCY_REF,
)

print("Simulando cenário 2/3 — Inversor FOC (regra antiga, 30 Hz)...")
results_foc_antigo = motor.run_with_inverter_foc(
    t,
    time_step=common.TUTORIAL_TIME_STEP,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    time_ramp=common.TIME_RAMP,
    frequency_s=common.FREQUENCY_S,
    frequency_ref=FREQUENCY_REF,
)

Vnl = phase_to_line(motor.voltage_nom)
voltage_dc = line_to_dc_bus(Vnl)

# Construído só para ler os ganhos calculados pela regra antiga (o inversor
# usado na simulação do cenário 2/3 acima é interno a
# motor.run_with_inverter_foc() e não fica acessível depois que ela retorna).
inverter_antigo_probe = InverterFOC(
    voltage_dc=voltage_dc,
    frequency_s=common.FREQUENCY_S,
    voltage_nom=Vnl,
    frequency_nom=motor.frequency_nom,
    n_poles=motor.n_poles,
    speed_nom=motor.speed_nom,
    torque_nom=motor.Tnom,
    stator_resistance=motor.stator_resistance,
    rotor_resistance=motor.rotor_resistance,
    stator_reactance=motor.stator_reactance,
    rotor_reactance=motor.rotor_reactance,
    mutual_reactance=motor.mutual_reactance,
    Ip_motor=motor.Ip_motor,
    time_ramp=common.TIME_RAMP,
    frequency_ref=FREQUENCY_REF,
)

print("Simulando cenário 3/3 — Inversor FOC (regra nova, 30 Hz)...")
inverter_novo = novo.InverterFOCNovo(
    voltage_dc=voltage_dc,
    frequency_s=common.FREQUENCY_S,
    voltage_nom=Vnl,
    frequency_nom=motor.frequency_nom,
    n_poles=motor.n_poles,
    speed_nom=motor.speed_nom,
    torque_nom=motor.Tnom,
    stator_resistance=motor.stator_resistance,
    rotor_resistance=motor.rotor_resistance,
    stator_reactance=motor.stator_reactance,
    rotor_reactance=motor.rotor_reactance,
    mutual_reactance=motor.mutual_reactance,
    Ip_motor=motor.Ip_motor,
    time_ramp=common.TIME_RAMP,
    frequency_ref=FREQUENCY_REF,
)
results_foc_novo = motor.run(
    t,
    time_step=common.TUTORIAL_TIME_STEP,
    load_torque_entrance_time=common.T_LOAD,
    load_torque_ratio=1.0,
    element=inverter_novo,
)

print(
    f"\nParâmetros de sintonia — regra nova: "
    f"tau_mech={inverter_novo.tau_mech * 1000:.1f} ms, "
    f"BWp_w={inverter_novo.BWp_w_novo:.2f} Hz, BWi_w={inverter_novo.BWi_w_novo:.2f} Hz, "
    f"kp_w={inverter_novo.kp_w:.4g}, ki_w={inverter_novo.ki_w:.4g}"
)
if inverter_novo.tripped:
    print(f"[AVISO] Proteção de sobrecorrente disparou em t={inverter_novo.trip_time:.4f}s")
else:
    print("Proteção de sobrecorrente: não disparou (corrente ficou dentro do limite).")

results_by_scenario = {
    "Inversor V/F": results_vf,
    "Inversor FOC (regra antiga)": results_foc_antigo,
    "Inversor FOC (regra nova)": results_foc_novo,
}


# =============================================================================
# 3. Geração dos gráficos comparativos
# =============================================================================

plots.reset_output_dir(OUTPUT_DIR)
print(f"\nGerando gráficos comparativos em '{OUTPUT_DIR}/'...")

zoom_xlim = (common.T_LOAD - common.ZOOM_BEFORE_S, common.T_LOAD + common.ZOOM_AFTER_S)

fig = plots.compare_time(
    results_by_scenario,
    plots.get_electric_torque,
    title="TPIM 1.5hp — Regra nova — Conjugados (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Torque (N·m)",
    reference_signal=plots.get_load_torque,
    reference_name="Torque de carga (referência)",
)
plots.save_figure(fig, OUTPUT_DIR, "01_conjugados_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_electric_torque,
    title="TPIM 1.5hp — Regra nova — Conjugados (zoom na entrada da carga, 30 Hz)",
    yaxis_title="Torque (N·m)",
    reference_signal=plots.get_load_torque,
    reference_name="Torque de carga (referência)",
    xlim=zoom_xlim,
)
plots.save_figure(fig, OUTPUT_DIR, "01_conjugados_tempo_zoom")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_speed_rpm,
    title="TPIM 1.5hp — Regra nova — Velocidade (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Velocidade (RPM)",
)
plots.save_figure(fig, OUTPUT_DIR, "02_velocidade_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_speed_rpm,
    title="TPIM 1.5hp — Regra nova — Velocidade (zoom na entrada da carga, 30 Hz)",
    yaxis_title="Velocidade (RPM)",
    xlim=zoom_xlim,
)
plots.save_figure(fig, OUTPUT_DIR, "02_velocidade_tempo_zoom")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_current_a,
    title="TPIM 1.5hp — Regra nova — Corrente de Fase A (30 Hz / 50% da velocidade nominal)",
    yaxis_title="Corrente (A)",
)
plots.save_figure(fig, OUTPUT_DIR, "03_corrente_fase_a_tempo")

fig = plots.compare_time(
    results_by_scenario,
    plots.get_current_a,
    title="TPIM 1.5hp — Regra nova — Corrente de Fase A (zoom na entrada da carga, 30 Hz)",
    yaxis_title="Corrente (A)",
    xlim=zoom_xlim,
)
plots.save_figure(fig, OUTPUT_DIR, "03_corrente_fase_a_tempo_zoom")

fig = plots.compare_frequency(
    results_by_scenario,
    plots.get_electric_torque,
    title="TPIM 1.5hp — Regra nova — Conjugados (FFT, 30 Hz / 50% da velocidade nominal)",
    yaxis_title="Magnitude do torque (N·m)",
)
plots.save_figure(fig, OUTPUT_DIR, "04_conjugados_freq")

print(f"\nGráficos comparativos (HTML + PNG) gravados em '{OUTPUT_DIR}/'.")


# =============================================================================
# 4. Métricas de resposta ao degrau de carga
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

# Registro comparativo dos parâmetros de sintonia calculados pelas duas
# regras, para referência.
tuning_df = pd.DataFrame(
    [
        {
            "regra": "antiga (fs/8/8/8)",
            "BWp_w_Hz": inverter_antigo_probe.frequency_s / 64,
            "BWi_w_Hz": inverter_antigo_probe.frequency_s / 512,
            "kp_w": inverter_antigo_probe.kp_w,
            "ki_w": inverter_antigo_probe.ki_w,
        },
        {
            "regra": "nova (tau_mech)",
            "BWp_w_Hz": inverter_novo.BWp_w_novo,
            "BWi_w_Hz": inverter_novo.BWi_w_novo,
            "kp_w": inverter_novo.kp_w,
            "ki_w": inverter_novo.ki_w,
        },
    ]
)
tuning_path = f"{OUTPUT_DIR}/parametros_sintonia.csv"
tuning_df.to_csv(tuning_path, index=False)
print(f"\n[OK] {tuning_path}")
print(tuning_df.to_string(index=False))
