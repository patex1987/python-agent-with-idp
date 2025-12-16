#!/usr/bin/env python3
"""
Retrieve an access token from Keycloak using the password grant flow.

This script reads configuration from environment variables and outputs
the access token for use in API calls.

Usage:
    python get_keycloak_token.py

Environment Variables:
    KEYCLOAK_URL: Keycloak base URL (default: http://localhost:8082)
    KEYCLOAK_REALM: Realm name (default: throttling-test)
    KEYCLOAK_CLIENT_ID: Client ID (default: throttling-api)
    KEYCLOAK_CLIENT_SECRET: Client secret (default: test-client-secret)
    KEYCLOAK_USERNAME: Username for password grant (default: test-user)
    KEYCLOAK_PASSWORD: Password for password grant (default: test-password)
"""

import os
import sys
from typing import Optional

import httpx


def get_env_var(key: str, default: str) -> str:
    """Get environment variable with default value."""
    return os.getenv(key, default)


def get_keycloak_token(
    keycloak_url: str,
    realm: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
) -> dict:
    """
    Retrieve an access token from Keycloak using password grant.

    :param keycloak_url: Base URL of Keycloak instance
    :param realm: Realm name
    :param client_id: Client ID
    :param client_secret: Client secret
    :param username: Username for authentication
    :param password: Password for authentication
    :return: Token response dictionary containing access_token, refresh_token, etc.
    :raises: httpx.HTTPStatusError if the request fails
    """
    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

    data = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def refresh_keycloak_token(
    keycloak_url: str,
    realm: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """
    Refresh an access token using a refresh token.

    :param keycloak_url: Base URL of Keycloak instance
    :param realm: Realm name
    :param client_id: Client ID
    :param client_secret: Client secret
    :param refresh_token: Refresh token from previous authentication
    :return: Token response dictionary containing new access_token, refresh_token, etc.
    :raises: httpx.HTTPStatusError if the request fails
    """
    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def main():
    """Main entry point for the script."""
    # Read configuration from environment variables
    keycloak_url = get_env_var("KEYCLOAK_URL", "http://localhost:8082")
    realm = get_env_var("KEYCLOAK_REALM", "throttling-test")
    client_id = get_env_var("KEYCLOAK_CLIENT_ID", "throttling-api")
    client_secret = get_env_var("KEYCLOAK_CLIENT_SECRET", "test-client-secret")
    username = get_env_var("KEYCLOAK_USERNAME", "test-user")
    password = get_env_var("KEYCLOAK_PASSWORD", "test-password")

    # Check if refresh token is provided
    refresh_token = os.getenv("KEYCLOAK_REFRESH_TOKEN")

    try:
        if refresh_token:
            # Use refresh token flow
            token_response = refresh_keycloak_token(
                keycloak_url=keycloak_url,
                realm=realm,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
        else:
            # Use password grant flow
            token_response = get_keycloak_token(
                keycloak_url=keycloak_url,
                realm=realm,
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
            )

        # Output the access token (useful for shell scripts)
        access_token = token_response.get("access_token")
        if access_token:
            print(access_token, file=sys.stdout)
            # Also print full response to stderr for debugging
            print(
                f"\nToken details:\n  Expires in: {token_response.get('expires_in')}s\n  Token type: {token_response.get('token_type')}\n  Scope: {token_response.get('scope')}",
                file=sys.stderr,
            )
            return 0
        else:
            print("Error: No access_token in response", file=sys.stderr)
            print(f"Response: {token_response}", file=sys.stderr)
            return 1

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to Keycloak: {e}", file=sys.stderr)
        print(f"URL: {keycloak_url}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
