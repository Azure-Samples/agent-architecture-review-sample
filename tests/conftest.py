"""
Shared fixtures for Architecture Review Agent tests.
"""

import pytest


# ── Parsed component/connection fixtures ────────────────────────────────

@pytest.fixture
def sample_components():
    """Minimal component list for unit tests."""
    return [
        {"id": "api_gateway", "name": "API Gateway", "type": "gateway",
         "description": "", "replicas": 1, "technology": "Kong"},
        {"id": "user_service", "name": "User Service", "type": "service",
         "description": "", "replicas": 3, "technology": ""},
        {"id": "user_db", "name": "User DB", "type": "database",
         "description": "", "replicas": 1, "technology": "PostgreSQL"},
        {"id": "redis_cache", "name": "Redis Cache", "type": "cache",
         "description": "", "replicas": 1, "technology": "Redis"},
    ]


@pytest.fixture
def sample_connections():
    """Minimal connection list for unit tests."""
    return [
        {"source": "api_gateway", "target": "user_service", "label": "REST", "type": "sync"},
        {"source": "user_service", "target": "user_db", "label": "TCP", "type": "sync"},
        {"source": "user_service", "target": "redis_cache", "label": "TCP", "type": "sync"},
    ]


@pytest.fixture
def multi_writer_components():
    """Components where multiple services write to one DB — for anti-pattern detection."""
    return [
        {"id": "svc_a", "name": "Service A", "type": "service", "replicas": 2, "technology": ""},
        {"id": "svc_b", "name": "Service B", "type": "service", "replicas": 2, "technology": ""},
        {"id": "shared_db", "name": "Shared DB", "type": "database", "replicas": 1, "technology": "PostgreSQL"},
    ]


@pytest.fixture
def multi_writer_connections():
    """Two services writing to the same database."""
    return [
        {"source": "svc_a", "target": "shared_db", "label": "", "type": "sync"},
        {"source": "svc_b", "target": "shared_db", "label": "", "type": "sync"},
    ]


@pytest.fixture
def frontend_to_db_components():
    """Frontend with direct DB access — security risk."""
    return [
        {"id": "frontend", "name": "React App", "type": "frontend", "replicas": 1, "technology": "React"},
        {"id": "user_db", "name": "User DB", "type": "database", "replicas": 1, "technology": "PostgreSQL"},
    ]


@pytest.fixture
def frontend_to_db_connections():
    """Direct frontend → database connection."""
    return [
        {"source": "frontend", "target": "user_db", "label": "", "type": "sync"},
    ]
