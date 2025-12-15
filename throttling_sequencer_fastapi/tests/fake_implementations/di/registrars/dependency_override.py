from typing import Any

import svcs

from throttling_sequencer.di.registrars.base import Registrar


class DependencyOverrideRegistrar(Registrar):
    """
    Registrar that allows overriding dependencies in tests.

    This registrar is used for testing to replace dependencies with test
    doubles (mocks, fakes, or stubs). It registers factory and value
    overrides into the DI registry, enabling test-specific dependency
    injection without modifying production code.

    :param factory_overrides: Dictionary mapping types to factory functions
        that will be registered instead of production factories.
    :param value_overrides: Dictionary mapping types to singleton values
        that will be registered instead of production values.

    Example:

        registrar = OverridableRegistrar(
            factory_overrides={SomeRepository: InMemoryRepository},
            value_overrides={GameStateRetriever: FakeGameStateRetriever()}
        )

    """

    def __init__(self, factory_overrides: dict[type, Any], value_overrides: dict[type, Any]) -> None:
        self.factory_overrides = factory_overrides
        self.value_overrides = value_overrides

    def register(self, registry: svcs.Registry) -> None:
        for type_, factory in self.factory_overrides.items():
            registry.register_factory(type_, factory=factory)
        for type_, value in self.value_overrides.items():
            registry.register_value(type_, value=value)
