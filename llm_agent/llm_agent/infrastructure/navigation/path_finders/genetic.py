import structlog

from llm_agent.domain.game.game_state import GameState
from llm_agent.domain.game.unit import Unit
from llm_agent.domain.grid.goal import UnitGoal
from llm_agent.domain.navigation.path_finder import PathFinderStrategy

import random

import time

from llm_agent.domain.genetic_path.configuration import GeneticConfiguration
from llm_agent.domain.genetic_path.fitness_score import FitnessScore
from llm_agent.domain.genetic_path.input import ThrottleCalculationInput
from llm_agent.domain.genetic_path.result import ThrottleSequenceGeneticResult


logger = structlog.get_logger(__name__)


class GeneticPathFinderStrategy(PathFinderStrategy):
    def __init__(self, genetic_configration: GeneticConfiguration):
        self.genetic_configration = genetic_configration

    def find_path(self, game_state: GameState, main_unit: Unit, target_unit: Unit) -> list[UnitGoal]:
        """
        Module contains functions to optimize the throttle sequence to a reach a given goal
        Main entrypoint is the `genetic_algorithm` function
        """

        logger.info("finding path with genetic algorithm")
        distance_to_target = main_unit.coordinate.calc_euclidean_distance(target_unit.coordinate)
        throttle_input = ThrottleCalculationInput(
            v0=main_unit.speed,
            mass=main_unit.mass,
            friction=main_unit.friction,
            d_target=distance_to_target,
        )
        result = find_optimal_throttle_sequence(throttle_input, self.genetic_configration)
        return [UnitGoal(target_unit.coordinate, throttle) for throttle in result.sequence]


def find_optimal_throttle_sequence(
    throttle_calculation_input: ThrottleCalculationInput,
    genetic_configration: GeneticConfiguration,
) -> ThrottleSequenceGeneticResult:
    """
    Run the genetic algorithm to find the optimal variable-length throttle sequence.

    :param throttle_calculation_input: ThrottleCalculationInput
    :param genetic_configration: GeneticConfiguration

    :return: ThrottleSequenceGeneticResult
    """
    # unpacking - #TODO: refactor this part
    v0 = throttle_calculation_input.v0
    mass = throttle_calculation_input.mass
    friction = throttle_calculation_input.friction
    d_target = throttle_calculation_input.d_target

    # Step 1: Initialize the population
    population = generate_initial_population(
        genetic_configration.population_size,
        genetic_configration.max_sequence_length,
        genetic_configration.throttle_range,
    )
    start_time = time.monotonic_ns() / 1e6  # Start time in milliseconds

    best_throttle_sequence = None
    best_fitness = None

    for generation in range(genetic_configration.num_generations):
        # Step 2: Calculate fitness for each individual in the population
        fitness_scores: list[FitnessScore] = [
            fitness(
                v0,
                throttles,
                mass,
                friction,
                d_target,
                genetic_configration.speed_threshold,
                genetic_configration.distance_weight,
                genetic_configration.speed_weight,
                genetic_configration.length_weight,
                genetic_configration.nonzero_weight,
            )
            for throttles in population
        ]

        # Step 3: Select the best individuals as parents
        best_parents = select_best_parents(population, fitness_scores, genetic_configration.num_best_parents)
        worst_parents = select_random_parents(population, fitness_scores, genetic_configration.num_worst_parents)

        all_parents = best_parents + worst_parents

        # Step 4: Create the next generation through crossover
        next_generation: list[list[int]] = []
        while len(next_generation) < genetic_configration.population_size:
            parent1, parent2 = random.sample(all_parents, 2)
            child = crossover(parent1, parent2, genetic_configration.max_sequence_length)
            next_generation.append(child)

        # Step 5: Apply mutation to the offspring
        next_generation = [
            mutate(child, genetic_configration.throttle_range, genetic_configration.mutation_rate)
            for child in next_generation
        ]

        # Display progress
        best_fitness = min(fitness_scores, key=lambda x: x.score)
        best_throttle_sequence = population[fitness_scores.index(best_fitness)]
        # print(
        #     f"Generation {generation + 1}, "
        #     f"best score: {best_fitness[0]:.02f}, distance_diff: {best_fitness[1]:.02f}, "
        #     f"speed diff: {best_fitness[2]:.02f}, "
        #     f"best sequence length: {best_fitness[3]} or {len(best_throttle_sequence)}"
        # )
        # print('[{}] {} -> {:.02f}'.format(generation + 1, best_throttle_sequence, best_fitness[0]))

        # if best_fitness[1] <= 3 and best_fitness[2] <= 3:
        #     print("Found a good enough solution!")
        #     break
        # Update the population
        population = next_generation
        actual_time = time.monotonic_ns() / 1e6  # Current time in milliseconds
        if actual_time - start_time >= genetic_configration.timeout_ms:
            logger.info("Timeout reached after {} generations".format(generation + 1))
            return ThrottleSequenceGeneticResult(best_throttle_sequence, best_fitness)

    return ThrottleSequenceGeneticResult(best_throttle_sequence, best_fitness)


def calculate_velocity(v0, throttle, m, f):
    """
    Calculate the velocity at time t given the throttle at that time.
    """
    return (v0 + (throttle / m)) * (1 - f)


def calculate_total_distance(v0, throttles, m, f):
    """
    Calculate the total distance after applying the sequence of throttles.
    The distance is the sum of velocities over each time step.
    """
    total_distance = 0
    velocity = v0

    for throttle in throttles:
        velocity = calculate_velocity(velocity, throttle, m, f)
        total_distance += velocity

    return total_distance, velocity


def fitness(
    v0,
    throttles,
    m,
    f,
    d_target,
    v_threshold,
    distance_weight=1.0,
    speed_weight=2.5,
    length_weight=0.1,
    nonzero_weight=0.1,
) -> FitnessScore:
    """
    Fitness function:
    - w1: weight for distance difference
    - w2: weight for final speed penalty
    - w3: weight for length penalty

    :param v0:
    :param throttles:
    :param m:
    :param f:
    :param d_target:
    :param v_threshold:
    :param distance_weight:
    :param speed_weight:
    :param length_weight:
    :param nonzero_weight:
    :return: tuple of:
        - score: the fitness score (lower is better)
        - distance_diff: the absolute difference from the target distance
        - speed_penalty: the penalty for the final speed (and its difference from the speed threshold)
        - length_penalty: the penalty for the length of the sequence
    """
    total_distance, final_speed = calculate_total_distance(v0, throttles, m, f)

    # Distance difference: we want to minimize the absolute difference from the target
    distance_diff = abs(d_target - total_distance)

    # Final speed penalty: the best is 0 speed at the end
    if 0 <= final_speed <= v_threshold:
        speed_penalty = 0
    else:
        speed_penalty = abs(final_speed - v_threshold)  # Heavy penalty for speeds above threshold

    # Length penalty: we want to minimize the number of steps
    length_penalty = len(throttles)

    # Calculate the final score (lower is better)
    nonzero_count = len(throttles) - throttles.count(0)  # Count non-zero throttles
    score = (
        (distance_weight * distance_diff)
        + (speed_weight * speed_penalty)
        + (length_weight * length_penalty)
        + (nonzero_count * nonzero_weight)
    )

    return FitnessScore(score, distance_diff, speed_penalty, length_penalty)


def generate_initial_population(pop_size, max_t, throttle_range):
    """
    Generate an initial population of variable-length throttle sequences.
    The length of each sequence can vary from 1 to max_t.
    """
    population = []
    for _ in range(pop_size):
        length = random.randint(1, max_t)  # Variable length
        throttles = [random.randint(throttle_range[0], throttle_range[1]) for _ in range(length)]
        population.append(throttles)
    return population


def select_best_parents(population, fitnesses: list[FitnessScore], num_parents):
    """
    Select the best solutions to become parents.
    """
    parents = sorted(zip(population, fitnesses), key=lambda x: x[1].score)[:num_parents]
    return [p[0] for p in parents]


def select_random_parents(population, fitnesses: list[FitnessScore], num_parents):
    """
    Select the worst solutions to become parents.
    """
    parents = random.sample(population, num_parents)
    return parents


def crossover(parent1, parent2, max_allowed_length: int):
    """
    Perform crossover between two parents to produce a child.
    Handles variable-length sequences by randomly combining parts of the parents.
    """
    crossover_point1 = random.randint(1, len(parent1))
    crossover_point2 = random.randint(1, len(parent2))
    child = parent1[:crossover_point1] + parent2[crossover_point2:]

    if len(child) >= max_allowed_length:
        child = child[:max_allowed_length]  # Trim to max length
    return child


def mutate(throttle_sequence, throttle_range, mutation_rate=0.1):
    """
    Mutate a throttle sequence with a given mutation rate.
    """
    for i in range(len(throttle_sequence)):
        if random.random() < mutation_rate:
            throttle_sequence[i] = random.randint(throttle_range[0], throttle_range[1])

    # # Random insertion of a new throttle value
    # if random.random() < mutation_rate and len(throttle_sequence) < max_length:
    #     insert_pos = random.randint(0, len(throttle_sequence))
    #     new_value = random.randint(throttle_range[0], throttle_range[1])
    #     throttle_sequence.insert(insert_pos, new_value)

    # Random deletion of an existing throttle value
    if random.random() < mutation_rate and len(throttle_sequence) > 1:  # Ensure at least 1 value
        delete_pos = random.randint(0, len(throttle_sequence) - 1)
        del throttle_sequence[delete_pos]

    return throttle_sequence


def get_distance_for_throttles_velocities(v0, m, f, throttles, start_position):
    """
    Run the path for a given sequence of throttles and return the final velocity.
    """
    actual_velocity = v0
    distance = start_position
    distance_velocities = [(distance, actual_velocity)]
    for throttle in throttles:
        actual_velocity = calculate_velocity(actual_velocity, throttle, m, f)
        distance += actual_velocity
        # print('Actual position: {}'.format(position))
        distance_velocities.append((distance, actual_velocity))

    return distance_velocities
