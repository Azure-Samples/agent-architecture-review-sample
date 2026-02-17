# Demo Scenarios

Pre-built scenarios for validating and demoing the Architecture Review Agent.

| Scenario | Format | Description |
|----------|--------|-------------|
| `ecommerce.yaml` | YAML | E-commerce platform with API gateway, microservices, and message queue |
| `event_driven.md` | Markdown | Event-driven IoT pipeline with Azure services |
| `healthcare_platform.yaml` | YAML | Multi-tier healthcare platform with HIPAA considerations |
| `microservices_banking.yaml` | YAML | Banking microservices with event sourcing and CQRS |
| `startup_mvp.yaml` | YAML | Minimal viable product with typical startup shortcuts |

## Usage

### Local CLI
```bash
python run_local.py scenarios/ecommerce.yaml
python run_local.py scenarios/event_driven.md
python run_local.py scenarios/healthcare_platform.yaml
python run_local.py scenarios/microservices_banking.yaml
python run_local.py scenarios/startup_mvp.yaml
```

### Web UI
1. Start the backend: `python api.py`
2. Start the frontend: `cd frontend && npm run dev`
3. Paste or upload any scenario file in the web UI.
