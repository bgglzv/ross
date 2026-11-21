'''' ==========================================================================
                         Ajuste de Velocidade V/f

Modelo do MIT acionado por meio de um inversor (VSI) com modulação vetorial
SVPWM. Tensão sintetizada de acordo com a referência de velocidade mantendo-se
o fluxo no entreferro constante de acordo com a relação V/f

Arismar Júnior - 19/11/26
 ========================================================================='''''

import numpy as np
import matplotlib.pyplot as plt

from inverter_vf_v2 import inverter_vf   # Portadora, ciclos retidos em Ts

from motor_element import MotorElement
from fft_analysis_v2 import windowed_fft, get_window
from select_harmonics_v2 import select_harmonics
from psd_analysis import calculate_psd, psd_bands
from pathlib import Path
from datetime import datetime

inicio_simulacao = datetime.now().astimezone()

# Limpeza do console opcional: funciona tambem fora do Spyder/IPython
try:
    from IPython import get_ipython
    ipython = get_ipython()
except ImportError:
    ipython = None
if ipython is not None:
    ipython.run_line_magic('clear', '')   # Limpando Console no Spyder/IPython
plt.close('all')                          # Fechando figuras anteriores

# ===================== Parâmetros de Entrada e Constantes ====================

# ------------------------- Parâmetros do Motor -------------------------------
Pn = 1.5                  # Potência nominal                           [cv]
Nn = 1710                 # Velocidade nominal                         [rpm]
Vn = 127*np.sqrt(3)       # Tensão nominal                             [V]
fn = 60                   # Frequência nominal                         [Hz]
NP = 4                    # Número de pólos 
Tn = 6.16                 # Torque nominal                             [N.m]
Jm = 0.0372               # Momento de inércia                         [kg.m2] 

TL_fator = 1              # Fator para o torque de carga desejado                 

# Parâmetros do circuito equivalente
Rs = 2.5                  # Resistência do estator                     [Ohm]
Rr = 1.8                  # Resistência do rotor (referida)            [Ohm]
Xls = 1.3                 # Reatância de dispersão do estator          [Ohm]
Xlr = 1.3                 # Reatância de dispersão do rotor (referida) [Ohm]
Xm = 43.08                # Reatância de magnetização                  [Ohm]

# ------------------------ Parâmetros do Conversor ----------------------------
Vcc = 1.35*Vn             # Tensão do barramento CC                    [V]
fs = 5000                 # Frequência de chaveamento dos IGBTs        [Hz]

# ------------------------ Parâmetros da Simulação ----------------------------
Ns = 200                  # Passos por período PWM (Com Ns = 200, deltat = 1us)
salvar = False            # True: salvar todos os resultados; False: não salvar
deltat = 1 / (fs*Ns)      # Para Ns = 100, deltat = 2e-6 s             [s]

t_total = 5               # Tempo total da simulação                   [s]
t_carga = 1               # Tempo de entrada da carga                  [s]
t_regime = 3              # Conferir inicio do regime nas respostas    [s]

# --------------------- Parâmetros da Análise Espectral -----------------------
Nciclos = 20              # Quantidade minima de ciclos para a FFT
df_desejada = 1           # Resolucao desejada da FFT                  [Hz]
tipo_janela = 'blackman'  # 'rectangular', 'hann', 'hamming' ou 'blackman'
zpadding = 8              # Fator de zero-padding
Fs = 1/deltat             # Frequência de amostragem                   [Hz]

thrs = 0.1                # Limiar para seleção dos harmônicos         [%]
f_max = 1000              # Máxima frequência de interesse             [Hz]
largura_faixas = 50       # Largura das faixas para integração da PSD  [Hz]

# ------------------------- Parâmetros Constantes -----------------------------
t = np.arange(0, t_total, deltat)  # Vetor de tempo
Nt = len(t)

# ========================= Trajetória de Velocidade ==========================
N_ref = 1800                      # Velocidade desejada                [rpm]
tramp = 0.6667                    # Tempo da rampa de aceleração       [s]

fref = N_ref*NP/120               # Frequência de referência           [Hz]

# ========================== Instanciando Objetos =============================
# Motor
motor = MotorElement(n=0,
                     Pnom=Pn*735.499,        # Conversão cv -> W
                     Vnom=Vn,
                     RPMnom=Nn,
                     fnom=fn,
                     npol=NP,
                     Rs=Rs,
                     Rr=Rr,
                     Xls=Xls,
                     Xlr=Xlr,
                     Xm=Xm,
                     Jm=Jm,
                     Bm=0.0,
                     Jl=0.0,
                     Vnet=Vn )

# Inversor
inv = inverter_vf(Vcc=Vcc,
                  fs=fs,
                  deltat=deltat,
                  Vn=Vn,
                  fn=fn,
                  tramp=tramp)

# ============================ Laço Principal =================================
van, vbn, vcn = [], [], []
ia_vec, ib_vec, ic_vec = [], [], []
wr_vec, rpm_vec, Te_vec, N_ref_vec = [], [], [], []
M_vec = []

for i in range(Nt):

    # Verifica se i é múltiplo de 100000 para mostrar o progresso da simulação
    if i % 100000 == 0:   
        print(f'{100*i/Nt:.1f}%')

    # Tempo corrente [s]
    tt = t[i]       

    # ------------------------- Torque de Carga -------------------------------
    # Partida a vazio, sendo a carga inserida em t_carga [s]
    if tt < t_carga:
        TL = 0.0
    else:
        TL = TL_fator*Tn

    # ----------------- Acionamento pelo Inversor SVPWM -----------------------
    # Tensões sintetizadas
    va, vb, vc, freq = inv.calc(fref, tt)

    # ------------------- Motor de Indução Trifásico --------------------------
    resultado = motor.calc(deltat,
                           tt,
                           va,
                           vb,
                           vc,
                           TL,
                           2*np.pi*freq) # O modelo recebe frequência em [rad/s]

    # -------------- Armazenamento das Variáveis da Simulação -----------------
    van.append(va)                    # Tensão da fase A               [V]
    vbn.append(vb)                    # Tensão da fase B               [V]
    vcn.append(vc)                    # Tensão da fase C               [V]

    ia_vec.append(resultado['Ias'])   # Corrente da fase A             [A]
    ib_vec.append(resultado['Ibs'])   # Corrente da fase B             [A]
    ic_vec.append(resultado['Ics'])   # Corrente da fase C             [A]

    wr_vec.append(resultado['wr'])    # Velocidade desenvolvida        [rad/s]
    rpm_vec.append(resultado['RPM'])  # Velocidade desenvolvida        [rpm]

    Te_vec.append(resultado['TE'])    # Torque eletromagnético         [N.m]

    N_ref_vec.append((120 * freq) / NP)   # Velocidade de referência [rpm]
    
    M_vec.append(inv.dados_svpwm['M'])    # Índice de modulação

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

N_ref_vec = np.array(N_ref_vec)

# ======================= Cálculo das Tensões de Linha ========================
Vab = van - vbn
Vbc = vbn - vcn
Vca = vcn - van

# ==================== Análise no Domínio da Frequência =======================
# Frequencia eletrica aplicada pelo inversor ao final da simulacao [Hz]
# Valido para referencia constante e rampa concluida.
f_est = abs(float(freq))
if not np.isfinite(f_est) or f_est <= 0:
    raise ValueError('A frequência elétrica final deve ser finita e positiva.')

# Duracao que atende ao numero de ciclos e a resolucao desejada
duracao_fft = max(Nciclos/f_est, 1/df_desejada)
N_janela = int(np.ceil(duracao_fft*Fs))
nf = len(t)                      # Limite exclusivo: inclui a ultima amostra
if not np.isfinite(t_regime) or not 0 <= t_regime < t_total:
    raise ValueError('Use 0 <= t_regime < t_total.')
n_regime = np.searchsorted(t, t_regime)
if N_janela > nf - n_regime:
    raise ValueError(
        f'Janela FFT exige {N_janela/Fs:.6f} s, mas há '
        f'{(nf-n_regime)/Fs:.6f} s após t_regime. Aumente t_total.'
    )
ni = nf-N_janela

# Mesmo intervalo para todos os sinais:
Va_est = van[ni:nf]
Vab_est = Vab[ni:nf]
ia_est = ia_vec[ni:nf]
T_est = Te_vec[ni:nf]

print(f'Janela FFT: {N_janela} amostras; {N_janela/Fs:.6f} s; '
      f'df = {Fs/N_janela:.6f} Hz; fe estimada = {f_est:.6f} Hz')

# Espectro da tensão de fase
freq_Va, Va_fft = windowed_fft(Va_est, Fs, padding=zpadding, window=tipo_janela)
Va_mag = np.abs(Va_fft)

# Espectro da tensão de linha
freq_Vab, Vab_fft = windowed_fft(Vab_est, Fs, padding=zpadding, window=tipo_janela)
Vab_mag = np.abs(Vab_fft)

# Espectro da corrente
freq_ia, ia_fft = windowed_fft(ia_est, Fs, padding=zpadding, window=tipo_janela)
ia_mag = np.abs(ia_fft)

# Espectro do Torque
freq_T, T_fft = windowed_fft(T_est, Fs, padding=zpadding, window=tipo_janela)
T_mag = np.abs(T_fft)

# ---------- Seleção das Componentes Espectrais e Cálculo da PSD --------------
resultados_txt = [
    f'Início da simulação: {inicio_simulacao.isoformat()}',
    f'Referência: {N_ref:g} rpm; fref = {fref:g} Hz',
    f'Janela FFT: {N_janela} amostras; {N_janela/Fs:.9f} s; df sem padding = {Fs/N_janela:.9f} Hz',
    f'Fs = {Fs:g} Hz; janela = {tipo_janela}; padding = {zpadding}; limiar = {thrs:g}%; f_max = {f_max:g} Hz',
    'Percentuais: maior pico CA para tensão/corrente; CC para torque.',
    f'PSD AC: {tipo_janela}; normalização de potência; média separada.',
    f'Faixas de {largura_faixas:g} Hz: [fi, ff), última inclui ff; bins atribuídos pelo centro.',
    'RMS por faixa usa todos os bins, independentemente do limiar dos picos.'
]
psds = {}

# Sinais para análise espectral
sinais = [
    ('Va',  Va_est,  freq_Va,  Va_mag,  'voltage'),
    ('Vab', Vab_est, freq_Vab, Vab_mag, 'voltage'),
    ('Ia',  ia_est,  freq_ia,  ia_mag,  'current'),
    ('Te',  T_est,   freq_T,   T_mag,   'torque')
]

for nome, sinal_est, freq, mag, signal_type in sinais:

    # Remoção da fundamental apenas para tensão e corrente
    remover = signal_type != 'torque'

    f_h, mag_h = select_harmonics(
        freq, mag, thrs, f_max, signal_type,
        remove_fundamental=remover,
        signal=sinal_est if remover else None,
        Fs=Fs if remover else None,
        padding=zpadding,
        window=tipo_janela
    )

    # Mesma referência utilizada por select_harmonics
    referencia = mag[0] if signal_type == 'torque' else np.max(mag[freq > 0])
    cabecalho = f'\n{nome}: componentes > {thrs:g}% da referência, até {f_max:g} Hz'
    print(cabecalho)
    resultados_txt.append(cabecalho)
    linha = f'Referência = {referencia:.9f}; percentual = 100*magnitude/referência'
    print(linha)
    resultados_txt.append(linha)
    linha = f'{"Frequência [Hz]":>18} {"Magnitude":>18} {"Referência [%]":>18}'
    print(linha)
    resultados_txt.append(linha)

    for frequency, magnitude in zip(f_h, mag_h):
        percentual = 100*magnitude/referencia if referencia > 0 else np.nan
        linha = f'{frequency:18.6f} {magnitude:18.6f} {percentual:18.6f}'
        print(linha)
        resultados_txt.append(linha)

    # Cálculo da densidade espectral
    if nome in ('Vab', 'Ia', 'Te'):
        unidade = {'Vab': 'V', 'Ia': 'A', 'Te': 'N.m'}[nome]
        # A FFT preserva a média em mag[0], substituindo o coeficiente CA
        # em zero. Recupera esse coeficiente por soma, sem refazer a FFT
        janela_fft = get_window(N_janela, tipo_janela)
        dc_ac = abs(np.sum((sinal_est-np.mean(sinal_est))*janela_fft))/np.sum(janela_fft)
        psd = calculate_psd(freq, mag, N_janela, dc_ac=dc_ac, window=tipo_janela)
        bordas, quadratico, rms = psd_bands(freq, psd, largura_faixas, f_max)
        psds[nome] = (freq, psd, bordas, quadratico, rms)

        linha = f'\n{nome}: RMS AC por faixa calculado pela PSD; média separada = {np.mean(sinal_est):.9f} {unidade}'
        print(linha)
        resultados_txt.append(linha)
        linha = f'{"fi [Hz]":>12} {"ff [Hz]":>12} {"Integral [unid²]":>22} {"RMS ["+unidade+"]":>22}'
        print(linha)
        resultados_txt.append(linha)
        for fi, ff, ms, valor_rms in zip(bordas[:-1], bordas[1:], quadratico, rms):
            linha = f'{fi:12.3f} {ff:12.3f} {ms:22.9e} {valor_rms:22.9e}'
            print(linha)
            resultados_txt.append(linha)

psd_Vab = psds['Vab'][1]
psd_ia = psds['Ia'][1]
psd_T = psds['Te'][1]

# ============================ Gráficos para Análise ==========================

# Velocidade
plt.figure(figsize=(10,5))
plt.plot(t, rpm_vec, label='Velocidade do Motor')
plt.plot(t, N_ref_vec, '--', label='Velocidade de Referência')
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

# PSD da tensão de linha Vab
plt.figure(figsize=(10, 5))
plt.plot(freq_Vab, psd_Vab)
plt.xlabel('Frequência [Hz]')
plt.ylabel('PSD de $V_{ab}$ [V²/Hz]')
plt.xlim([0, f_max])
plt.grid()

# PSD da corrente Ia
plt.figure(figsize=(10, 5))
plt.plot(freq_ia, psd_ia)
plt.xlabel('Frequência [Hz]')
plt.ylabel('PSD de $I_a$ [A²/Hz]')
plt.xlim([0, f_max])
plt.grid()

# PSD da ondulação do torque
plt.figure(figsize=(10, 5))
plt.plot(freq_T, psd_T)
plt.xlabel('Frequência [Hz]')
plt.ylabel('PSD de $T_e$ [(N.m)²/Hz]')
plt.xlim([0, f_max])
plt.grid()

plt.tight_layout()
# Índice de modulação solicitado: M = sqrt(3)*|v_ref|/Vcc
plt.figure(figsize=(10,5))
plt.plot(t, M_vec, label='$M$')
plt.xlabel('Tempo [s]')
plt.ylabel('Índice de modulação M')
plt.grid()
plt.legend()

# Mantém referências para salvar mesmo se plt.show() fechar as janelas
figuras_salvar = [plt.figure(numero) for numero in plt.get_fignums()]
plt.show()

# ======================== Salvando os Resultados =============================
if salvar:

    carga_percentual = 100.0 * TL / Tn
    identificacao = inicio_simulacao.strftime('%Y%m%d_%H%M%S_%f')
    pasta_resultados = Path(f'resultados_Vf_Ns{Ns}_{identificacao}')
    pasta_resultados.mkdir()

    # --------------------- Informações da Simulação --------------------------

    resultados_txt.extend([
        '',
        '==================== Parâmetros da Simulação ====================',
        f'Potência nominal = {Pn:.6f} cv',
        f'Velocidade nominal = {Nn:.6f} rpm',
        f'Tensão nominal = {Vn:.6f} V',
        f'Frequência nominal = {fn:.6f} Hz',
        f'Torque nominal informado = {Tn:.9f} N.m',
        f'Momento de inércia = {Jm:.9f} kg.m²',
        f'Tensão do barramento CC = {Vcc:.6f} V',
        f'Frequência de chaveamento = {fs:.6f} Hz',
        f'Passo de integração = {deltat:.9e} s',
        f'Tempo total da simulação = {t_total:.6f} s',
        f'Tempo de entrada da carga = {t_carga:.6f} s',
        f'Torque de carga final = {TL:.9f} N.m',
        f'Carga final = {carga_percentual:.6f}% Tn',
        '',
        '===================== Análise Espectral =========================',
        f'Frequência elétrica final = {f_est:.6f} Hz',
        f'Intervalo analisado = [{t[ni]:.6f}, {t[nf-1]:.6f}] s',
        f'Duração da janela = {N_janela/Fs:.9f} s',
        f'Número de amostras = {N_janela}',
        f'Resolução sem padding = {Fs/N_janela:.9f} Hz',
        f'Espaçamento após padding = {Fs/(N_janela*zpadding):.9f} Hz',
        f'Janela utilizada = {tipo_janela}',
        f'Limiar de seleção = {thrs:.6f}%',
        f'Frequência máxima = {f_max:.6f} Hz',
        'Remoção automática da fundamental: tensão e corrente.',
        'Torque: referência CC, sem remoção da fundamental.',
        '',
        f'Pasta dos resultados: {pasta_resultados}'
    ])

    # Salvamento do relatório
    (pasta_resultados/'resultados.txt').write_text(
        '\n'.join(resultados_txt)+'\n',
        encoding='utf-8'
    )

    # ------------------------- Salvamento das Figuras ------------------------

    nomes_figuras = [
        'velocidade',
        'torque',
        'correntes',
        'tensoes_linha',
        'FFT_Va',
        'FFT_Vab',
        'FFT_Ia',
        'FFT_Te',
        'PSD_Vab',
        'PSD_Ia',
        'PSD_Te',
        'indice_modulacao'
    ]

    for numero, (figura, nome) in enumerate(
        zip(figuras_salvar, nomes_figuras), start=1
    ):

        figura.tight_layout()

        figura.savefig(
            pasta_resultados/f'{numero:02d}_{nome}.png',
            dpi=200,
            bbox_inches='tight',
            facecolor='white'
        )

        figura.savefig(
            pasta_resultados/f'{numero:02d}_{nome}.pdf',
            dpi=200,
            bbox_inches='tight',
            facecolor='white'
        )

    # ------------------------ Salvamento das PSDs ----------------------------

    for nome, (freq_psd, psd, bordas, quadratico, rms) in psds.items():

        mascara = freq_psd <= f_max

        # Densidade espectral de potência
        np.savetxt(
            pasta_resultados/f'{nome}_psd.txt',
            np.column_stack((
                freq_psd[mascara],
                psd[mascara]
            )),
            header='Frequencia_Hz PSD_AC_unidade2_por_Hz',
            fmt='%.12e'
        )

        # Integral da PSD e RMS por faixa
        np.savetxt(
            pasta_resultados/f'{nome}_faixas.txt',
            np.column_stack((
                bordas[:-1],
                bordas[1:],
                quadratico,
                rms
            )),
            header='fi_Hz ff_Hz Integral_unidade2 RMS_unidade',
            fmt='%.12e'
        )

    #plt.close('all')
    print(f'\nResultados e figuras salvos em: {pasta_resultados}')
