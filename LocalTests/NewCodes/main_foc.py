import numpy as np
import matplotlib.pyplot as plt

from motor_element import MotorElement
from inverter_foc import inverter_foc
from fft_analysis import windowed_fft
from IPython import get_ipython

get_ipython().run_line_magic('clear', '') # Limpando Console
plt.close('all')                          # Fechando figuras anteriores

'''' ========================================================================== 
                               FOC Speed Control

Three-phase Induction Motor model driven by a Voltage Source Inverter (VSI)
using Space Vector Pulse Width Modulation (SVPWM). The synthesized voltages
are generated according to the indirect Field-Oriented Control (iFOC)
speed control strategy.

Arismar Júnior - 15/06/26                     
 ========================================================================='''''

# ===================== Parâmetros de Entrada e Constantes ====================
Vn = 127*np.sqrt(3)               # Tensão nominal [V]
fn = 60                           # Frequência nominal [Hz]
NP = 4                            # Número de pólos

Vcc = 1.35*Vn                     # Tensão do barramento CC [V]
fs = 5000                         # Frequência de chaveamento [Hz]

deltat = 2e-6                     # Passo da simulação [s]
t_total = 3.0                     # Tempo total da simulação [s]

# Parâmetros constantes:
t = np.arange(0, t_total, deltat) # Vetor de tempo
Nt = len(t)

# ========================== Referência de Velocidade =========================
rpm_ref = 900                    # Velocidade desejada (rpm)
wref = rpm_ref * np.pi / 30       # rad/s                        

# ========================== Instanciando Objetos =============================
# Motor
motor = MotorElement(
    n=0,
    Pnom=4.9316 * 735.499,        # Conversão HP -> W
    Vnom=127,
    RPMnom=1710,
    fnom=60,
    npol=4,
    Rs=2.5,
    Rr=1.8,
    Xls=1.3,
    Xlr=1.3,
    Xm=43.08,
    Jm=0.0372,
    Bm=0.0,
    Jl=0.0
)

# Inversor com controle FOC
inv = inverter_foc(
    Vcc=Vcc,
    fs=fs,
    deltat=deltat,
    motor=motor,
    tramp=0.6667                  # Tempo da rampa de aceleração [s]
)

# ============================ Laço Principal =================================
van = []
vbn = []
vcn = []

wr_vec = []
rpm_vec = []
Te_vec = []

ia_vec = []
ib_vec = []
ic_vec = []

rpm_ref_vec = []

wr = 0.0
ia = 0.0
ib = 0.0
ic = 0.0

for i in range(Nt):

    if i % 100000 == 0:
        print(f'{100*i/Nt:.1f}%')

    tt = t[i]       # Tempo corrente

    # ------------------------- Torque de carga -------------------------------
    # Partida a vazio, sendo a carga inserida em 1 segundo
    if tt < 1.0:
        TL = 0.0
    else:
        TL = 6.16

    # ---- Acionamento pelo inversor SVPWM com controle de Velocidade iFOC ----
    # Tensões sintetizadas
    resultado_inv = inv.calc(
        wref,
        tt,
        wr,
        ia,
        ib,
        ic,
        deltat
        )

    va = resultado_inv['va']
    vb = resultado_inv['vb']
    vc = resultado_inv['vc']
    
    weixo = resultado_inv['weixo']

    # ------------------- Motor de Indução Trifásico --------------------------
    resultado = motor.calc(
        deltat,
        tt,
        va,
        vb,
        vc,
        TL,
        weixo
        )
    
    wr = resultado['wr']

    ia = resultado['Ias']
    ib = resultado['Ibs']
    ic = resultado['Ics']

    # -------------- Armazenamento das variáveis da simulação -----------------
    van.append(va)                    # Tensão da fase A [V]
    vbn.append(vb)                    # Tensão da fase B [V]
    vcn.append(vc)                    # Tensão da fase C [V]

    ia_vec.append(resultado['Ias'])   # Corrente da fase A [A]
    ib_vec.append(resultado['Ibs'])   # Corrente da fase B [A]
    ic_vec.append(resultado['Ics'])   # Corrente da fase C [A]

    wr_vec.append(resultado['wr'])    # Velocidade desenvolvida em [rad/s]
    rpm_vec.append(resultado['RPM'])  # Velocidade desenvolvida em [rpm]

    Te_vec.append(resultado['TE'])    # Torque eletromagnético [N.m]

    rpm_ref_vec.append(inv.wref_ramp * 30 / np.pi) # Velocidade de referência [rpm]

# =================== Conversão para Arrays do Numpy ==========================
van = np.array(van)
vbn = np.array(vbn)
vcn = np.array(vcn)

wr_vec = np.array(wr_vec)
rpm_vec = np.array(rpm_vec)
Te_vec = np.array(Te_vec)

ia_vec = np.array(ia_vec)
ib_vec = np.array(ib_vec)
ic_vec = np.array(ic_vec)

rpm_ref_vec = np.array(rpm_ref_vec)

# ======================= Cálculo das Tensões de Linha ========================
Vab = van - vbn
Vbc = vbn - vcn
Vca = vcn - van

# ==================== Análise no Domínio da Frequência =======================
Fs = 1 / deltat

ni = round(1.8*(Nt//2))   # Amostra inicial (80% finais)
#ni = round(Nt // 2)      # Amostra inicial (metade)
nf = round(Nt - 1)        # Amostra final

# Delimitando sinais entre ni e nf
Va_est = van[ni:nf]
Vab_est = Vab[ni:nf]
ia_est = ia_vec[ni:nf]
T_est = Te_vec[ni:nf]

# Espectro da tensão de fase
freq_Va, Va_mag = windowed_fft(Va_est, Fs)

# Espectro da tensão de linha
freq_Vab, Vab_mag = windowed_fft(Vab_est, Fs)

# Espectro da corrente
freq_ia, ia_mag = windowed_fft(ia_est, Fs)

# Espectro do Torque
freq_T, T_mag = windowed_fft(T_est, Fs)

# ============================ Gráficos para Análise ========================== 

# Velocidade
plt.figure(figsize=(10,5))
plt.plot(t, rpm_vec, label='Velocidade do Motor')
plt.plot(t, rpm_ref_vec, '--', label='Velocidade de Referência')

# plt.title('Velocidade do Motor vs Referência')
plt.xlabel('Tempo [s]')
plt.ylabel('N [rpm]')
plt.grid()
plt.legend()

# Torque
plt.figure(figsize=(10,5))
plt.plot(t, Te_vec)

# plt.title('Torque Eletromagnético')
plt.xlabel('Tempo [s]')
plt.ylabel('$T_e$ [N.m]')
plt.grid()

# Correntes
plt.figure(figsize=(10,5))
plt.plot(t, ia_vec, label='$I_a$')
plt.plot(t, ib_vec, label='$I_b$')
plt.plot(t, ic_vec, label='$I_c$')

# plt.title('Correntes do Estator')
plt.xlabel('Tempo [s]')
plt.ylabel('$I_{Fase}$ [A]')
plt.legend()
plt.grid()

# Tensões de linha
plt.figure(figsize=(10,5))
plt.plot(t, Vab, label='$V_{ab}$')
plt.plot(t, Vbc, label='$V_{bc}$')
plt.plot(t, Vca, label='$V_{ca}$')

# plt.title('Tensões de Linha')
plt.xlabel('Tempo [s]')
plt.ylabel('$V_{Linha}$ [V]')
plt.legend()
plt.grid()

# FFT da tensão Va
plt.figure(figsize=(10,5))
plt.plot(freq_Va, Va_mag)

# plt.title('FFT - Tensão de Fase')
plt.xlabel('Frequência [Hz]')
plt.ylabel('$V_a$ [V]')
plt.xlim([-10, Fs/2])
plt.grid()

# FFT da tensão Vab
plt.figure(figsize=(10,5))
plt.plot(freq_Vab, Vab_mag)

# plt.title('FFT - Tensão de Linha')
plt.xlabel('Frequência [Hz]')
plt.ylabel('$V_{ab}$ [V]')
plt.xlim([-10, Fs/2])
plt.grid()

# FFT da corrente Ia
plt.figure(figsize=(10,5))
plt.plot(freq_ia, ia_mag)

# plt.title('FFT - Corrente')
plt.xlabel('Frequência [Hz]')
plt.ylabel('$I_a$ [A]')
plt.xlim([-10, Fs/2])
plt.grid()

# FFT do torque
plt.figure(figsize=(10,5))
plt.plot(freq_T, T_mag)

# plt.title('FFT - Torque')
plt.xlabel('Frequência [Hz]')
plt.ylabel('$T_e$ [N.m]')
plt.xlim([-10, Fs/2])
plt.grid()

plt.tight_layout()
plt.show()