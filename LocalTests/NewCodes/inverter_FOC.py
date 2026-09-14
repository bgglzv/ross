""" Voltage Source Inverter Module with Indirect Field-Oriented Control

This module defines the inverter class, which represents a three-phase
Voltage Source Inverter (VSI) operating under indirect Field-Oriented
Control (iFOC). Space Vector Pulse Width Modulation (SVPWM) is employed
to synthesize the three-phase output voltages.

Based on:
    Wu, B. & Narimani, M. High-Power Converters and AC Drives, 2016.
    Novotny, D. & Lipo, T. Vector Control and Dynamics of AC Drives, 1996.
"""

import numpy as np

from transforms import abc_dq0
from transforms import dq0_abc


class inverter_foc:

    """A three-phase Voltage Source Inverter (VSI).

    This class implements a three-phase Voltage Source Inverter (VSI)
    operating under indirect Field-Oriented Control (iFOC). The output
    voltages are synthesized using Space Vector Pulse Width Modulation
    (SVPWM).
    """

    def __init__(self,
                 Vcc,
                 fs,
                 deltat,
                 motor,
                 tramp=1.0):

        # ======================== Input Parameters ===========================
        # Inverter Parameters 
        self.Vcc = Vcc            # DC Link Voltage [V]
        self.fs = fs              # Switching frequency [Hz]
        self.Ts = 1 / fs          # Switching period [s]
        self.deltat = deltat      # Simulation time step [s]

        # Speed Reference Ramp 
        self.tramp = tramp        # Acceleration ramp time [s]
        self.wref_ramp = 0.0      # Current mechanical speed reference

        # Induction Motor Model 
        self.motor = motor

        # ======================== Motor Parameters ===========================
        # Nominal Values 
        self.Vn = motor.Vnom      # Nominal line voltage [V]
        self.fn = motor.fnom      # Nominal frequency [Hz]
        self.NP = motor.npol      # Number of poles
        self.N = motor.RPMnom     # Nominal speed [rpm]
        self.Tn = motor.Tnom      # Nominal torque [N.m]

        # Electrical Parameters 
        self.Rs = motor.Rs        # Stator resistance [Ohms]
        self.Rr = motor.Rr        # Rotor resistance [Ohms]
        self.Xls = motor.Xls      # Stator leakage reactance [Ohms]
        self.Xlr = motor.Xlr      # Rotor leakage reactance [Ohms]
        self.Xm = motor.Xm        # Magnetizing reactance [Ohms]

        # Mechanical Parameters 
        self.J = motor.Jm                     # Rotor inertia [kg.m²]

        # ======================= Derived Parameters ==========================
        # Peak phase voltage
        self.Vn_fp = (self.Vn / np.sqrt(3)) * np.sqrt(2)

        # Pole pairs
        self.p = self.NP / 2

        # Electrical angular frequency
        self.we = motor.ws

        # Nominal angular speed [rad/s]
        self.wn = motor.wnom

        # ========================= iFOC Parameters ===========================
        # Inductances      
        self.Lls = motor.Lls      # Stator leakage inductance   
        self.Llr = motor.Llr      # Rotor leakage inductance 
        self.Lm = motor.Lm        # Magnetizing inductance
        self.Lss = motor.Lss      # Stator inductance
        self.Lrr = motor.Lrr      # Rotor inductance

        # Rotor time constant
        self.taur = self.Lrr / self.Rr    

        # =========== Direct-axis Reference Current Calculation ===============

        # Nominal slip
        self.sn = ((self.we - self.p*self.wn)/ self.we)

        # Modified Equivalent Circuit Rotor Resistance
        Rr_eq = (self.Rr * (self.Lm/self.Lrr)**2 ) / self.sn

        # Auxiliary variables for calculating Zeq
        Ls1 = self.Lss - (self.Lm**2/self.Lrr)
        Lm1 = (self.Lm**2)/self.Lrr

        # Equivalent impedance
        Zeq = (
                (self.Rs + 1j*self.we*Ls1)
                +
                (1j*self.we*Lm1*Rr_eq) 
                /
                (1j*self.we*Lm1 + Rr_eq)
              )

        # Phase Voltage Peak
        Vmax = self.Vn * (np.sqrt(2)/np.sqrt(3))

        # Total Stator Current
        Is = Vmax / Zeq

        # Modified Equivalent Circuit Voltage Er
        Er = (Vmax - (self.Rs + 1j*self.we*Ls1)*Is)   # ??? Is ou abs(Is) ???

        # Direct-Axis Reference Current
        self.ids_ref = abs(Er)/(self.we*Lm1)

        # =============== PIs Controller Gains Calculation ====================
        # According to the bandwidth method

        BWp_iqs = fs/8  # Bandwidth of the proportional q-axis current controller
        BWp_ids = fs/8  # Bandwidth of the proportional d-axis current controller
        BWi_ids = fs/8  # Bandwidth of the integral d-axis current controller
        BWp_w = BWi_ids/8 # Bandwidth of the proportional speed controller
        BWi_w = BWp_w/8   # Bandwidth of the integral speed controller

        # Load constant
        KL = self.Tn / ((self.NP/2)*self.wn)

        # Torque constant
        KT = (3*(self.NP/2) *(self.Lm**2) *(self.ids_ref/self.Lrr))

        # Proportional Speed Controller Gain
        self.kp_w = (self.J*2*np.pi*(BWp_w+BWi_w)-KL)

        # Integral Speed Controller Gain
        self.ki_w = (self.J*4*(np.pi**2) * BWp_w*BWi_w)

        # Proportional d-axis Current Controller Gain
        self.kp_ids = (self.Lss * 2*np.pi * (BWp_ids+BWi_ids))

        # Integral d-axis Current Controller Gain
        self.ki_ids = (self.Lss * 4*(np.pi**2) * BWp_ids*BWi_ids)

        # Proportional q-axis Current Controller Gain
        self.Lsline = ( self.Lss - (self.Lm**2)/(self.Lrr) ) # Equivalent leakage inductance
        self.kp_iqs = (2*np.pi * self.Lsline * BWp_iqs)

        # ========================== Internal States ==========================
        self.int_errow = 0.0
        self.int_erroids = 0.0
        self.teta = 0.0

        # Constant terms
        self.pi3 = np.pi / 3
        self.doispi = 2 * np.pi

        # Switching SVPWM table
        # Each column represents the states of the upper switches
        # for the space vectors V0, V1, V3, V2, V6, V4, V5 and V7
        self.sw_table = np.array([
            [0,1,1,0,0,0,1,1],
            [0,0,1,1,1,0,0,1],
            [0,0,0,0,1,1,1,1]
        ])

        # Active vectors according to the sector
        self.actv_vet = np.array([
            [2,3],
            [3,4],
            [4,5],
            [5,6],
            [6,7],
            [7,2]
        ])

        # Null vectors
        self.V0 = 1
        self.V7 = 8

        # Clarke transformation matrix
        self.C = (2/3) * np.array([
                                  [1, -0.5, -0.5],
                                  [0, np.sqrt(3)/2, -np.sqrt(3)/2]
                                  ])

        # Internal state (carrier)
        self.k = 1

        # Number of simulation samples per switching period
        self.Ns = max(1, int(round(self.Ts / self.deltat)))


    def speed_control(self, wref):

        """Mechanical speed reference with acceleration ramp."""

        # ========================= Reference saturation ======================
        if wref < 0:
            wref = 0

        if wref > self.wn:
            wref = self.wn

        # ========================= Acceleration Ramp =========================

        # Maximum speed variation per integration step
        # to reach the reference speed exactly in tramp seconds
        dw_max = self.wn * self.deltat / self.tramp

        if self.wref_ramp < wref:

            self.wref_ramp += dw_max

            if self.wref_ramp > wref:
                self.wref_ramp = wref

        elif self.wref_ramp > wref:

            self.wref_ramp -= dw_max

            if self.wref_ramp < wref:
                self.wref_ramp = wref

        # Desired mechanical speed reference
        return self.wref_ramp

    def ifoc_control(self, wref, wr, ia, ib, ic, dt):

        """ Indirect Field Oriented Control (iFOC). """

        # ======================== Speed Control Loop =========================
        
        wref = self.speed_control(wref) # Speed reference with acceleration ramp      
        erro_w = wref - wr # Speed error

        # PI controller
        u_prop = self.kp_w * erro_w
        u_int  = self.ki_w * self.int_errow

        iqs_ref_unsat = u_prop + u_int

        # q-axis current reference
        iqs_ref = iqs_ref_unsat

        # Slip Frequency Calculation 
        wsl = ((1 / self.taur) * (iqs_ref / self.ids_ref) )

        # Synchronous electrical speed
        weixo = wsl + self.p * wr

        self.teta += weixo * dt  # Angle integration

        # abc-dq Park transformation
        iqs, ids, _ = abc_dq0(ia, ib, ic, self.teta)

        # ======================== iqs Current Loop ===========================
        erro_iqs = iqs_ref - iqs

        vqs_ref = (self.kp_iqs * erro_iqs + self.Rs * iqs  +
            self.Lss * weixo * ids
        )

        # ======================== ids Current Loop ===========================
        erro_ids = self.ids_ref - ids

        # Integrator
        self.int_erroids += erro_ids * dt

        vds_ref = (
            self.kp_ids * erro_ids
            +
            self.ki_ids * self.int_erroids
            +
            self.Rs * ids
            -
            self.Lsline * weixo * iqs
        )

        # =================== Saturation & Anti-windup ========================
        Vmax = self.Vcc / np.sqrt(3)            # Maximum phase voltage       
        Vref = np.sqrt(vqs_ref**2 + vds_ref**2) # Voltage reference magnitude

        saturou = Vref > Vmax

        if Vref > Vmax:

            scale = Vmax / Vref

            vqs_ref *= scale
            vds_ref *= scale

        # Anti-windup
        if (
            (not saturou)
            or
            (np.sign(erro_w) != np.sign(iqs_ref_unsat))
        ):

            self.int_errow += erro_w * dt

        iqs_ref = (
            self.kp_w * erro_w
            +
            self.ki_w * self.int_errow
        )

       # dq-abc Park transformation
        va_ref, vb_ref, vc_ref = dq0_abc(vqs_ref, vds_ref, 0, self.teta)

        # =============== Phase-voltage synteses Through SVPWM ===============
        van, vbn, vcn = self.svpwm(va_ref, vb_ref, vc_ref)

        # Outputs
        return van, vbn, vcn, self.teta, weixo

    def svpwm(self, va_ref, vb_ref, vc_ref):

        """ Space Vector PWM Modulation """

        # Clarke transformation
        v_alpha = (
            self.C[0,0]*va_ref +
            self.C[0,1]*vb_ref +
            self.C[0,2]*vc_ref
        )

        v_beta = (
            self.C[1,0]*va_ref +
            self.C[1,1]*vb_ref +
            self.C[1,2]*vc_ref
        )

        # Vector module
        vr = np.sqrt(v_alpha**2 + v_beta**2)

        # Vector angle
        theta = np.arctan2(v_beta, v_alpha)

        if theta < 0:
            theta += self.doispi

        # Sector determination
        S = int(np.floor(theta / self.pi3)) + 1

        S = max(1, min(S, 6))

        # Angle within the sector
        thetak = theta - (S-1)*self.pi3

        # Modulation index
        M = (np.sqrt(3) * vr) / self.Vcc

        # Dwell times
        T1 = self.Ts * M * np.sin(self.pi3 - thetak)

        T2 = self.Ts * M * np.sin(thetak)

        T0 = self.Ts - T1 - T2

        eps = np.finfo(float).eps

        # Overmodulation correction
        if M > 0.907 and M <= 1:

            T0 = max(T0, 0)

            fator = self.Ts / (T1 + T2 + T0 + eps)

            T1 *= fator
            T2 *= fator

            T0 = self.Ts - T1 - T2

        elif M > 1 and M <= 1.1547:

            T0 = 0

            fator = self.Ts / (T1 + T2 + eps)

            T1 *= fator
            T2 *= fator

        elif M > 1.1547:

            if thetak <= self.pi3/2:
                T1, T2 = self.Ts, 0
            else:
                T1, T2 = 0, self.Ts

            T0 = 0

        # Normalization
        T1 = max(T1, 0)
        T2 = max(T2, 0)
        T0 = max(T0, 0)

        sumT = T1 + T2 + T0

        if abs(sumT - self.Ts) > 1e-12:

            if sumT > 0:

                T1 *= self.Ts / sumT
                T2 *= self.Ts / sumT

                T0 = self.Ts - T1 - T2

            else:

                T1, T2, T0 = 0, 0, self.Ts

        # Vector sequence
        vetor_seq = np.array([
            self.V0,
            self.actv_vet[S-1,0],
            self.actv_vet[S-1,1],
            self.V7
        ]) - 1

        t_seq = np.array([
            T0/2,
            T1,
            T2,
            T0/2
        ])

        # Switching states
        Sa_bits = self.sw_table[0, vetor_seq]
        Sb_bits = self.sw_table[1, vetor_seq]
        Sc_bits = self.sw_table[2, vetor_seq]

        # Duty cycles
        Da = np.dot(t_seq, Sa_bits) / self.Ts
        Db = np.dot(t_seq, Sb_bits) / self.Ts
        Dc = np.dot(t_seq, Sc_bits) / self.Ts

        Da = np.clip(Da, 0, 1)
        Db = np.clip(Db, 0, 1)
        Dc = np.clip(Dc, 0, 1)

        # Triangular carrier
        n_in_period = (self.k - 1) % self.Ns

        if self.Ns == 1:
            u = 0
        else:
            u = n_in_period / (self.Ns - 1)

        carrier = 1 - 4 * np.abs(u - 0.5)

        # Thresholds
        RefA = 2*Da - 1
        RefB = 2*Db - 1
        RefC = 2*Dc - 1

        # Switching states
        Sa = float(carrier <= RefA)
        Sb = float(carrier <= RefB)
        Sc = float(carrier <= RefC)

        # Pole voltages
        vao = (2*Sa - 1)*(self.Vcc/2)
        vbo = (2*Sb - 1)*(self.Vcc/2)
        vco = (2*Sc - 1)*(self.Vcc/2)

        # Phase voltages
        van = (2/3)*vao - (1/3)*(vbo + vco)

        vbn = (2/3)*vbo - (1/3)*(vao + vco)

        vcn = (2/3)*vco - (1/3)*(vbo + vao)

        self.k += 1

        return van, vbn, vcn

    def calc(self,

             # Reference speed
             wref,

             # Time (kept for interface compatibility)
             t,

             # FOC parameters
             wr=0.0,
             ia=0.0,
             ib=0.0,
             ic=0.0,
             dt=None):

        """ Main inverter method """

        va, vb, vc, teta, weixo = self.ifoc_control(
            wref,
            wr,
            ia,
            ib,
            ic,
            dt
        )

        return {
            'va': va,
            'vb': vb,
            'vc': vc,
            'teta': teta,
            'weixo': weixo
        }