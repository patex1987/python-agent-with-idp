from dataclasses import dataclass


@dataclass
class ThrottleCalculationInput:
    """
    :param v0: initial speed
    :param mass: mass
    :param friction: friction
    :param d_target: target distance
    """

    v0: float
    mass: float
    friction: float
    d_target: float
