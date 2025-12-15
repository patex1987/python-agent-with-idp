from dataclasses import dataclass


@dataclass
class FitnessScore:
    """
    - score: the fitness score (lower is better)
    - distance_diff: the absolute difference from the target distance
    - speed_penalty: the penalty for the final speed (and its difference
        from the speed threshold)
    - length_penalty: the penalty for the length of the sequence
    """

    score: float
    distance_diff: float
    speed_penalty: float
    length_penalty: int
