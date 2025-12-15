from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents an authenticated user with their claims."""

    user_id: str
    username: str
    email: str | None
    roles: list[str]
    scopes: list[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
