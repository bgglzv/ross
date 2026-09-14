"""Tests for the WEG Induction Motor M-C-5283001.

Motor: 2474 kW / 4000 V / 60 Hz / 4 poles — Recycle Gas Compressor
Plant: REPLAN — U-5283 Unidade de Hidrotratamento de Diesel IV
Document: I-FD-5270.00-52313-712-BI4-102 (rev. D, 23-JAN-24)

Parâmetros do circuito equivalente
-----------------------------------
Os valores em p.u. (coluna Sₙ, folha 4 do datasheet) são convertidos para
Ohm por meio de ``pu_to_ohm()``, conforme detalhado no documento
"Pu-Ohm_Conversao.docx":

    Sbase = √3 · Uₙ · Iₙ = √3 × 4000 V × 422,7 A = 2 928 551,51 VA
    Zbase = Uₙ² / Sbase = 4000² / 2 928 551,51 = 5,46345 Ω

    r₁  = 0,005 pu  →  0,02732 Ω
    X₁  = 0,131 pu  →  0,71571 Ω
    r₂  = 0,005 pu  →  0,02732 Ω
    X₂  = 0,105 pu  →  0,57366 Ω
    Xₘ  = 3,363 pu  →  18,37359 Ω

Testes implementados
--------------------
Grupo 1 – Conversão p.u. → Ω
    Verifica Zbase, Sbase, tensão de fase e cada parâmetro convertido.

Grupo 2 – Parâmetros do MotorElement instanciado
    Potência nominal, conjugado nominal (Tnom), velocidade, frequência e
    número de polos.

Grupo 3 – Operação a vazio
    Velocidade ≈ 1800 rpm, corrente de magnetização ≈ 121 A rms e
    conjugado próximo de zero.

Grupo 4 – Carga nominal
    Corrente ≈ 422,7 A rms, velocidade ≈ 1791 rpm, conjugado ≈ 13 192 N·m
    e escorregamento ≈ 0,5 %.

Parâmetros de simulação
-----------------------
    dt_eval   : 1 ms      passo de avaliação dos resultados
    time_step : 0,1 ms    passo interno do integrador RK4
    tf        : 20 s      tempo total para ambas as simulações

    Janela de regime permanente — a vazio    : t ∈ [8, 20] s
    Janela de regime permanente — carga nom. : t ∈ [16, 20] s

Notas sobre a dinâmica de partida
----------------------------------
A inércia total do motor (Jm = 57,5 kg·m²) implica tempo de partida
elevado: o eixo atinge velocidade síncrona (~1800 rpm) apenas após ~7-8 s.
Por isso a janela de regime permanente começa em t = 8 s para a simulação
a vazio, e a carga nominal só é aplicada em t = 8 s (após o motor atingir
velocidade próxima ao síncrono).

A inércia da carga (Jext = 140 kg·m²) não é incluída no MotorElement
durante os testes de regime elétrico: o parâmetro ``Ip_load = 0`` garante
que a partida não ultrapasse o tempo de simulação tf = 20 s.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose

from ross.motor.motor_element import MotorElement
from ross.units import Q_


# ---------------------------------------------------------------------------
# Conversão p.u. → Ohm
# ---------------------------------------------------------------------------


def pu_to_ohm(
    r1_pu: float,
    X1_pu: float,
    r2_pu: float,
    X2_pu: float,
    Xm_pu: float,
    voltage_line: float,
    current_rated: float,
) -> dict:
    """Converte os parâmetros do circuito equivalente de p.u. para Ohm.

    A impedância base é calculada a partir da potência aparente trifásica
    (Sbase = √3 · Uₙ · Iₙ) e da tensão de linha nominal (Uₙ):

        Zbase = Uₙ² / Sbase

    Parameters
    ----------
    r1_pu : float
        Resistência do estator em p.u. (coluna Sₙ do datasheet).
    X1_pu : float
        Reatância de dispersão do estator em p.u.
    r2_pu : float
        Resistência do rotor referida ao estator em p.u.
    X2_pu : float
        Reatância de dispersão do rotor referida ao estator em p.u.
    Xm_pu : float
        Reatância de magnetização em p.u.
    voltage_line : float
        Tensão de linha nominal [V].
    current_rated : float
        Corrente nominal de linha [A].

    Returns
    -------
    dict
        Dicionário com as chaves:

        - ``"Zbase"``        : impedância base [Ω]
        - ``"Sbase"``        : potência aparente base [VA]
        - ``"r1"``           : resistência do estator [Ω]
        - ``"X1"``           : reatância de dispersão do estator [Ω]
        - ``"r2"``           : resistência do rotor ref. ao estator [Ω]
        - ``"X2"``           : reatância de dispersão do rotor ref. ao estator [Ω]
        - ``"Xm"``           : reatância de magnetização [Ω]
        - ``"voltage_phase"`` : tensão de fase (linha-neutro) RMS [V]

    Examples
    --------
    >>> params = pu_to_ohm(0.005, 0.131, 0.005, 0.105, 3.363, 4000.0, 422.7)
    >>> round(params["Zbase"], 5)
    5.46345
    >>> round(params["r1"], 5)
    0.02732
    >>> round(params["Xm"], 5)
    18.37359
    """
    Sbase = np.sqrt(3.0) * voltage_line * current_rated
    Zbase = voltage_line**2 / Sbase
    voltage_phase = voltage_line / np.sqrt(3.0)

    return {
        "Sbase": Sbase,
        "Zbase": Zbase,
        "r1": r1_pu * Zbase,
        "X1": X1_pu * Zbase,
        "r2": r2_pu * Zbase,
        "X2": X2_pu * Zbase,
        "Xm": Xm_pu * Zbase,
        "voltage_phase": voltage_phase,
    }


# ---------------------------------------------------------------------------
# Parâmetros do motor M-C-5283001 (datasheet I-FD-5270.00-52313-712-BI4-102)
# ---------------------------------------------------------------------------

# --- Dados nominais — folha 2 ---
_UN_LINE   = 4000.0   # V    campo 9  — tensão nominal de linha
_IN        = 422.7    # A    campo 15 — corrente nominal
_PN_kW     = 2474.0   # kW   campo 8  — potência nominal
_FN        = 60.0     # Hz   campo 10 — frequência nominal
_N_POLES   = 4        #      campo 12 — número de polos
_SPEED_RPM = 1791.0   # rpm  campo 12 — velocidade nominal
_TN_NM     = 13192.0  # N·m  campo 30 — conjugado nominal
_JP_MOTOR  = 57.5     # kg·m² campo 37 — inércia do motor
_JP_LOAD   = 140.0    # kg·m² campo 38 — inércia da carga (compressor)

# --- Parâmetros em p.u. — coluna Sₙ — folha 4, campos 102-107 ---
_R1_PU = 0.005
_X1_PU = 0.131
_R2_PU = 0.005
_X2_PU = 0.105
_XM_PU = 3.363

# --- Parâmetros de simulação ---
_DT_EVAL   = 1e-3    # s  passo de avaliação (t_eval)
_TIME_STEP = 1e-4    # s  passo interno do integrador RK4
_TF        = 20.0    # s  tempo total de simulação (ambas as condições)
_T_SS_NL   = 8.0     # s  início da janela de regime permanente — a vazio
_T_SS_NOM  = 16.0    # s  início da janela de regime permanente — carga nominal
_TLOAD     = 8.0     # s  instante de aplicação da carga nominal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ohm_params():
    """Retorna os parâmetros convertidos de p.u. para Ω."""
    return pu_to_ohm(
        _R1_PU, _X1_PU, _R2_PU, _X2_PU, _XM_PU,
        _UN_LINE, _IN,
    )


@pytest.fixture(scope="module")
def motor_m_c_5283001(ohm_params):
    """Instância do MotorElement com os parâmetros do motor M-C-5283001.

    Notas
    -----
    - ``Ip_load = 0``: a inércia da carga do compressor (140 kg·m²) não é
      incluída aqui para manter o tempo de partida dentro de tf = 20 s. Os
      valores de regime permanente (corrente, velocidade, conjugado) são
      independentes de Ip_load.
    - ``voltage_nom`` e ``voltage_net`` recebem a tensão de fase (Uₙ / √3)
      em valor eficaz (RMS), que é a grandeza esperada pelo MotorElement e
      pelo SourceAC.
    """
    p = ohm_params
    return MotorElement(
        n=0,
        tag="M-C-5283001",
        power_nom=_PN_kW * 1e3,
        voltage_nom=p["voltage_phase"],
        speed_nom=Q_(_SPEED_RPM, "RPM"),
        frequency_nom=Q_(_FN, "Hz"),
        n_poles=_N_POLES,
        stator_resistance=p["r1"],
        rotor_resistance=p["r2"],
        stator_reactance=p["X1"],
        rotor_reactance=p["X2"],
        mutual_reactance=p["Xm"],
        Ip_motor=_JP_MOTOR,
        viscosity_coeff=0.0,
        Ip_load=0.0,
        voltage_net=p["voltage_phase"],
        frequency_net=Q_(_FN, "Hz"),
    )


@pytest.fixture(scope="module")
def results_no_load(motor_m_c_5283001):
    """Simulação a vazio (sem carga mecânica), tf = 20 s.

    Com a inércia do motor (Jm = 57,5 kg·m²), o eixo atinge velocidade
    próxima ao síncrono em ~7-8 s. A janela de regime permanente começa
    em t = 8 s.
    """
    t = np.arange(0.0, _TF + _DT_EVAL, _DT_EVAL)
    return motor_m_c_5283001.run_with_AC_source(
        t,
        time_step=_TIME_STEP,
        load_torque_entrance_time=_TF + 1.0,  # sem carga durante todo o ensaio
        load_torque_ratio=0.0,
    )


@pytest.fixture(scope="module")
def results_nominal_load(motor_m_c_5283001):
    """Simulação com carga nominal aplicada em t = 8 s, tf = 20 s.

    A carga é aplicada somente após o motor ter atingido velocidade próxima
    ao síncrono (~7-8 s), garantindo convergência numérica do integrador RK4.
    A janela de regime permanente começa em t = 16 s.
    """
    t = np.arange(0.0, _TF + _DT_EVAL, _DT_EVAL)
    return motor_m_c_5283001.run_with_AC_source(
        t,
        time_step=_TIME_STEP,
        load_torque_entrance_time=_TLOAD,
        load_torque_ratio=1.0,
    )


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def rms(signal):
    """Retorna o valor RMS de *signal*."""
    return float(np.sqrt(np.mean(signal**2)))


def ss_mask(t, t_start, t_end=None):
    """Máscara booleana para a janela de regime permanente [t_start, t_end]."""
    if t_end is None:
        t_end = t[-1]
    return (t >= t_start) & (t <= t_end)


# ---------------------------------------------------------------------------
# Grupo 1 — Conversão p.u. → Ω
# ---------------------------------------------------------------------------


def test_zbase(ohm_params):
    """Zbase deve ser 5,46345 Ω conforme "Pu-Ohm_Conversao.docx"."""
    assert_allclose(ohm_params["Zbase"], 5.46345, rtol=1e-4)


def test_sbase(ohm_params):
    """Sbase deve ser 2 928 551,51 VA (√3 × 4000 V × 422,7 A)."""
    assert_allclose(ohm_params["Sbase"], 2_928_551.51, rtol=1e-4)


def test_voltage_phase(ohm_params):
    """Tensão de fase deve ser 4000 / √3 ≈ 2309,40 V."""
    assert_allclose(ohm_params["voltage_phase"], _UN_LINE / np.sqrt(3.0), rtol=1e-6)


def test_r1_ohm(ohm_params):
    """r₁ = 0,005 pu × Zbase → 0,02732 Ω."""
    assert_allclose(ohm_params["r1"], 0.02732, rtol=1e-3)


def test_X1_ohm(ohm_params):
    """X₁ = 0,131 pu × Zbase → 0,71571 Ω."""
    assert_allclose(ohm_params["X1"], 0.71571, rtol=1e-3)


def test_r2_ohm(ohm_params):
    """r₂ = 0,005 pu × Zbase → 0,02732 Ω (igual a r₁, conforme datasheet)."""
    assert_allclose(ohm_params["r2"], 0.02732, rtol=1e-3)


def test_X2_ohm(ohm_params):
    """X₂ = 0,105 pu × Zbase → 0,57366 Ω."""
    assert_allclose(ohm_params["X2"], 0.57366, rtol=1e-3)


def test_Xm_ohm(ohm_params):
    """Xₘ = 3,363 pu × Zbase → 18,37359 Ω."""
    assert_allclose(ohm_params["Xm"], 18.37359, rtol=1e-3)


# ---------------------------------------------------------------------------
# Grupo 2 — Parâmetros do MotorElement instanciado
# ---------------------------------------------------------------------------


def test_motor_power_nom(motor_m_c_5283001):
    """Potência nominal deve ser 2 474 000 W (campo 8 do datasheet)."""
    assert_allclose(motor_m_c_5283001.power_nom, 2_474_000.0, rtol=1e-6)


def test_motor_tnom(motor_m_c_5283001):
    """Tnom interno = Pₙ / ωᵣ ≈ 13 190,93 N·m (datasheet campo 30: 13 192 N·m)."""
    # A diferença de ~1 N·m deve-se às perdas por dispersão (stray losses),
    # que não são modeladas pelo circuito T simplificado.
    assert_allclose(motor_m_c_5283001.Tnom, 13_190.93, rtol=1e-3)


def test_motor_speed_nom_rpm(motor_m_c_5283001):
    """Velocidade nominal deve ser 1791 rpm (campo 12)."""
    speed_rpm = motor_m_c_5283001.speed_nom * 60.0 / (2.0 * np.pi)
    assert_allclose(speed_rpm, _SPEED_RPM, rtol=1e-4)


def test_motor_frequency_nom_hz(motor_m_c_5283001):
    """Frequência nominal deve ser 60 Hz (campo 10)."""
    freq_hz = motor_m_c_5283001.frequency_nom / (2.0 * np.pi)
    assert_allclose(freq_hz, _FN, rtol=1e-6)


def test_motor_n_poles(motor_m_c_5283001):
    """Motor deve ter 4 polos (campo 12)."""
    assert motor_m_c_5283001.n_poles == _N_POLES


# ---------------------------------------------------------------------------
# Grupo 3 — Operação a vazio
#   Janela de regime permanente: t ∈ [8, 20] s
# ---------------------------------------------------------------------------


def test_no_load_speed(results_no_load):
    """A vazio, velocidade ≈ 1800 rpm (velocidade síncrona, escorregamento ≈ 0)."""
    mask = ss_mask(results_no_load.t, _T_SS_NL)
    speed_rpm = np.mean(results_no_load.speed[mask]) * 60.0 / (2.0 * np.pi)
    # Tolerância: ±2 rpm
    assert_allclose(speed_rpm, 1800.0, atol=2.0,
                    err_msg=f"Velocidade a vazio fora da faixa: {speed_rpm:.2f} rpm")


def test_no_load_current_rms(results_no_load):
    """A vazio, corrente RMS ≈ 121 A (corrente de magnetização, << Iₙ = 422,7 A)."""
    mask = ss_mask(results_no_load.t, _T_SS_NL)
    ia_rms = rms(results_no_load.currents["a"][mask])
    # Corrente de magnetização: Iₘ = Vph / Xm = 2309,4 / 18,37 ≈ 125,7 A (fase)
    # Tolerância: ±10 %
    assert_allclose(ia_rms, 121.0, rtol=0.10,
                    err_msg=f"Corrente a vazio RMS fora da faixa: {ia_rms:.2f} A")


def test_no_load_torque_near_zero(results_no_load):
    """A vazio, conjugado eletromagnético médio deve ser próximo de zero."""
    mask = ss_mask(results_no_load.t, _T_SS_NL)
    te_mean = float(np.mean(np.abs(results_no_load.electric_torque[mask])))
    # Modelo sem atrito (viscosity_coeff = 0): |Te| < 1 N·m em regime
    assert te_mean < 1.0, (
        f"Conjugado a vazio elevado: {te_mean:.4f} N·m (esperado < 1 N·m)"
    )


def test_no_load_current_below_rated(results_no_load):
    """A corrente a vazio deve ser menor que a corrente nominal (422,7 A)."""
    mask = ss_mask(results_no_load.t, _T_SS_NL)
    ia_rms = rms(results_no_load.currents["a"][mask])
    assert ia_rms < _IN, (
        f"Corrente a vazio ({ia_rms:.1f} A) não é menor que In ({_IN} A)"
    )


# ---------------------------------------------------------------------------
# Grupo 4 — Carga nominal
#   Janela de regime permanente: t ∈ [16, 20] s
# ---------------------------------------------------------------------------


def test_nominal_load_speed(results_nominal_load):
    """Com carga nominal, velocidade ≈ 1791 rpm (campo 12 do datasheet)."""
    mask = ss_mask(results_nominal_load.t, _T_SS_NOM)
    speed_rpm = np.mean(results_nominal_load.speed[mask]) * 60.0 / (2.0 * np.pi)
    # Tolerância: ±10 rpm (±0,6 %)
    assert_allclose(speed_rpm, _SPEED_RPM, atol=10.0,
                    err_msg=f"Velocidade nominal fora da faixa: {speed_rpm:.2f} rpm")


def test_nominal_load_current_rms(results_nominal_load):
    """Com carga nominal, corrente RMS ≈ 422,7 A (campo 15 do datasheet)."""
    mask = ss_mask(results_nominal_load.t, _T_SS_NOM)
    ia_rms = rms(results_nominal_load.currents["a"][mask])
    # Tolerância: ±5 % (modelo não inclui stray losses nem rc)
    assert_allclose(ia_rms, _IN, rtol=0.05,
                    err_msg=f"Corrente nominal RMS fora da faixa: {ia_rms:.2f} A")


def test_nominal_load_torque(results_nominal_load):
    """Com carga nominal, conjugado eletromagnético ≈ 13 192 N·m (campo 30)."""
    mask = ss_mask(results_nominal_load.t, _T_SS_NOM)
    te_mean = float(np.mean(results_nominal_load.electric_torque[mask]))
    # Tolerância: ±2 % (diferença de ~1 N·m por stray losses)
    assert_allclose(te_mean, _TN_NM, rtol=0.02,
                    err_msg=f"Conjugado nominal fora da faixa: {te_mean:.2f} N·m")


def test_nominal_load_slip(results_nominal_load):
    """Escorregamento nominal ≈ 0,5 % (nₛ = 1800 rpm, nₙ = 1791 rpm → Δn = 9 rpm)."""
    mask = ss_mask(results_nominal_load.t, _T_SS_NOM)
    speed_rpm = np.mean(results_nominal_load.speed[mask]) * 60.0 / (2.0 * np.pi)
    n_sync = 2.0 * _FN * 60.0 / _N_POLES   # = 1800 rpm
    slip = (n_sync - speed_rpm) / n_sync
    # Datasheet implica s_nom = 9/1800 = 0,005; tolerância ±0,002
    assert_allclose(slip, 0.005, atol=0.002,
                    err_msg=f"Escorregamento fora da faixa: {slip:.5f}")


def test_nominal_load_current_above_no_load(results_no_load, results_nominal_load):
    """Corrente com carga nominal deve ser maior que a corrente a vazio."""
    mask_nl = ss_mask(results_no_load.t, _T_SS_NL)
    mask_nom = ss_mask(results_nominal_load.t, _T_SS_NOM)
    ia_nl = rms(results_no_load.currents["a"][mask_nl])
    ia_nom = rms(results_nominal_load.currents["a"][mask_nom])
    assert ia_nom > ia_nl, (
        f"Corrente nominal ({ia_nom:.1f} A) deveria ser > corrente a vazio ({ia_nl:.1f} A)"
    )
