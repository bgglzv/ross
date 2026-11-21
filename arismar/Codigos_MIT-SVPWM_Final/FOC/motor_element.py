"""Electric Motor Element module.

This module defines the MotorElement class which represents a 3-phase Induction Electric Motor
simulated using a 4th-order Runge-Kutta method, considering magnetic fluxes and currents.
"""
#import plotly.graph_objects as go
#from plotly.subplots import make_subplots
import numpy as np
#from ross.element import Element


__all__ = ["MotorElement"]


class MotorElement:
    """A 3-phase Induction Motor element.

    This class creates a electric Three-Phase Induction Motor (TPIM) assuming
    rotor flux as sinchronous reference


    Attributes
    ----------
    n: int
        Node in which the motor will be couppled.
    tag : str, optional
        A tag to name the element
        Default is None
    
    ----Nominal Operational Machine Parameters (NOMP)
    Pnom : float
        Nominal power [W].
    Vnom : float
        Nominal voltage [V].
    RPMnom : float
        Nominal machine rotation [RPM].
    fnom : float
        Nominal frequency [Hz].
    npol: int
        Number of machine's poles [ad].
        
    ----Circuit-Equivalent Model Parameters (CEMP)  
    Rs : float
        Stator resistance [Ohm].
    Rr : float
        Rotor resistance [Ohm].
    Xls : float
        Stator self-reactance at fnom [Ohm].
    Xlr : float
        Rotor self-reactance at fnom [Ohm].
    Xm : float
        Mutual reactance at fnom [Ohm].
    Jm : float
        Polar Moment of inertia: motor axis [kg*m2].
    Bm : float
        Viscous friction coeficient [Pa*s].
    Jl : float
        Polar Moment of inertia: load [kg*m2].

    ----Short-Circuit Impedance Parameters (SCIP)  
    Vnet : float
        Electrical tension of Power Supply [V].
    fnet : float
        Electrical frequency of Power Supply [Hz].
    ainet : float
        Initial angular phase frequency of Power Supply [°].            
    SCRnet : float
        Short-Circuit Ratio in Common Coupling Point with Power Supply [ad].
    XRRnet : float
        Reactance/Resistance Ratio in Coupling Point with Power Supply [ad].
    """
    def __init__(self, 
             n,
             tag=None,
             Pnom=None,
             Vnom=None,
             RPMnom=None, 
             fnom=60.0,
             npol=4,
             Rs=None,
             Rr=None,
             Xls=None,
             Xlr=None,
             Xm=None,
             Jm=None,
             Bm=0.0,
             Jl=0.0,
             Vnet=None,
             fnet=None,
             ainet=20.0,
             SCRnet=50.0,
             XRRnet=80.0
             ):
      #  super().__init__(n, tag)

        # ---------- Numerical Validation of NOMP entries 
        if Pnom is None:
            raise ValueError(
                 "Nominal machine power (Pnom) must be a value in Watt greather than 0")
        else:
            self.Pnom = float(Pnom)

        if Vnom is None:
            raise ValueError(
                 "Nominal electrical tension (Vnom) must be a value in Volt greather than 0")
        else:
            self.Vnom = float(Vnom)

        if RPMnom is None:
            raise ValueError(
                 "Nominal machine rotation (RPMnom) must be a value in RPM greather than 0")
        else:
            self.RPMnom = float(RPMnom)

        if fnom is None:
            print ('Nominal electrical frequency (fnom) must be a value in Hertz greather than 0. \n Adopting fnom=60.0Hz')
            self.fnom = 60.0
        else:
            self.fnom = float(fnom)
            
        if npol is None:
            print ('Number of machine poles (npol) must be a integer value greather than 0. \n Adopting npol=4')
            self.npol = 4
        else:
            self.npol = int(npol)

        # ---------- Numerical Validation of CEMP entries 
        if Rs is None:           
            raise ValueError(
                 "Stator Resistance (Rs) must be a value in Ohm greather than 0")
        else:
            self.Rs = float(Rs)

        if Rr is None:           
            raise ValueError(
                 "Rotor Resistance (Rr) must be a value in Ohm greather than 0")
        else:
            self.Rr = float(Rr)

        if Xls is None:           
            raise ValueError(
                "Stator reactance at fnom (Xls) must be a value in Ohm greather than 0")
        else:
            self.Xls = float(Xls)

        if Xlr is None:           
            raise ValueError(
                "Rotor reactance at fnom (Xlr) must be a value in Ohm greather than 0")
        else:
            self.Xlr = float(Xlr)
            
        if Xm is None:           
            raise ValueError(
                "Mutual reactance at fnom (Xm) must be a value in Ohm greather than 0")
        else:
            self.Xm = float(Xm)

        if Jm is None:           
            raise ValueError(
                "Motor Axis Polar Moment of inertia (Jm) must be a value in kg*m2  greather than 0")
        else:
            self.Jm = float(Jm)

        if Bm is None:
            print ('Viscous friction coeficient (Bm) not inputted. \n Adopting Bm=0.0 Pa*s')
            self.Bm = 0.0
        else:
            self.Bm = float(Bm)
            
        if Jl is None:
            print ('Load Axis Polar Moment of inertia (Jl) not inputted. \n Adopting Jl=0.0 kg*m2')
            self.Jl = 0.0
        else:
            self.Jl = float(Jl)
            
        # ---------- Numerical Validation of SCIP entries 
        if Vnet is None:
            print('Electrical tension of Power Supply (Vnet) not inputted. \n Adopting Vnet=Vnom={:.1f}'.format(self.Vnom))
            self.Vnet = self.Vnom
        else:
            self.Vnet = float(Vnet)
            
        if fnet is None:
            print('Electrical frequency of Power Supply (fnet) not inputted. \n Adopting fnet=fnom={:.1f}'.format(self.fnom))
            self.fnet = self.fnom
        else:
            self.fnet = float(fnet)

        if ainet is None:
            print('Initial angular phase frequency of Power Supply (ainet) not inputted. \n Adopting ainet=20.0deg')
            self.ainet = 20.0
        else:
            self.ainet = float(ainet)

        if SCRnet is None:
            print ('Short-Circuit Ratio in Coupling Point with Power Supply (SCRnet) not inputted. \n Adopting SCRnet=50.0')
            self.SCRnet = 50.0
        else:
            self.SCRnet = float(SCRnet)
            
        if XRRnet is None:
            print ('Reactance/Resistance Ratio in Coupling Point with Power Supply (XRRnet) not inputted. \n Adopting XRRnet=80.0')
            self.XRRnet = 80.0
        else:
            self.XRRnet = float(XRRnet)

        # ---------- Internal model speed parameters derived from NOMP
        self.ws = 2 * np.pi * self.fnom
        self.wrnom = self.RPMnom  * np.pi / 30 # Converting to rad/s
        self.snom = (self.ws - self.wrnom * self.npol / 2) / self.ws * 100

        # ---------- Circuit-equivalent model parameters (CEMP) 
        # self.Rs = 0.087
        # self.Rr = 0.229
        # self.Lls = 0.302 / (2 * np.pi * self.fnom)
        # self.Llr = 0.302 / (2 * np.pi * self.fnom)
        # self.Lm = 13.08 / (2 * np.pi * self.fnom)
        # self.Lss = self.Lls + self.Lm
        # self.Lrr = self.Llr + self.Lm
        # self.Jm = 1.662
        # self.Bm = 0.0100

        # ---------- Internal model inductances parameters derived from CEMP
        self.Lls = self.Xls / (2 * np.pi * self.fnom)
        self.Llr = self.Xlr / (2 * np.pi * self.fnom)
        self.Lm = self.Xm / (2 * np.pi * self.fnom)
        self.Lss = self.Lls + self.Lm
        self.Lrr = self.Llr + self.Lm


        # ---------- Internal Electric Motor constants derived from NOMP and CEMP
        self.wnom = (2 * np.pi * self.fnom * (1 - self.snom / 100)) / (self.npol / 2)
        self.Tnom = self.Pnom / self.wnom
        self.sigma = 1 - self.Lm**2 / (self.Lss * self.Lrr)
        self.a = 1 / (self.sigma * self.Lss)
        self.b = 1 / (self.sigma * self.Lrr)
        self.c = self.Lm / (self.sigma * self.Lss * self.Lrr)

        # ---------- Short-Circuit Power and Impedances parameters derived from SCIP
        self.thetai = -(90 - self.ainet) * np.pi / 180
        self.SCCnet = self.SCRnet * self.Pnom
        self.Zsc = self.Vnet**2 / self.SCCnet
        self.Xsc = self.Zsc * self.XRRnet / np.sqrt(1 + self.XRRnet**2)
        self.Rsc = self.Xsc / self.XRRnet

        # ---------- Initial values of Rotor speed, Flux angle and Electrial Torque
        # Obs: a possible new feature is to insert non-null initial values user's parameters 
        self.wr = 0.0           #Rotor's angular speed in rad*s
        self.thetar = 0.0       #Rotor's angle in rad
        self.ro = self.thetai   #Flux's initial angle in rad
        self.Te = 0.0           #Electrical Torque in N*m

        # ---------- Initial alpha-beta and dq currents (based in nulled instantaneous phase currents)
        ias, ibs, ics = 0, 0, 0
        ialfas = 2 / 3 * (ias - ibs / 2 - ics / 2)
        ibetas = 2 / 3 * (ibs - ics) * np.sqrt(3) / 2
        ids = ialfas * np.cos(self.ro) + ibetas * np.sin(self.ro)
        iqs = -ialfas * np.sin(self.ro) + ibetas * np.cos(self.ro)

        # ---------- Initial rotor and stator's inductances
        self.Lds = self.Lss * ids + self.Lm * 0
        self.Lqs = self.Lss * iqs + self.Lm * 0
        self.Ldr = self.Lrr * 0 + self.Lm * ids
        self.Lqr = self.Lrr * 0 + self.Lm * iqs

    def __str__(self):
        """Convert object into string.

        Returns
        -------
        The object's user-defined parameters translated to strings
        """
        return (
            f"Tag:                                {self.tag}"
            f"\nNode:                               {self.n}"
            f"\n--- Nominal Parameters (NOMP) ---"
            f"\nNominal Power (W):                  {self.Pnom}"
            f"\nNominal Voltage (V):                {self.Vnom}"
            f"\nNominal Rotation (RPM):             {self.RPMnom}"
            f"\nNominal Frequency (Hz):             {self.fnom}"
            f"\nNumber of Poles:                    {self.npol}"
            f"\n--- Circuit Parameters (CEMP) ---"
            f"\nStator Resistance (Ohm):            {self.Rs}"
            f"\nRotor Resistance (Ohm):             {self.Rr}"
            f"\nStator Reactance (Ohm):             {self.Xls}"
            f"\nRotor Reactance (Ohm):              {self.Xlr}"
            f"\nMutual Reactance (Ohm):             {self.Xm}"
            f"\nMotor Inertia (kg*m2):              {self.Jm}"
            f"\nFriction Coef (Pa*s):               {self.Bm}"
            f"\nLoad Inertia (kg*m2):               {self.Jl}"
            f"\n--- Power Supply Parameters (SCIP) ---"
            f"\nSupply Voltage (V):                 {self.Vnet}"
            f"\nSupply Frequency (Hz):              {self.fnet}"
            f"\nInitial Phase Angle (deg):          {self.ainet}"
            f"\nShort-Circuit Ratio (ad):           {self.SCRnet}"
            f"\nX/R Ratio (ad):                     {self.XRRnet}"
        )

    def __repr__(self):
        """Return a string representation of the motor element's calculated internal parameters.

        Returns
        -------
        A string representation of a motor element object containing calculated values.
        """
        return (
            f"{self.__class__.__name__}("
            f"ws={self.ws:.4f}, wrnom={self.wrnom:.4f}, snom={self.snom:.4f}, "
            f"Lls={self.Lls:.4e}, Llr={self.Llr:.4e}, Lm={self.Lm:.4e}, Lss={self.Lss:.4e}, Lrr={self.Lrr:.4e}, "
            f"wnom={self.wnom:.4f}, Tnom={self.Tnom:.4f}, sigma={self.sigma:.4f}, "
            f"a={self.a:.4e}, b={self.b:.4e}, c={self.c:.4e}, "
            f"thetai={self.thetai:.4f}, SCCnet={self.SCCnet:.4f}, Zsc={self.Zsc:.4f}, Xsc={self.Xsc:.4f}, Rsc={self.Rsc:.4f}, "
            f"wr={self.wr:.4f}, thetar={self.thetar:.4f}, ro={self.ro:.4f}, Te={self.Te:.4f}, "
            f"Lds={self.Lds:.4e}, Lqs={self.Lqs:.4e}, Ldr={self.Ldr:.4e}, Lqr={self.Lqr:.4e})"
        )
    def dof_mapping(self):
        # Exemplo simples, precisa ajustar conforme a convenção de DOFs do ROSS (ex: torcional ou 6DOF)
        return {"alpha": 0} # ou o índice correspondente ao DOF rotacional

    def M(self):
        # Deve retornar matriz com a inércia Jm na posição correta
        m = np.zeros((1, 1)) # Dimensão depende do dof_mapping
        m[0, 0] = self.Jm
        return m

    def K(self):
        return np.zeros((1, 1))
    
    def C(self):
        return np.zeros((1, 1))

    def G(self):
        return np.zeros((1, 1))
    
    #def calc(self, h, t, vas, vbs, vcs, Tload, fe):   # <--- INCLUSÃO DO PARÂMETRO fref ---------------------------- < ----------
    def calc(self, h, t, vas, vbs, vcs, Tload, we):   # <--- INCLUSÃO DO PARÂMETRO fref ---------------------------- < ----------

        """Perform a single iteration calculation for the motor dynamics.

        This method calculates the state of the motor for a specific time point 't',
        given the input voltages and load torque. It uses a 4th-order Runge-Kutta
        integration step.

        Parameters
        ----------
        h : float, optional
            Simulation time step (step size) for the Runge-Kutta integration.
            Default is 1e-4.

        t : float
            Current simulation time [s].
        vas : float
            Phase A voltage [V].
        vbs : float
            Phase B voltage [V].
        vcs : float
            Phase C voltage [V].
        Tload : float
            Load torque applied to the shaft [N.m].


        Returns
        -------
        results : dict
            A dictionary containing the calculated values for the current step:
            - tempo: Time [s]
            - Ias, Ibs, Ics: Phase currents [A]
            - Ialfas, Ibetas: Alpha-Beta currents [A]
            - Ids, Iqs: d-q axis currents [A]
            - TE: Electromagnetic Torque [N.m]
            - TC: Load Torque [N.m]
        """
        # Determine step size h based on current time or use fixed internal h
        # Note: The original logic relies on a fixed h for the RK coefficients.
        # We assume the user calls this sequentially or we rely on the internal h.
        self.h = float(h)
        
        # Updating angles
        #weixo = 2 * np.pi * self.f
        #self.ro += weixo * h
        #self.thetar += (self.wr * self.npol / 2) * h

        weixo = we
        #weixo = 2 * np.pi * fref          # < ----- MODIFICAÇÃO NECESSÁRIA -------------------------------- <-------
        # weixo = 2 * np.pi * self.fnom
        self.ro += weixo * h
        self.thetar += (self.wr * self.npol / 2) * h

        # Clarke & Park Transforms for Voltages
        valfas = 2 / 3 * (vas - vbs / 2 - vcs / 2)
        vbetas = 2 / 3 * (vbs - vcs) * np.sqrt(3) / 2
        vds = valfas * np.cos(self.ro) + vbetas * np.sin(self.ro)
        vqs = -valfas * np.sin(self.ro) + vbetas * np.cos(self.ro)

        vdr, vqr = 0, 0

        # Constants for readability in RK4
        Rs, Rsc = self.Rs, self.Rsc
        Rr = self.Rr
        Lds, Lqs = self.Lds, self.Lqs
        Ldr, Lqr = self.Ldr, self.Lqr
        a, b, c = self.a, self.b, self.c
        wr = self.wr
        npol = self.npol
        Te = self.Te
        Jm, Jl = self.Jm, self.Jl
        Bm = self.Bm

        # --- Runge-Kutta 4th Order Step ---

        # Step 1
        k11 = h * (vds - (Rs + Rsc) * a * Lds + (Rs + Rsc) * c * Ldr + weixo * Lqs)
        k21 = h * (vqs - (Rs + Rsc) * a * Lqs + (Rs + Rsc) * c * Lqr - weixo * Lds)
        k31 = h * (vdr - Rr * b * Ldr + Rr * c * Lds + (weixo - wr * npol / 2) * Lqr)
        k41 = h * (vqr - Rr * b * Lqr + Rr * c * Lqs - (weixo - wr * npol / 2) * Ldr)
        k51 = h * (Te / (Jm + Jl) - Bm * wr / (Jm + Jl) - Tload / (Jm + Jl))

        Te_rk = 1.5 * c * ((Lqs + k21 / 2) * (Ldr + k31 / 2) - (Lds + k11 / 2) * (Lqr + k41 / 2)) * npol / 2

        # Step 2
        k12 = h * (vds - (Rs + Rsc) * a * (Lds + k11 / 2) + (Rs + Rsc) * c * (Ldr + k31 / 2) + weixo * (Lqs + k21 / 2))
        k22 = h * (vqs - (Rs + Rsc) * a * (Lqs + k21 / 2) + (Rs + Rsc) * c * (Lqr + k41 / 2) - weixo * (Lds + k11 / 2))
        k32 = h * (vdr - Rr * b * (Ldr + k31 / 2) + Rr * c * (Lds + k11 / 2) + (weixo - (wr + k51 / 2) * npol / 2) * (Lqr + k41 / 2))
        k42 = h * (vqr - Rr * b * (Lqr + k41 / 2) + Rr * c * (Lqs + k21 / 2) - (weixo - (wr + k51 / 2) * npol / 2) * (Ldr + k31 / 2))
        k52 = h * (Te_rk / (Jm + Jl) - Bm * (wr + k51 / 2) / (Jm + Jl) - Tload / (Jm + Jl))

        Te_rk = 1.5 * c * ((Lqs + k22 / 2) * (Ldr + k32 / 2) - (Lds + k12 / 2) * (Lqr + k42 / 2)) * npol / 2

        # Step 3
        k13 = h * (vds - (Rs + Rsc) * a * (Lds + k12 / 2) + (Rs + Rsc) * c * (Ldr + k32 / 2) + weixo * (Lqs + k22 / 2))
        k23 = h * (vqs - (Rs + Rsc) * a * (Lqs + k22 / 2) + (Rs + Rsc) * c * (Lqr + k42 / 2) - weixo * (Lds + k12 / 2))
        k33 = h * (vdr - Rr * b * (Ldr + k32 / 2) + Rr * c * (Lds + k12 / 2) + (weixo - (wr + k52 / 2) * npol / 2) * (Lqr + k42 / 2))
        k43 = h * (vqr - Rr * b * (Lqr + k42 / 2) + Rr * c * (Lqs + k22 / 2) - (weixo - (wr + k52 / 2) * npol / 2) * (Ldr + k32 / 2))
        k53 = h * (Te_rk / (Jm + Jl) - Bm * (wr + k52 / 2) / (Jm + Jl) - Tload / (Jm + Jl))

        Te_rk = 1.5 * c * ((Lqs + k23) * (Ldr + k33) - (Lds + k13) * (Lqr + k43)) * npol / 2

        # Step 4
        k14 = h * (vds - (Rs + Rsc) * a * (Lds + k13) + (Rs + Rsc) * c * (Ldr + k33) + weixo * (Lqs + k23))
        k24 = h * (vqs - (Rs + Rsc) * a * (Lqs + k23) + (Rs + Rsc) * c * (Lqr + k43) - weixo * (Lds + k13))
        k34 = h * (vdr - Rr * b * (Ldr + k33) + Rr * c * (Lds + k13) + (weixo - (wr + k53) * npol / 2) * (Lqr + k43))
        k44 = h * (vqr - Rr * b * (Lqr + k43) + Rr * c * (Lqs + k23) - (weixo - (wr + k53) * npol / 2) * (Ldr + k33))
        k54 = h * (Te_rk / (Jm + Jl) - Bm * (wr + k53) / (Jm + Jl) - Tload / (Jm + Jl))

        # Update State Variables
        self.Lds += (k11 + 2 * k12 + 2 * k13 + k14) / 6
        self.Lqs += (k21 + 2 * k22 + 2 * k23 + k24) / 6
        self.Ldr += (k31 + 2 * k32 + 2 * k33 + k34) / 6
        self.Lqr += (k41 + 2 * k42 + 2 * k43 + k44) / 6
        self.wr += (k51 + 2 * k52 + 2 * k53 + k54) / 6
        
        # Calculate Outputs
        ids = a * self.Lds - c * self.Ldr
        iqs = a * self.Lqs - c * self.Lqr
        self.Te = 1.5 * c * (self.Lqs * self.Ldr - self.Lds * self.Lqr) * npol / 2

        ialfas = ids * np.cos(self.ro) - iqs * np.sin(self.ro)
        ibetas = ids * np.sin(self.ro) + iqs * np.cos(self.ro)
        ias = ialfas
        ibs = -ialfas / 2 + np.sqrt(3) * ibetas / 2
        ics = -ialfas / 2 - np.sqrt(3) * ibetas / 2

        self.current_time = t

        return {
            'tempo': t,
            'Ias': ias,
            'Ibs': ibs,
            'Ics': ics,
            'Ialfas': ialfas,
            'Ibetas': ibetas,
            'Ids': ids,
            'Iqs': iqs,
            'TE': self.Te,
            'Tl': Tload,
            'wr': self.wr, 
            'RPM': self.wr * 30 / np.pi
        }

    def run(self, time_vector, vas_vector, vbs_vector, vcs_vector, Tload_vector):
        """Run the simulation for a series of time steps.

        Parameters
        ----------
        time_vector : array_like
            Array of time steps.
        vas_vector : array_like
            Array of Phase A voltages.
        vbs_vector : array_like
            Array of Phase B voltages.
        vcs_vector : array_like
            Array of Phase C voltages.
        Tload_vector : array_like
            Array of load torques.

        Returns
        -------
        results : dict
            A dictionary containing lists of results for the entire simulation:
            - tempo, Ias, Ibs, Ics, Ialfas, Ibetas, Ids, Iqs, TE, TC.
        """
        results = {
            'tempo': [], 'Ias': [], 'Ibs': [], 'Ics': [],
            'Ialfas': [], 'Ibetas': [], 'Ids': [], 'Iqs': [],
            'TE': [], 'TC': []
        }

        # Ensure inputs are iterable/arrays
        time_vector = np.array(time_vector)
        vas_vector = np.array(vas_vector)
        vbs_vector = np.array(vbs_vector)
        vcs_vector = np.array(vcs_vector)
        Tload_vector = np.array(Tload_vector)

        for i, t in enumerate(time_vector):
            # Extract inputs for the current step
            vas = vas_vector[i]
            vbs = vbs_vector[i]
            vcs = vcs_vector[i]
            Tload = Tload_vector[i]

            # Run single step calculation
            step_result = self.calc(t, vas, vbs, vcs, Tload)

            # Append results
            for key in results:
                results[key].append(step_result[key])

        return results
    
    def plot(self, results):
        """Plot the simulation results (Torque and Speed).
        
        Parameters
        ----------
        results : dict
            Dictionary returned by the 'run' method containing lists of results.
        
        Returns
        -------
        fig : plotly.graph_objects.Figure
            Figure with Torque and Speed subplots.
        """

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Scatter(x=results['time'], y=results['TE'], name="Torque (N.m)"),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(x=results['time'], y=results['wr'], name="Speed (rad/s)"),
            secondary_y=True,
        )

        fig.update_layout(title="Electric Motor Starting")
        fig.update_xaxes(title_text="Time (s)")
        fig.update_yaxes(title_text="Electromagnetic Torque (N.m)", secondary_y=False)
        fig.update_yaxes(title_text="Angular speed (rad/s)", secondary_y=True)

        return fig
def motor_example():
    """Create an example of disk element.

    This function returns an instance of a simple electric motor. The purpose is to make available
    a simple model so that doctest can be written using it.

    Returns
    -------
    motor : ross.MotorElement
        An instance of a motor object.

    Examples
    --------
    >>> motor = motor_example()
    >>> motor.RPNnom
    1725
    """
    motor = MotorElement(
             n=0,
             tag=None,
             Pnom=1.5*735.499,  #Direct conversion cv --> W
             Vnom=127,          #Volts      
             RPMnom=1725,       #RPM 
             fnom=60.0,         #Hz
             npol=4,            #Stator's poles
             Rs=2.5,            #Ohm
             Rr=1.8,            #Ohm
             Xls=1.3,           #Ohm
             Xlr=1.3,           #Ohm
             Xm=43.08,          #Ohm 
             Jm=0.0372,         #kg*m2
             Bm=0.0,            #kg*m*s2   
             Jl=0.0,            #kg*m2
             Vnet=127,          #Volts             
             fnet=60.0,         #Hz
             # ainet=20.0,        
             # SCRnet=50.0,
             # XRRnet=80.0
             )
    
    resul=motor.run(time_vector, vas_vector, vbs_vector, vcs_vector, Tload_vector)
    return motor
