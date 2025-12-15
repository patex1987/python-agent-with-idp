from dataclasses import dataclass

from llm_agent.domain.genetic_path.fitness_score import FitnessScore


@dataclass
class ThrottleSequenceGeneticResult:
    sequence: list[int]
    fitness_score: FitnessScore
