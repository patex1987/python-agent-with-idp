from dataclasses import dataclass


@dataclass
class Coordinate:
    x: float
    y: float

    def calc_euclidean_distance(self, other: "Coordinate") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
