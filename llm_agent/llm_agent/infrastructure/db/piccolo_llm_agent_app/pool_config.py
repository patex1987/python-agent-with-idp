def get_db_pool_config():
    return {
        "min_size": 1,
        "max_size": 20,
        "max_queries": 50_000,  # rotate conns after N queries
        "max_inactive_connection_lifetime": 100,  # seconds; drop idle/stale conns
        # You can also pass asyncpg 'setup' / 'init' callables if needed
    }
