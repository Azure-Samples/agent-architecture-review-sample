# Event-Driven IoT Pipeline

## Components

### Edge Gateway
- **Type:** gateway
- **Technology:** Azure IoT Edge
- **Replicas:** 10
- Collects sensor data from field devices and performs edge inference

### Ingestion Hub
- **Type:** queue
- **Technology:** Azure Event Hubs
- **Replicas:** 4
- Central telemetry ingestion point with partitioned consumers

### Stream Processor
- **Type:** service
- **Technology:** Azure Stream Analytics / Apache Flink
- **Replicas:** 3
- Real-time anomaly detection and data enrichment

### Cold Storage
- **Type:** database
- **Technology:** Azure Data Lake Gen2
- **Replicas:** 1
- Long-term telemetry archive for batch analytics

### Hot Storage
- **Type:** database
- **Technology:** Azure Cosmos DB
- **Replicas:** 3
- Low-latency reads for dashboards and alerts

### Alert Service
- **Type:** service
- **Technology:** Azure Functions
- **Replicas:** 1
- Triggers alerts based on anomaly thresholds

### Dashboard API
- **Type:** service
- **Technology:** Node.js Express
- **Replicas:** 2
- Serves real-time dashboards and historical queries

### Notification Service
- **Type:** service
- **Technology:** Azure Logic Apps
- **Replicas:** 1
- Sends SMS, email, and Teams notifications

## Connections

- Edge Gateway -> Ingestion Hub (MQTT over AMQP)
- Ingestion Hub -> Stream Processor (Event Hub consumer)
- Stream Processor -> Hot Storage (Cosmos DB SDK)
- Stream Processor -> Cold Storage (ADLS SDK)
- Stream Processor -> Alert Service (HTTP webhook)
- Alert Service -> Notification Service (HTTP)
- Dashboard API -> Hot Storage (Cosmos DB SDK)
- Dashboard API -> Cold Storage (ADLS query)
