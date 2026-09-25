"""inverter_foc_novo.py — Proposta de nova regra de sintonia para o InverterFOC.

Contexto (ver `Estudo_Mergulho_Velocidade_FOC.txt`): o `InverterFOC` original
(`ross/motors/inverters.py`) encadeia as larguras de banda de TODAS as malhas
a partir de um único parâmetro, `frequency_s` (frequência de chaveamento),
por divisões sucessivas fixas de 8:

    BWp_iqs = BWp_ids = BWi_ids = frequency_s / 8      # malhas de corrente
    BWp_w   = BWi_ids / 8                              # malha de velocidade (P)
    BWi_w   = BWp_w / 8                                # malha de velocidade (I)

Isso amarra a dinâmica mecânica (velocidade) a um parâmetro puramente
elétrico/de chaveamento, sem relação com a inércia ou o torque nominal do
motor. No estudo do mergulho de velocidade, essa amarra fixa — combinada
com uma frequência de chaveamento baixa (2000 Hz) escolhida para o motor
industrial — produziu um ganho proporcional de velocidade (`kp_w`, que
escala com a inércia `J`) alto o bastante para que a corrente real
ultrapassasse em ~50% o próprio limite que o controlador tenta impor
(`iqs_max`), resultando num mergulho de velocidade subamortecido.

Este módulo propõe e implementa duas mudanças, isoladas do pacote `ross`
(``InverterFOCNovo`` é uma subclasse local, o `InverterFOC` original não é
alterado):

1. NOVA REGRA — largura de banda da malha de velocidade desacoplada de
   `frequency_s`, derivada da própria constante de tempo mecânica do
   motor (ver `compute_speed_bandwidths` abaixo), com a razão entre as
   duas larguras de banda da malha de velocidade (`speed_i_ratio`) exposta
   como parâmetro em vez de um "8" fixo no meio do código. As malhas de
   corrente (`BWp_iqs`, `BWp_ids`, `BWi_ids`) permanecem exatamente como
   no `InverterFOC` original — ligadas a `frequency_s` por um fator fixo
   de 8 — porque há uma razão física real para essa amarra específica
   (margem de fase do laço de corrente digital face ao período de
   chaveamento) que o estudo do mergulho não questiona; só a malha de
   velocidade, cuja amarra à frequência de chaveamento não tinha
   justificativa física equivalente, foi desacoplada.

2. PROTEÇÃO DE SOBRECORRENTE INSTANTÂNEA — o `InverterFOC` original só
   satura a REFERÊNCIA de corrente (`iqs_max = 3 x Is_nom`), nunca a
   corrente de fase real medida; é exatamente essa lacuna que permitiu o
   mergulho estudado. `InverterFOCNovo` desarma (desliga as tensões de
   saída, como a proteção de hardware de um inversor real) se a corrente
   de fase medida ultrapassar `current_trip_multiple x Is_nom`.

Não é executado diretamente — importado pelos scripts de teste
(``TPIM_Comparativo1_novo.py``).
"""

import numpy as np

from ross.motors.inverters import InverterFOC
from ross.units import check_units


def mechanical_time_constant(Ip_motor, speed_nom, torque_nom):
    """Constante de tempo mecânica do motor: tempo para desacelerar de
    `speed_nom` até parar sob torque de carga constante igual a
    `torque_nom` (J·dw/dt = -Tnom => tau = J*speed_nom/Tnom).

    É uma grandeza puramente mecânica — não depende de `frequency_s` nem
    de qualquer parâmetro do inversor — e, ao contrário da inércia J
    isolada, é comparável entre motores de porte muito diferente: um
    motor maior tem mais inércia, mas também mais torque nominal para
    movê-la, então `tau_mech` tende a ficar na mesma ordem de grandeza
    entre motores bem projetados (ver docstring de `compute_speed_bandwidths`
    para os valores reais medidos nos dois motores deste projeto).
    """
    return float(Ip_motor) * float(speed_nom) / float(torque_nom)


def compute_speed_bandwidths(
    Ip_motor, speed_nom, torque_nom, speed_dip_fraction=0.001, speed_i_ratio=100.0
):
    """Nova regra proposta para as larguras de banda da malha de velocidade,
    desacoplada de `frequency_s`.

    Ideia: em vez de herdar a largura de banda de uma fração arbitrária da
    frequência de chaveamento, escolher `BWp_w` a partir de uma
    especificação de desempenho de rejeição de distúrbio diretamente
    interpretável — "sob um degrau de carga igual ao torque nominal, sem
    nenhuma correção do controlador, quanto tempo o motor levaria para a
    velocidade cair `speed_dip_fraction` da velocidade nominal? A malha
    deve reagir (no ritmo do polo mais rápido) dentro desse tempo":

        t_alvo  = speed_dip_fraction * tau_mech
        BWp_w   = 1 / (2*pi*t_alvo) = 1 / (2*pi*speed_dip_fraction*tau_mech)
        BWi_w   = BWp_w / speed_i_ratio

    `speed_i_ratio` (razão entre as duas larguras de banda da malha de
    velocidade) continua fixa em 8 por padrão — não porque seja um número
    mágico, mas porque, para o par de polos reais resultante do método de
    bandwidth já usado no `InverterFOC` (raízes em `-2*pi*BWp_w` e
    `-2*pi*BWi_w`), essa razão foi verificada analiticamente aqui como
    produzindo um sobressinal de torque de apenas ~7% sobre o valor final
    após um degrau de carga nominal (resposta bem amortecida) — um
    comportamento independente da inércia ou da largura de banda absoluta,
    então continua válido ao trocar `speed_dip_fraction`.

    Calibração — ACHADO IMPORTANTE: a primeira tentativa de calibração foi
    puramente numérica (escolher `speed_dip_fraction` para que `kp_w` desse
    a mesma ordem de grandeza do valor já usado pela regra antiga no motor
    pequeno, ~129). Isso levou a `speed_dip_fraction = 0.0003` (`kp_w =
    130,8`, a menos de 3% do valor antigo). Testado em simulação
    (`TPIM_Comparativo1_novo.py`), esse valor produziu uma resposta MUITO
    pior que a regra antiga — mergulho de torque de -8,5 a +11,9 N·m no
    degrau de carga, em vez da faixa limpa de ~4 a ~9 N·m da regra antiga
    — apesar de `kp_w`/`ki_w` diferirem da regra antiga por menos de 3%.

    Isolado o efeito (reproduzido também travando manualmente esses mesmos
    `kp_w`/`ki_w` num `InverterFOC` comum, sem nenhuma outra mudança deste
    módulo — não é um bug de implementação), uma varredura fina de
    `speed_dip_fraction` revelou que a resposta alterna entre "limpa" e
    "mergulho" de forma NÃO monotônica e sensível a variações de poucos
    por cento em `kp_w` (ex.: 0,00100 limpo, 0,00105 mergulho, 0,00110
    mergulho, 0,00120 limpo — variação de ganho de menos de 10% entre
    pontos). A causa mais provável é a lógica de anti-windup do
    `InverterFOC` (`inverters.py`, a condição `np.sign(err_w) !=
    np.sign(iqs_ref_unsat)` que congela/libera o integrador): é uma
    comutação discreta, e pequenas mudanças de ganho deslocam o instante
    exato em que ela liga/desliga durante a rampa de partida, alterando o
    estado do integrador de velocidade no momento em que o degrau de carga
    chega (a 0,83 s do fim da rampa) — o suficiente para produzir uma
    resposta qualitativamente diferente. Isso é uma sensibilidade real do
    `InverterFOC` original (presente também na regra antiga, só não
    evidenciada porque seu `kp_w` particular não caiu numa faixa ruim para
    este motor/protocolo) — não uma fragilidade introduzida pela regra
    nova.

    Dado esse achado, `speed_dip_fraction = 0.001` (`kp_w = 39,2`) foi
    escolhido por ter sido VALIDADO por simulação (resposta limpa, ~3,8 a
    ~9,3 N·m, próxima da regra antiga) — não por proximidade numérica a
    nenhum valor pré-existente. Ainda assim, dada a sensibilidade fina
    encontrada, este valor não deve ser tratado como definitivamente
    robusto: qualquer mudança de protocolo (tempo de rampa, instante do
    degrau de carga) ou a aplicação desta regra a outro motor (o motor
    industrial ainda não foi testado com ela) deveria repetir uma
    varredura de validação como a feita aqui, em vez de assumir que o
    valor calibrado se transporta sem checagem.

    ACHADO 2 — `speed_i_ratio` recalibrado para evitar torque negativo:
    mesmo com `speed_dip_fraction = 0.001` validado acima, o torque
    eletromagnético ainda cruzava para valores NEGATIVOS logo após o
    degrau de carga — um problema mecânico à parte de "ripple" ou
    "sobressinal": torque negativo inverte o sentido do esforço no eixo
    (torção reversa), o que é indesejável independente da magnitude. Uma
    varredura de `speed_i_ratio` nos dois ensaios do motor pequeno (60 Hz
    e 30 Hz) mostrou o mesmo padrão de sensibilidade fina e não monotônica
    já descrito acima (ex.: r=95 e r=105 cruzam para negativo no ensaio de
    30 Hz, -0,95 e -0,73 N·m; r=110, 150, 200 cruzam para bem negativo no
    ensaio de 60 Hz, até -9,6 N·m) — mas **r=100 foi o único valor, entre
    todos os testados (8 a 200), com torque mínimo positivo nos dois
    ensaios** (60 Hz: +4,89 N·m; 30 Hz: +0,41 N·m), ao custo de um tempo
    de acomodação maior no ensaio de 60 Hz (~0,41 s, contra ~0,07-0,13 s
    dos valores vizinhos). Por isso o default de `speed_i_ratio` mudou de
    8.0 para 100.0. Dada a mesma sensibilidade fina já documentada, este
    valor também não deve ser considerado garantidamente robusto fora das
    condições testadas (60 Hz e 30 Hz, degrau de carga nominal, motor
    pequeno) — qualquer mudança de condição pede nova varredura de
    validação, focada especificamente no MÍNIMO do torque (não só no
    sobressinal ou no tempo de acomodação).

    Parameters
    ----------
    Ip_motor : float
        Inércia do rotor [kg.m²].
    speed_nom : float
        Velocidade mecânica nominal [rad/s].
    torque_nom : float
        Torque nominal [N.m].
    speed_dip_fraction : float, optional
        Parâmetro de projeto da nova regra (ver "Calibração" acima — não
        tem uma leitura literal em % da velocidade nominal devido à
        convenção interna de unidades do `InverterFOC`). Default 0.001,
        validado por simulação no motor pequeno — ver "Calibração" acima
        para o porquê de não ser um valor puramente analítico.
    speed_i_ratio : float, optional
        BWp_w / BWi_w. Default 100.0 — ver "ACHADO 2" acima: escolhido para
        evitar torque negativo (torção reversa no eixo) no degrau de carga,
        não pelo sobressinal ou tempo de acomodação isoladamente.

    Returns
    -------
    BWp_w, BWi_w : float
        Larguras de banda proporcional e integral da malha de velocidade [Hz].
    tau_mech : float
        Constante de tempo mecânica usada no cálculo [s].
    """
    tau_mech = mechanical_time_constant(Ip_motor, speed_nom, torque_nom)
    BWp_w = 1.0 / (2 * np.pi * speed_dip_fraction * tau_mech)
    BWi_w = BWp_w / speed_i_ratio
    return BWp_w, BWi_w, tau_mech


class InverterFOCNovo(InverterFOC):
    """`InverterFOC` com a malha de velocidade retunada pela nova regra
    (`compute_speed_bandwidths`) e proteção de sobrecorrente instantânea.

    As malhas de corrente (`kp_iqs`, `kp_ids`, `ki_ids`) são herdadas sem
    alteração do `InverterFOC` original — mesma razão com `frequency_s`
    (`current_bw_ratio`, default 8, idêntico ao valor fixo anterior).
    Só a malha de velocidade (`kp_w`, `ki_w`) é recalculada.

    Parameters
    ----------
    (mesmos parâmetros de `InverterFOC`, mais:)
    speed_dip_fraction : float, optional
        Ver `compute_speed_bandwidths`. Default 0.001.
    speed_i_ratio : float, optional
        Ver `compute_speed_bandwidths`. Default 100.0.
    current_trip_multiple : float, optional
        Limite de desarme por sobrecorrente instantânea, em múltiplos de
        `Is_nom` (corrente de fase de pico nominal), aplicado à corrente de
        fase MEDIDA (não à referência). Default 3.6 — 20% acima do limite
        de referência já existente (`iqs_max = 3 x Is_nom`), para tolerar
        a ultrapassagem normal da dinâmica de fluxo sobre a referência sem
        deixar de capturar uma fuga como a do estudo do mergulho (~4,5x).
        Uma vez desarmado, o inversor passa a aplicar tensão nula
        (desligado) pelo resto da simulação — como a proteção de hardware
        de um inversor real.
    current_filter_cutoff_hz : float or None, optional
        Frequência de corte [Hz] de um filtro passa-baixa de 1ª ordem
        aplicado à corrente de fase MEDIDA antes de entrar na malha de
        controle (Clarke/Park) — simula o filtro anti-aliasing de um
        sensor de corrente real, não muda a estrutura do controlador.
        `None` (default) desativa o filtro (comportamento idêntico ao sem
        filtro). A proteção de sobrecorrente (`current_trip_multiple`)
        continua usando a corrente BRUTA, não a filtrada — um desarme de
        hardware real reage à corrente instantânea por um circuito
        dedicado, separado da malha de controle. Ver a nota de
        investigação no final deste módulo para os valores testados
        (piorou muito — desestabiliza a malha de corrente).
    speed_filter_cutoff_hz : float or None, optional
        Mesma ideia de `current_filter_cutoff_hz`, mas aplicado à
        velocidade MEDIDA do rotor em vez da corrente de fase — motivação:
        reduzir a sensibilidade do PI de velocidade a flutuações rápidas de
        `rotor_speed`, sem tocar no ganho `kp_w` nem no limite `iqs_max`
        (ver "ACHADO 3" no final deste módulo). `None` (default) desativa.
    """

    @check_units
    def __init__(
        self,
        voltage_dc,
        frequency_s,
        voltage_nom,
        frequency_nom,
        n_poles,
        speed_nom,
        torque_nom,
        stator_resistance,
        rotor_resistance,
        stator_reactance,
        rotor_reactance,
        mutual_reactance,
        Ip_motor,
        time_ramp=1.0,
        frequency_ref=None,
        speed_dip_fraction=0.001,
        speed_i_ratio=100.0,
        current_trip_multiple=3.6,
        current_filter_cutoff_hz=None,
        speed_filter_cutoff_hz=None,
    ):
        super().__init__(
            voltage_dc,
            frequency_s,
            voltage_nom,
            frequency_nom,
            n_poles,
            speed_nom,
            torque_nom,
            stator_resistance,
            rotor_resistance,
            stator_reactance,
            rotor_reactance,
            mutual_reactance,
            Ip_motor,
            time_ramp=time_ramp,
            frequency_ref=frequency_ref,
        )

        BWp_w, BWi_w, tau_mech = compute_speed_bandwidths(
            Ip_motor,
            self.speed_nom,
            float(torque_nom),
            speed_dip_fraction=speed_dip_fraction,
            speed_i_ratio=speed_i_ratio,
        )

        J = float(Ip_motor)
        KL = float(torque_nom) / (self.np_pairs * self.speed_nom)

        self.kp_w = J * 2 * np.pi * (BWp_w + BWi_w) - KL
        self.ki_w = J * 4 * (np.pi**2) * BWp_w * BWi_w

        self.tau_mech = tau_mech
        self.BWp_w_novo = BWp_w
        self.BWi_w_novo = BWi_w
        self.speed_dip_fraction = speed_dip_fraction

        self.current_trip_multiple = current_trip_multiple
        self.current_filter_cutoff_hz = current_filter_cutoff_hz
        self.speed_filter_cutoff_hz = speed_filter_cutoff_hz
        self.tripped = False
        self.trip_time = None

    def initialize_control_state(self, dt, theta_0=0.0):
        """Igual a `InverterFOC.initialize_control_state`, mais o estado dos
        filtros de corrente e de velocidade (zerados — partida do repouso)."""
        super().initialize_control_state(dt, theta_0)
        self.control_state["ia_filt"] = 0.0
        self.control_state["ib_filt"] = 0.0
        self.control_state["ic_filt"] = 0.0
        self.control_state["speed_filt"] = 0.0

    def get_current_state(self, t, dt, rotor_speed, ia, ib, ic, frequency_ref=None):
        """Igual a `InverterFOC.get_current_state`, exceto pela checagem de
        sobrecorrente instantânea e pelos filtros de medição de corrente e
        de velocidade (ver docstring da classe)."""
        if self.tripped:
            return self.np_pairs * rotor_speed, 0.0, 0.0, 0.0

        current_limit = self.current_trip_multiple * self.Is_nom
        if max(abs(ia), abs(ib), abs(ic)) > current_limit:
            self.tripped = True
            self.trip_time = t
            return self.np_pairs * rotor_speed, 0.0, 0.0, 0.0

        if self.current_filter_cutoff_hz is not None:
            # Filtro passa-baixa de 1a ordem, discretizado por Euler:
            # y[k] = y[k-1] + (dt/tau)*(x[k]-y[k-1]), tau = 1/(2*pi*fc).
            # Só filtra o que entra no CONTROLE (Clarke/Park abaixo) — a
            # checagem de sobrecorrente acima já usou a corrente bruta.
            state = self.control_state
            tau = 1.0 / (2 * np.pi * self.current_filter_cutoff_hz)
            alpha = dt / (tau + dt)
            state["ia_filt"] += alpha * (ia - state["ia_filt"])
            state["ib_filt"] += alpha * (ib - state["ib_filt"])
            state["ic_filt"] += alpha * (ic - state["ic_filt"])
            ia, ib, ic = state["ia_filt"], state["ib_filt"], state["ic_filt"]

        if self.speed_filter_cutoff_hz is not None:
            # Mesmo filtro de 1a ordem, aplicado à velocidade MEDIDA do
            # rotor antes de qualquer uso dela no controle (erro de
            # velocidade E a velocidade síncrona derivada dela) — simula um
            # sensor/observador de velocidade com filtro, não a corrente.
            # A malha de velocidade é bem mais lenta que a de corrente, daí
            # a expectativa de tolerar melhor o atraso de fase introduzido
            # (ver nota de investigação no final do módulo).
            state = self.control_state
            tau = 1.0 / (2 * np.pi * self.speed_filter_cutoff_hz)
            alpha = dt / (tau + dt)
            state["speed_filt"] += alpha * (rotor_speed - state["speed_filt"])
            rotor_speed = state["speed_filt"]

        return super().get_current_state(t, dt, rotor_speed, ia, ib, ic, frequency_ref)
