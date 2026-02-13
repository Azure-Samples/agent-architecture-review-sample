"""
Shared test data for Architecture Review Agent tests.
Constants and sample inputs used across test modules.
"""

# ── Sample YAML architecture ────────────────────────────────────────────

SAMPLE_YAML = """\
name: Test Architecture
components:
  - name: API Gateway
    type: gateway
    technology: Kong
    replicas: 2
  - name: User Service
    type: service
    replicas: 3
  - name: Order Service
    type: service
    replicas: 1
  - name: User Database
    type: database
    technology: PostgreSQL
    replicas: 1
  - name: Order Database
    type: database
    technology: PostgreSQL
    replicas: 1
  - name: Redis Cache
    type: cache
    replicas: 1

connections:
  - from: api_gateway
    to: user_service
    protocol: REST
  - from: api_gateway
    to: order_service
    protocol: REST
  - from: user_service
    to: user_database
    protocol: TCP
  - from: order_service
    to: order_database
    protocol: TCP
  - from: user_service
    to: redis_cache
    protocol: TCP
  - from: order_service
    to: redis_cache
    protocol: TCP
"""


# ── Sample Markdown architecture ────────────────────────────────────────

SAMPLE_MARKDOWN = """\
## Components

### Edge Gateway
- **Type:** gateway
- **Technology:** Azure IoT Edge
- **Replicas:** 4

### Stream Processor
- **Type:** service
- **Technology:** Apache Flink
- **Replicas:** 2

### Hot Storage
- **Type:** database
- **Technology:** Cosmos DB

## Connections
- Edge Gateway -> Stream Processor (MQTT)
- Stream Processor -> Hot Storage (SDK)
"""


# ── Sample plaintext architecture ───────────────────────────────────────

SAMPLE_TEXT = """\
Load Balancer -> Web Server -> App Server -> PostgreSQL DB
Web Server -> Redis Cache
App Server -> Message Queue
"""
