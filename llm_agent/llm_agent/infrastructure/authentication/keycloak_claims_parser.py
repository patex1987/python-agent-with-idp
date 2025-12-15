"""
Utility for parsing Keycloak JWT token claims into AuthenticatedUser.
"""

from llm_agent.domain.authentication.user import AuthenticatedUser


def parse_keycloak_claims(claims: dict) -> AuthenticatedUser:
    """
    Parse Keycloak JWT token claims into an AuthenticatedUser.

    :param claims: The validated token claims dictionary from Keycloak
    :return: AuthenticatedUser with extracted identity information
    """
    user_id = claims["sub"]
    username = claims.get("preferred_username") or claims.get("name") or user_id
    email = claims.get("email")

    # Extract roles: realm roles + client roles
    roles = []
    if realm_roles := claims.get("realm_access", {}).get("roles"):
        roles.extend(realm_roles)
    if resource_access := claims.get("resource_access"):
        for client_roles in resource_access.values():
            if client_role_list := client_roles.get("roles"):
                roles.extend(client_role_list)

    # Extract scopes
    scope_str = claims.get("scope", "")
    scopes = scope_str.split() if scope_str else []

    return AuthenticatedUser(
        user_id=user_id,
        username=username,
        email=email,
        roles=roles,
        scopes=scopes,
    )
