"""
Worker module for run execution.

This module contains all worker-related logic. A worker is the entity responsible for
executing runs that are requested via the POST endpoint.

Architecture:
    Run orchestration and execution are completely decoupled. This module provides
    an in-memory implementation for local development and testing.
"""

