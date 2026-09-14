import numpy as np

"""Three-Phase Coordinate Transformations 
     Convention:
         - q-axis aligned with cosine
         - d-axis aligned with sine
         - id → flux
         - iq → torque
"""

def abc_dq0(a, b, c, theta):
    """
    Input parameters:
    a, b, c : float
        Three-phase components (e.g., current, voltage)
    theta : float
        Electrical angle [rad]

    Output:
    q : float
        q-axis component (related to electromagnetic torque)
    d : float
        d-axis component (related to electromagnetic flux)
    zero : float
        Zero sequency component
    """

    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    cos_t_120 = np.cos(theta - 2*np.pi/3)
    sin_t_120 = np.sin(theta - 2*np.pi/3)

    cos_t_p120 = np.cos(theta + 2*np.pi/3)
    sin_t_p120 = np.sin(theta + 2*np.pi/3)

    q = (2.0 / 3.0) * (a*cos_t + b*cos_t_120 + c*cos_t_p120)
    d = (2.0 / 3.0) * (a*sin_t + b*sin_t_120 + c*sin_t_p120)

    zero = (1.0 / 3.0) * (a + b + c)

    return q, d, zero

def dq0_abc(q, d, zero, theta):
    """
    Input parametes:
    q : float
        q-axis component
    d : float
        d-axis component
    zero : float
        Zero sequency component
    theta : float
        Electrical angle [rad]

    Output
    a, b, c : float
        Three-phase components (e.g., current, voltage)
    """

    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    cos_t_120 = np.cos(theta - 2*np.pi/3)
    sin_t_120 = np.sin(theta - 2*np.pi/3)

    cos_t_p120 = np.cos(theta + 2*np.pi/3)
    sin_t_p120 = np.sin(theta + 2*np.pi/3)

    # Igual ao MATLAB:
    a = q*cos_t + d*sin_t + zero
    b = q*cos_t_120 + d*sin_t_120 + zero
    c = q*cos_t_p120 + d*sin_t_p120 + zero

    return a, b, c